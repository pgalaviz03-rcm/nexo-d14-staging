"""PDF isolation, page provenance, document scoping and local library workflow."""
from pathlib import Path
import hashlib,io,json
import pytest
from fastapi import HTTPException,UploadFile
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
from sqlalchemy import select,func
from app.models import Dataset,DatasetBlob,AuditEvent
from app.pdf_evidence import extract_pdf,PdfInvalid
from app.library_api import prepare_pdf,pdf_packet,catalogue
from app.evidence_search import retrieve_context
from app.workspace_api import ContextRequest
from app.report_api import ReportInput
from test_manual_reviews import archive,endpoint

def pdf(texts=('Agua potable en el territorio.','Transporte y escuelas.')):
    writer=PdfWriter()
    for text in texts:
        page=writer.add_blank_page(width=600,height=800)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 30 700 Td ('+text.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')+') Tj ET').encode('ascii'))
        page[NameObject('/Contents')]=writer._add_object(stream)
    out=io.BytesIO();writer.write(out);return out.getvalue()

def add(a,raw=None,name='Informe.pdf',pid=None):
    raw=raw if raw is not None else pdf();s=a[1]
    row=Dataset(project_id=pid or a[2].id,uploaded_by=a[4][0].id,filename=name,media_type='.pdf',sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),status='staged',record_count=0,detail='Original guardado',path='database')
    s.add(row);s.flush();s.add(DatasetBlob(project_id=row.project_id,dataset_id=row.id,content=raw));s.commit();return row
def uploads(a):return Path(a[0].state.engine.url.database).parent/'uploads'
def prepare(a,row):return prepare_pdf(a[1],row.project_id,row.id,uploads(a),a[4][1].id)
def query(a,question='agua',**kw):return retrieve_context(a[1],a[2].id,question,uploads(a),source_kind='documents',**kw)
def call(a,path,method='GET',**kw):return endpoint(a[0],path,method)(pid=a[2].id,user=a[4][1],session=a[1],**kw)

def test_bounded_worker_extracts_text_with_physical_page_numbers(tmp_path):
    p=extract_pdf(pdf(),tmp_path);assert p['page_count']==2 and p['pages'][1]['number']==2
    assert 'Agua potable' in p['pages'][0]['text'] and 'Transporte' in p['pages'][1]['text'] and not p['ocr_used']
    assert list(tmp_path.iterdir())==[]

@pytest.mark.parametrize('raw',[b'not pdf',b'%PDF-invalid'])
def test_malformed_pdf_fails_without_partial_cache(tmp_path,raw):
    with pytest.raises(PdfInvalid):extract_pdf(raw,tmp_path)
    assert list(tmp_path.iterdir())==[]

def test_encrypted_pdf_is_not_guessed_or_decrypted(tmp_path):
    w=PdfWriter();w.add_blank_page(width=600,height=800);w.encrypt('secret-test-only');b=io.BytesIO();w.write(b)
    with pytest.raises(PdfInvalid,match='contraseña'):extract_pdf(b.getvalue(),tmp_path)

def test_page_limit_rejects_document_instead_of_silently_truncating(tmp_path):
    w=PdfWriter()
    for _ in range(161):w.add_blank_page(width=100,height=100)
    b=io.BytesIO();w.write(b)
    with pytest.raises(PdfInvalid,match='160'):extract_pdf(b.getvalue(),tmp_path)

def test_timeout_stops_worker_and_cleans_private_temporary_files(tmp_path,monkeypatch):
    monkeypatch.setattr('app.pdf_evidence.TIMEOUT',.000001)
    with pytest.raises(PdfInvalid,match='demasiado'):extract_pdf(pdf(),tmp_path)
    assert list(tmp_path.iterdir())==[]

def test_preparation_preserves_original_and_deduplicates_cache(archive):
    r=add(archive);before=(r.sha256,r.detail,r.status,bytes(archive[1].get(DatasetBlob,r.id).content))
    result=prepare(archive,r);assert result['searchable'] and result['page_count']==2
    assert (r.sha256,r.detail,r.status,bytes(archive[1].get(DatasetBlob,r.id).content))==before
    assert prepare(archive,r)['deduplicated']
    assert archive[1].scalar(select(func.count(Dataset.id)))==2

def test_search_cites_page_and_never_merges_neighbor_pages(archive):
    r=add(archive);prepare(archive,r);p=query(archive,'agua',document_id=r.id)
    assert len(p['citations'])==1;c=p['citations'][0]
    assert c['page']==1 and c['record_type']=='pdf_page' and c['pdf_origin']['sha256']==r.sha256
    assert 'Transporte' not in c['excerpt'] and c['citation']==f'D{r.id}:P1:0'

def test_document_filter_excludes_other_pdf_and_news(archive):
    a=add(archive);b=add(archive,pdf(('Agua otro informe.',)),name='Otro.pdf');prepare(archive,a);prepare(archive,b)
    p=query(archive,'agua',document_id=a.id)
    assert {c['dataset_id'] for c in p['citations']}=={a.id} and p['coverage']['news_scanned']==0

def test_nonexistent_or_foreign_document_is_not_a_global_search_fallback(archive):
    foreign=add(archive,pid=archive[3].id)
    for did in (foreign.id,999999):
        with pytest.raises(HTTPException) as exc:query(archive,document_id=did)
        assert exc.value.status_code==404

def test_original_integrity_failure_removes_cached_text_from_search(archive):
    r=add(archive);prepare(archive,r);archive[1].get(DatasetBlob,r.id).content=b'corrupt';archive[1].commit()
    assert not query(archive)['citations']

def test_sidecar_corruption_is_not_returned_as_raw_json(archive):
    r=add(archive);prepare(archive,r)
    cache=archive[1].scalar(select(Dataset).where(Dataset.id!=r.id));archive[1].get(DatasetBlob,cache.id).content=b'agua forged';archive[1].commit()
    assert not query(archive)['citations']

def test_catalogue_shows_original_once_and_actionable_ready_state(archive):
    r=add(archive);assert catalogue(archive[1],r.project_id,uploads(archive))['items'][0]['state']=='needs_prepare'
    prepare(archive,r);items=catalogue(archive[1],r.project_id,uploads(archive))['items']
    assert len(items)==1 and items[0]['id']==r.id and items[0]['state']=='ready'

def test_blank_pdf_is_ocr_needed_never_zero_as_positive_result(archive):
    r=add(archive,pdf(('',)));result=prepare(archive,r)
    assert not result['searchable'] and not query(archive)['citations']
    assert catalogue(archive[1],r.project_id,uploads(archive))['items'][0]['state']=='needs_ocr'

def test_empty_page_coverage_is_explicit_and_other_page_searchable(archive):
    r=add(archive,pdf(('Agua publica.','')));prepare(archive,r)
    assert catalogue(archive[1],r.project_id,uploads(archive))['items'][0]['state']=='partial'
    assert query(archive)['coverage']['not_indexed']==[dict(dataset_id=r.id,page=2,reason='pdf_page_without_text')]

def test_reader_page_is_scoped_and_out_of_range_rejected(archive):
    r=add(archive);prepare(archive,r)
    p=call(archive,'/api/projects/{pid}/library/documents/{dataset_id}/pages/{page_number}',dataset_id=r.id,page_number=2)
    assert p['page']==2 and 'Transporte' in p['text']
    with pytest.raises(HTTPException):call(archive,'/api/projects/{pid}/library/documents/{dataset_id}/pages/{page_number}',dataset_id=r.id,page_number=3)

def test_viewer_can_read_but_not_prepare_and_foreign_member_is_hidden(archive):
    r=add(archive);route=endpoint(archive[0],'/api/projects/{pid}/library/documents/{dataset_id}/prepare','POST')
    with pytest.raises(HTTPException) as exc:route(pid=r.project_id,dataset_id=r.id,user=archive[4][2],session=archive[1])
    assert exc.value.status_code==403
    listing=endpoint(archive[0],'/api/projects/{pid}/library/documents')
    assert not listing(pid=r.project_id,user=archive[4][2],session=archive[1])['can_prepare']
    with pytest.raises(HTTPException) as exc:listing(pid=r.project_id,user=archive[4][3],session=archive[1])
    assert exc.value.status_code==404

def test_failed_prepare_does_not_leave_a_dataset_or_extracted_text(archive):
    r=add(archive,b'%PDF-bad')
    with pytest.raises(HTTPException):prepare(archive,r)
    assert archive[1].scalar(select(func.count(Dataset.id)))==1

def test_upload_workflow_prepares_pdf_in_one_action(archive,monkeypatch):
    # Direct route contract: no event loop/network is opened in this environment.
    # PDF subprocess and resource limits run normally; only scheduling is inline.
    import tempfile
    async def inline(func,*args):return func(*args)
    monkeypatch.setattr('starlette.concurrency.run_in_threadpool',inline)
    stream=tempfile.SpooledTemporaryFile(max_size=1024*1024);stream.write(pdf());stream.seek(0)
    route=endpoint(archive[0],'/api/projects/{pid}/library/upload','POST')
    task=route(pid=archive[2].id,file=UploadFile(filename='Nuevo.pdf',file=stream),user=archive[4][1],session=archive[1])
    with pytest.raises(StopIteration) as done:task.send(None)
    result=done.value.value;stream.close()
    assert result['preparation']['searchable'] and 'listo' in result['detail']
    assert query(archive,document_id=result['id'])['citations']

def test_context_request_and_report_keep_selected_document_scope(archive):
    r=add(archive);prepare(archive,r)
    p=call(archive,'/api/projects/{pid}/knowledge/context','POST',body=ContextRequest(question='agua',document_id=r.id))
    assert p['document_id']==r.id
    made=call(archive,'/api/projects/{pid}/reports','POST',body=ReportInput(title='Consulta acotada',question='agua',document_id=r.id))
    detail=call(archive,'/api/projects/{pid}/reports/{report_id}',report_id=made['id'])
    assert detail['snapshot']['filters']['document_id']==r.id
    assert all(c['dataset_id']==r.id for c in detail['snapshot']['context']['citations'])

def test_audit_records_identifiers_not_extracted_text(archive):
    r=add(archive);prepare(archive,r)
    event=archive[1].scalar(select(AuditEvent).where(AuditEvent.action=='library.pdf.prepare'))
    assert event and 'Agua' not in event.target and 'pages:2' in event.target

def test_workspace_counts_originals_not_internal_extractions(archive):
    r=add(archive);prepare(archive,r)
    assert call(archive,'/api/projects/{pid}/workspace')['counts']['documents']==1

@pytest.mark.parametrize('path,size,expected',[
    ('/api/projects/1/library/upload',600_000,200),
    ('/api/projects/1/library/upload',14*1024*1024,413),
    ('/api/projects/1/knowledge/context',600_000,413)])
def test_upload_request_body_allowance_is_limited_to_upload_route(path,size,expected,monkeypatch):
    from app.controls import Guard
    messages=[]
    async def inline_wait(awaitable,timeout):return await awaitable
    monkeypatch.setattr('app.controls.asyncio.wait_for',inline_wait)
    async def downstream(scope,receive,send):
        await receive();await send(dict(type='http.response.start',status=200,headers=[]))
    async def receive():return dict(type='http.request',body=b'x'*size,more_body=False)
    async def send(message):messages.append(message)
    task=Guard(downstream,'test')(dict(type='http',method='POST',path=path,headers=[]),receive,send)
    with pytest.raises(StopIteration):task.send(None)
    assert next(m['status'] for m in messages if m['type']=='http.response.start')==expected


def test_compressed_large_content_is_rejected_in_isolated_worker(tmp_path):
    writer=PdfWriter();page=writer.add_blank_page(width=600,height=800)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 30 700 Td ('+b'X'*(8*1024*1024)+b') Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream.flate_encode())
    output=io.BytesIO();writer.write(output)
    assert len(output.getvalue())<100000
    with pytest.raises(PdfInvalid):extract_pdf(output.getvalue(),tmp_path)
