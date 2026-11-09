"""Project archive, document boundaries, explicit source selection and reports."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib,json,sqlite3
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from app.models import NewsArticle,Dataset,DatasetBlob,Report,ReportVersion,Membership,UsageCounter
from app.explorer_port import ExplorerQuery,EvidenceSelection,ExplorerReport,DisabledSemanticEvidenceSearch,SemanticSearchUnavailable
from app.explorer_service import search,selection,resolve,public_entry
from app.report_api import ReportRevision,ReleaseInput
from app.pulse_models import PulseBatch,PulseDocument,PulseMention,PulseActor
from test_manual_reviews import archive,endpoint
from test_pulse import add_actor

def catalog(a,**kwargs):return search(a[1],a[2].id,ExplorerQuery(**kwargs),(Path(a[0].state.engine.url.database).parent/'uploads'))
def document(a,text='Agua y movilidad en el proyecto',filename='Contexto.txt',*,pid=None,path='database',declared_hash=None):
    raw=text.encode();d=Dataset(project_id=pid or a[2].id,uploaded_by=a[4][0].id,filename=filename,media_type='text/plain',sha256=declared_hash or hashlib.sha256(raw).hexdigest(),size_bytes=len(raw),path=path)
    a[1].add(d);a[1].flush()
    if path=='database':a[1].add(DatasetBlob(dataset_id=d.id,project_id=d.project_id,content=raw))
    a[1].commit();return d
def save(a,refs,*,user=0,preview=None,**kw):
    p=preview or selection(a[1],a[2].id,refs,(Path(a[0].state.engine.url.database).parent/'uploads'))
    return endpoint(a[0],'/api/projects/{pid}/explorer/reports','POST')(pid=a[2].id,body=ExplorerReport(references=refs,preview_sha256=p['preview_sha256'],title='Selección ficticia',note='Nota de prueba',**kw),user=a[4][user],session=a[1])

def test_news_search_returns_only_own_project_and_no_filesystem_paths(archive):
    p=catalog(archive);assert len(p['items'])==1 and p['items'][0]['reference']==f'news:{archive[5][0].id}' and p['counts']['news']==1
    assert all(k not in p['items'][0] for k in ['path','uploaded_by','body']) and p['external_calls']==0

def test_lexical_search_handles_accents_and_literal_wildcards(archive):
    n=archive[5][0];n.title='Información ÁGUA y transporte';archive[1].commit()
    assert catalog(archive,q='informacion agua')['matched_in_scan']==1 and catalog(archive,q='%')['matched_in_scan']==0

def test_verified_document_content_and_metadata_are_searchable(archive):
    d=document(archive);p=catalog(archive,q='movilidad',kind='document');assert p['items'][0]['reference']==f'document:{d.id}' and p['items'][0]['preview_status']=='text_verified'
    assert catalog(archive,q='Contexto')['matched_in_scan']==1

@pytest.mark.parametrize('mode',['outside','bad_hash','pdf'])
def test_unsafe_or_unextractable_documents_have_metadata_only(archive,tmp_path,mode):
    f=tmp_path/'outside.txt';f.write_text('Never reveal outside content')
    d=document(archive,text='Never reveal outside content',filename='Ficha.pdf' if mode=='pdf' else 'Ficha.txt',path=str(f) if mode=='outside' else 'database',declared_hash='0'*64 if mode=='bad_hash' else None)
    p=catalog(archive,kind='document');assert p['items'][0]['excerpt']=='' and p['items'][0]['preview_status']!='text_verified'
    assert catalog(archive,q='Never reveal')['matched_in_scan']==0
    with pytest.raises(HTTPException) as e:selection(archive[1],archive[2].id,[f'document:{d.id}'],(Path(archive[0].state.engine.url.database).parent/'uploads'))
    assert e.value.status_code==422

def test_source_and_date_filters_use_declared_date_basis(archive):
    n=archive[5][0];n.published_at=None;n.ingested_at=datetime.now(timezone.utc)-timedelta(days=10);archive[1].commit()
    assert catalog(archive)['items'][0]['date_basis']=='ingested'
    now=datetime.now(timezone.utc);assert catalog(archive,start=now-timedelta(days=1),end=now)['matched_in_scan']==0
    assert catalog(archive,source='news:Fixture')['matched_in_scan']==1 and catalog(archive,source='news:Foreign')['matched_in_scan']==0

def test_social_actor_filter_is_exact_and_demo_never_leaks(archive):
    actor=add_actor(archive)['id'];other=add_actor(archive,name='Actor B',kind='comparator')['id']
    batch=PulseBatch(project_id=archive[2].id,provider='synthetic',sha256='fixture',created_by=archive[4][0].id,is_demo=False);archive[1].add(batch);archive[1].flush()
    d=PulseDocument(project_id=archive[2].id,batch_id=batch.id,network='facebook',external_id='fixture',url='https://example.org/fixture',title='Synthetic social',text='Agua del proyecto',published_at=datetime.now(timezone.utc)-timedelta(hours=1),collected_at=datetime.now(timezone.utc),is_demo=False);archive[1].add(d);archive[1].flush();archive[1].add(PulseMention(project_id=archive[2].id,document_id=d.id,actor_id=actor,is_demo=False));archive[1].commit()
    assert catalog(archive,actor_id=actor)['counts']==dict(news=0,social=1,document=0)
    assert catalog(archive,actor_id=other)['matched_in_scan']==0 and catalog(archive,network='press')['counts']['social']==0

def test_foreign_actor_source_and_document_selection_are_hidden(archive):
    foreign=add_actor(archive,pid=archive[3].id,actor=3)['id']
    with pytest.raises(HTTPException):catalog(archive,actor_id=foreign)
    for ref in [f'news:{archive[5][1].id}',f'document:{document(archive,pid=archive[3].id).id}']:
        with pytest.raises(HTTPException) as e:resolve(archive[1],archive[2].id,ref,(Path(archive[0].state.engine.url.database).parent/'uploads'))
        assert e.value.status_code==404

def test_bounded_candidates_and_document_text_limit_are_explicit(archive,monkeypatch):
    import app.explorer_service as svc
    document(archive,filename='one.txt');document(archive,filename='two.txt');monkeypatch.setattr(svc,'MAX_TEXT_DOCUMENTS',1)
    p=catalog(archive,kind='document');assert p['coverage']['bounded'] and p['coverage']['document_texts_attempted']==1 and p['coverage']['documents_metadata_only']==1

def test_pagination_and_counters_describe_scanned_matches(archive):
    for i in range(25):archive[1].add(NewsArticle(project_id=archive[2].id,title='Pieza '+str(i),url='https://example.org/'+str(i),url_hash='new'+str(i),publisher='Fixture',origin='csv'))
    archive[1].commit();a=catalog(archive);b=catalog(archive,offset=20)
    assert len(a['items'])==20 and a['has_more'] and len(b['items'])==6 and not b['has_more'] and a['matched_in_scan']==26
    assert not {e['reference'] for e in a['items']}.intersection(e['reference'] for e in b['items'])

def test_selection_is_reread_not_trusted_from_client_and_has_stable_hash(archive):
    ref=f'news:{archive[5][0].id}';p=selection(archive[1],archive[2].id,[ref],(Path(archive[0].state.engine.url.database).parent/'uploads'))
    assert p==selection(archive[1],archive[2].id,[ref],(Path(archive[0].state.engine.url.database).parent/'uploads')) and p['citations'][0]['excerpt']
    with pytest.raises(ValidationError):EvidenceSelection(references=[ref],citations=[{'excerpt':'forged'}])

def test_report_freezes_selected_sources_and_uses_existing_release_boundary(archive):
    ref=f'news:{archive[5][0].id}';r=save(archive,[ref]);row=archive[1].scalar(select(ReportVersion));payload=json.loads(row.payload)
    assert payload['mode']=='explorer_selection_v1' and payload['context']['citations'][0]['citation']==ref and hashlib.sha256(row.payload.encode()).hexdigest()==row.sha256
    read=endpoint(archive[0],'/api/projects/{pid}/reports/{report_id}')
    with pytest.raises(HTTPException):read(pid=archive[2].id,report_id=r['id'],user=archive[4][2],session=archive[1])
    endpoint(archive[0],'/api/projects/{pid}/reports/{report_id}/release','POST')(pid=archive[2].id,report_id=r['id'],body=ReleaseInput(expected_version=1),user=archive[4][0],session=archive[1])
    assert read(pid=archive[2].id,report_id=r['id'],user=archive[4][2],session=archive[1])['snapshot']['mode']=='explorer_selection_v1'

def test_changed_source_rejects_save_without_creating_report(archive):
    ref=f'news:{archive[5][0].id}';p=selection(archive[1],archive[2].id,[ref],(Path(archive[0].state.engine.url.database).parent/'uploads'));archive[5][0].abstract='Changed';archive[1].commit()
    with pytest.raises(HTTPException) as e:save(archive,[ref],preview=p)
    assert e.value.status_code==409 and archive[1].scalar(select(func.count()).select_from(Report))==0

@pytest.mark.parametrize('user',[2,3])
def test_reader_and_foreign_user_cannot_save(archive,user):
    with pytest.raises(HTTPException) as e:save(archive,[f'news:{archive[5][0].id}'],user=user)
    assert e.value.status_code in {403,404}

def test_selected_report_cannot_be_replaced_by_legacy_search_revision(archive):
    r=save(archive,[f'news:{archive[5][0].id}'])
    with pytest.raises(HTTPException) as e:endpoint(archive[0],'/api/projects/{pid}/reports/{report_id}/versions','POST')(pid=archive[2].id,report_id=r['id'],body=ReportRevision(title='Altered',question='agua',expected_version=1),user=archive[4][0],session=archive[1])
    assert e.value.status_code==409

def test_revoked_member_cannot_search_or_read_details(archive):
    m=archive[1].scalar(select(Membership).where(Membership.project_id==archive[2].id,Membership.user_id==archive[4][0].id));archive[1].delete(m);archive[1].commit()
    with pytest.raises(HTTPException) as e:endpoint(archive[0],'/api/projects/{pid}/explorer/items/{reference}')(pid=archive[2].id,reference=f'news:{archive[5][0].id}',user=archive[4][0],session=archive[1])
    assert e.value.status_code==404

@pytest.mark.parametrize('refs',[[],['news:1']*2,['news:1']*9,['../../private'],['news:-1'],['news:0']])
def test_selection_contract_rejects_duplicates_path_and_invalid_ids(refs):
    with pytest.raises(ValidationError):EvidenceSelection(references=refs)

def test_query_contract_future_dates_and_disabled_semantic_reader(monkeypatch):
    for fields in [dict(q='x'*121),dict(kind='secrets'),dict(offset=-1),dict(actor_id=True),dict(start=datetime.now(),end=datetime.now()),dict(start=datetime.now(timezone.utc),end=datetime.now(timezone.utc)+timedelta(days=1))]:
        with pytest.raises(ValidationError):ExplorerQuery(**fields)
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-unused')
    with pytest.raises(SemanticSearchUnavailable):DisabledSemanticEvidenceSearch().search()

def test_analyst_can_save_but_quota_blocks_more_reports(archive):
    ref=f'news:{archive[5][0].id}';save(archive,[ref],user=1)
    assert archive[1].scalar(select(Report.created_by))==archive[4][1].id
    quota=archive[1].scalar(select(UsageCounter).where(UsageCounter.project_id==archive[2].id,UsageCounter.action=='explorer.report'));quota.used=20;archive[1].commit()
    with pytest.raises(HTTPException) as e:save(archive,[ref])
    assert e.value.status_code==429 and archive[1].scalar(select(func.count()).select_from(Report))==1

def test_selected_source_report_survives_isolated_restore(archive,monkeypatch):
    from scripts import backup_local as backup
    ref=f'news:{archive[5][0].id}';save(archive,[ref]);private=Path(archive[0].state.engine.url.database).parent
    uploads=private/'uploads';uploads.mkdir(exist_ok=True);key=private/'fixture.key';key.write_text('fixture-only')
    raw,manifest=backup.make_archive(private,db_file=Path(archive[0].state.engine.url.database),uploads_directory=uploads,secret_file=key);monkeypatch.setattr(backup,'dpapi',lambda data,decrypt=False:data)
    file=private/'selection-fixture.nexobak';file.write_bytes(backup.MAGIC+raw);assert backup.restore_backup(file,private/'restore')['counts']==manifest['counts']
    with sqlite3.connect(private/'restore/storage/nexo.db') as c:
        raw,digest=c.execute('SELECT payload,sha256 FROM report_versions').fetchone();assert hashlib.sha256(raw.encode()).hexdigest()==digest and json.loads(raw)['context']['citations'][0]['citation']==ref

