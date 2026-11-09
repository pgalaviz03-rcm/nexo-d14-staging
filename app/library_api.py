"""Project document catalogue, automatic PDF preparation and page-scoped reading."""
from pathlib import Path
import hashlib,json
from fastapi import Depends,HTTPException,UploadFile,File
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from .models import Dataset,DatasetBlob,AuditEvent
from .knowledge import document_bytes
from .workbook_evidence import CONTRACT as XLSX_CONTRACT
from .actors_api import lock_project
from .controls import take_quota
from .pdf_evidence import CONTRACT,MAX_FILE,extract_pdf,PdfInvalid

WRITERS={'admin','editor','analyst'}

def original_bytes(session,pid,did,uploads):
    row=session.scalar(select(Dataset).where(Dataset.project_id==pid,Dataset.id==did))
    if not row:raise HTTPException(404,'Documento no disponible en este proyecto.')
    if row.size_bytes>MAX_FILE:raise HTTPException(422,'El archivo supera 12 MB.')
    if row.path=='database':
        blob=session.scalar(select(DatasetBlob).where(DatasetBlob.project_id==pid,DatasetBlob.dataset_id==did))
        raw=bytes(blob.content) if blob else b''
    else:
        path=Path(row.path).resolve();allowed=(Path(uploads)/str(pid)).resolve()
        if not path.is_relative_to(allowed):raise HTTPException(409,'El almacenamiento del archivo necesita revisión.')
        try:
            with path.open('rb') as f:raw=f.read(MAX_FILE+1)
        except OSError:raise HTTPException(409,'El original no está disponible.') from None
    if len(raw)!=row.size_bytes or len(raw)>MAX_FILE or hashlib.sha256(raw).hexdigest()!=row.sha256:
        raise HTTPException(409,'La integridad del documento necesita revisión.')
    return row,raw

def pdf_packet(session,pid,source,uploads):
    """Validated cache only; both blobs stay inside the authorized project."""
    try:original_bytes(session,pid,source.id,uploads)
    except HTTPException:return None
    rows=session.scalars(select(Dataset).where(Dataset.project_id==pid,Dataset.detail.startswith(CONTRACT+'\n')).order_by(Dataset.id.desc()).limit(500)).all()
    for row in rows:
        try:
            meta=json.loads(row.detail.split('\n',1)[1])
            if meta['source_dataset_id']!=source.id or meta['source_sha256']!=source.sha256:continue
            raw,error=document_bytes(session,row,uploads)
            if error:return None
            packet=json.loads(raw)
            if packet['contract']!=CONTRACT or packet['page_count']!=len(packet['pages']) or not 1<=packet['page_count']<=160:return None
            if any(p['number']!=i or not isinstance(p['text'],str) for i,p in enumerate(packet['pages'],1)):return None
            return dict(packet,text_dataset_id=row.id,text_sha256=row.sha256)
        except (ValueError,KeyError,TypeError,IndexError):continue
    return None

def prepare_pdf(session,pid,did,uploads,user_id):
    source,raw=original_bytes(session,pid,did,uploads)
    if Path(source.filename).suffix.lower()!='.pdf':raise HTTPException(422,'Elige un documento PDF.')
    existing=pdf_packet(session,pid,source,uploads)
    if existing:return dict(dataset_id=did,deduplicated=True,page_count=existing['page_count'],searchable=existing['text_chars']>0)
    try:packet=extract_pdf(raw,Path(uploads)/'.pdf-temporary')
    except PdfInvalid as exc:raise HTTPException(422,str(exc)) from None
    encoded=json.dumps(packet,ensure_ascii=False,sort_keys=True).encode('utf-8')
    lock_project(session,pid)
    # Concurrent preparations converge on one cache after the project lock.
    existing=pdf_packet(session,pid,source,uploads)
    if existing:return dict(dataset_id=did,deduplicated=True,page_count=existing['page_count'],searchable=existing['text_chars']>0)
    used=session.scalar(select(func.coalesce(func.sum(Dataset.size_bytes),0)).where(Dataset.project_id==pid))
    if used+len(encoded)>250*1024*1024:raise HTTPException(429,'El proyecto alcanzó su límite de almacenamiento de 250 MB.')
    detail=CONTRACT+'\n'+json.dumps(dict(source_dataset_id=did,source_sha256=source.sha256),sort_keys=True)
    row=Dataset(project_id=pid,uploaded_by=user_id,filename=Path(source.filename).stem[:150]+' - páginas.json',
        media_type='.json',sha256=hashlib.sha256(encoded).hexdigest(),size_bytes=len(encoded),status='validated',
        record_count=packet['page_count'],detail=detail,path='database')
    session.add(row);session.flush();session.add(DatasetBlob(project_id=pid,dataset_id=row.id,content=encoded))
    session.add(AuditEvent(project_id=pid,user_id=user_id,action='library.pdf.prepare',target=f'source:{did}:text:{row.id}:pages:{packet["page_count"]}'))
    session.commit()
    return dict(dataset_id=did,deduplicated=False,page_count=packet['page_count'],searchable=packet['text_chars']>0)

def catalogue(session,pid,uploads):
    rows=session.scalars(select(Dataset).where(Dataset.project_id==pid).order_by(Dataset.id.desc()).limit(501)).all()
    extracts={}
    for row in rows:
        if row.detail.startswith(XLSX_CONTRACT+'\n'):
            try:extracts[json.loads(row.detail.split('\n',1)[1])['source_dataset_id']]=row.id
            except (ValueError,KeyError,IndexError):pass
    items=[]
    for row in rows[:500]:
        if row.detail.startswith((CONTRACT+'\n',XLSX_CONTRACT+'\n')):continue
        ext=Path(row.filename).suffix.lower();packet=pdf_packet(session,pid,row,uploads) if ext=='.pdf' else None
        state='ready' if ext in {'.txt','.md','.csv'} or row.id in extracts else 'stored'
        if ext=='.pdf':state=('partial' if packet['empty_pages'] else 'ready') if packet and packet['text_chars'] else 'needs_ocr' if packet else 'needs_prepare'
        items.append(dict(id=row.id,filename=row.filename,size_bytes=row.size_bytes,format=ext.lstrip('.').upper(),state=state,
            searchable=state in {'ready','partial'},pages=packet['page_count'] if packet else None,
            empty_pages=packet['empty_pages'] if packet else [],selection_dataset_id=extracts.get(row.id)))
    return dict(items=items,bounded=len(rows)>500)

def install_library_api(app,db,current_user,allow,uploads):
    original_upload=next((r.endpoint for r in app.routes if getattr(r,'path',None)=='/api/projects/{pid}/datasets' and 'POST' in r.methods),None)
    @app.get('/api/projects/{pid}/library/documents')
    def listing(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        _,member=allow(pid,user,session)
        return dict(**catalogue(session,pid,uploads),can_prepare=member.role in WRITERS,external_calls=0)

    @app.post('/api/projects/{pid}/library/documents/{dataset_id}/prepare')
    def prepare(pid:int,dataset_id:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=WRITERS);take_quota(session,pid,'library.pdf.prepare',20)
        return prepare_pdf(session,pid,dataset_id,uploads,user.id)

    @app.get('/api/projects/{pid}/library/documents/{dataset_id}/pages/{page_number}')
    def page(pid:int,dataset_id:int,page_number:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session);source,_=original_bytes(session,pid,dataset_id,uploads)
        if Path(source.filename).suffix.lower()!='.pdf':raise HTTPException(404,'Página no disponible.')
        packet=pdf_packet(session,pid,source,uploads)
        if not packet:raise HTTPException(409,'Prepara el documento para leer sus páginas.')
        if not 1<=page_number<=packet['page_count']:raise HTTPException(404,'Página no disponible.')
        return dict(dataset_id=dataset_id,filename=source.filename,page=page_number,pages=packet['page_count'],
            text=packet['pages'][page_number-1]['text'],external_calls=0)

    @app.post('/api/projects/{pid}/library/upload')
    async def upload(pid:int,file:UploadFile=File(...),user=Depends(current_user),session:Session=Depends(db)):
        if original_upload is None:raise HTTPException(503,'La carga de archivos no está instalada en este servidor.')
        result=await original_upload(pid=pid,file=file,user=user,session=session)
        if Path(result['filename']).suffix.lower()=='.pdf':
            from starlette.concurrency import run_in_threadpool
            try:
                result['preparation']=await run_in_threadpool(prepare_pdf,session,pid,result['id'],uploads,user.id)
                result['detail']='Documento listo para buscar por palabras y consultar por página.' if result['preparation']['searchable'] else 'Este PDF necesita reconocimiento de texto (OCR).'
            except HTTPException as exc:
                session.rollback();result['preparation_error']=exc.detail
                result['detail']='Archivo guardado. '+str(exc.detail)
        return result
