"""Project XLSX evidence sidecars, reusing immutable original bytes and text retrieval."""
from pathlib import Path
import hashlib,json,re
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from .models import Dataset,DatasetBlob,AuditEvent
from .actors_api import lock_project
from .controls import take_quota
from .workbook_evidence import read_workbook,public_structure,prepare,WorkbookInvalid,MAX_FILE,CONTRACT

WRITERS={'admin','editor','analyst'}
class WorkbookSelection(BaseModel):
 model_config=ConfigDict(extra='forbid')
 sheet:str=Field(min_length=1,max_length=80)
 columns:list[str]=Field(min_length=1,max_length=30)
 header_row:int=Field(default=1,ge=1,le=4999)
 first_row:int=Field(default=2,ge=2,le=5000)
 last_row:int=Field(default=5000,ge=2,le=5000)
 source_year:int|None=Field(default=None,ge=1900,le=2100)
 source_note:str=Field(default='',max_length=400)

class WorkbookExtract(WorkbookSelection):
 preview_sha256:str=Field(pattern=r'^[a-f0-9]{64}$')

def source_bytes(session,pid,did,uploads):
 row=session.scalar(select(Dataset).where(Dataset.id==did,Dataset.project_id==pid))
 if not row or Path(row.filename).suffix.lower()!='.xlsx':raise HTTPException(404,'Libro no disponible.')
 if row.size_bytes>MAX_FILE:raise HTTPException(422,'La extracción admite libros de hasta 2 MB.')
 if row.path=='database':
  blob=session.scalar(select(DatasetBlob).where(DatasetBlob.dataset_id==did,DatasetBlob.project_id==pid));raw=bytes(blob.content) if blob else b''
 else:
  path=Path(row.path).resolve();allowed=(Path(uploads)/str(pid)).resolve()
  if not path.is_relative_to(allowed):raise HTTPException(409,'El archivo necesita revisión de almacenamiento.')
  try:
   with path.open('rb') as f:raw=f.read(MAX_FILE+1)
  except OSError:raise HTTPException(409,'El original no está disponible.') from None
 if len(raw)!=row.size_bytes or len(raw)>MAX_FILE or hashlib.sha256(raw).hexdigest()!=row.sha256:
  raise HTTPException(409,'La integridad del original necesita revisión.')
 return row,raw

def build(session,pid,did,uploads,body):
 row,raw=source_bytes(session,pid,did,uploads)
 if any(not re.fullmatch('[A-Z]{1,2}',c) for c in body.columns):raise HTTPException(422,'Usa letras de columna válidas.')
 try:result=prepare(raw,row.filename,body)
 except WorkbookInvalid as e:raise HTTPException(422,str(e)) from None
 return row,result

def extract(session,pid,did,uploads,body,user_id):
 lock_project(session,pid);source,packet=build(session,pid,did,uploads,body)
 if packet['preview_sha256']!=body.preview_sha256:raise HTTPException(409,'La selección cambió. Revisa de nuevo la vista previa.')
 raw=packet['text'].encode();sha=hashlib.sha256(raw).hexdigest()
 existing=session.scalar(select(Dataset).where(Dataset.project_id==pid,Dataset.sha256==sha))
 if existing:return dict(dataset_id=existing.id,deduplicated=True,rows=packet['metadata']['row_count'],external_calls=0)
 used=session.scalar(select(func.coalesce(func.sum(Dataset.size_bytes),0)).where(Dataset.project_id==pid))
 if used+len(raw)>250*1024*1024:raise HTTPException(429,'Almacenamiento del proyecto: máximo 250 MB.')
 filename=(Path(source.filename).stem[:80]+' - '+packet['metadata']['sheet'][:35]+' - evidencia.md')
 detail=CONTRACT+'\n'+json.dumps(dict(**packet['metadata'],source_dataset_id=source.id,preview_sha256=packet['preview_sha256']),ensure_ascii=False,sort_keys=True)
 item=Dataset(project_id=pid,uploaded_by=user_id,filename=filename,media_type='.md',sha256=sha,size_bytes=len(raw),status='validated',record_count=packet['metadata']['row_count'],detail=detail,path='database')
 session.add(item);session.flush();session.add(DatasetBlob(dataset_id=item.id,project_id=pid,content=raw))
 session.add(AuditEvent(project_id=pid,user_id=user_id,action='library.xlsx.extract',target=f'source:{source.id}:text:{item.id}'))
 session.commit();return dict(dataset_id=item.id,deduplicated=False,rows=item.record_count,external_calls=0)

def install_workbook_api(app,db,current_user,allow,uploads):
 @app.get('/api/projects/{pid}/library/workbooks')
 def listing(pid:int,user=Depends(current_user),session:Session=Depends(db)):
  _,member=allow(pid,user,session)
  rows=session.scalars(select(Dataset).where(Dataset.project_id==pid,func.lower(Dataset.filename).like('%.xlsx')).order_by(Dataset.id.desc()).limit(101)).all()
  return dict(items=[dict(id=r.id,filename=r.filename,sha256=r.sha256) for r in rows[:100] if Path(r.filename).suffix.lower()=='.xlsx'],can_extract=member.role in WRITERS,bounded=len(rows)>100)
 @app.get('/api/projects/{pid}/library/workbooks/{dataset_id}')
 def inspect(pid:int,dataset_id:int,user=Depends(current_user),session:Session=Depends(db)):
  allow(pid,user,session);row,raw=source_bytes(session,pid,dataset_id,uploads)
  try:sheets=public_structure(read_workbook(raw))
  except WorkbookInvalid as e:raise HTTPException(422,str(e)) from None
  return dict(dataset_id=row.id,filename=row.filename,sha256=row.sha256,sheets=sheets,external_calls=0)
 @app.post('/api/projects/{pid}/library/workbooks/{dataset_id}/preview')
 def preview(pid:int,dataset_id:int,body:WorkbookSelection,user=Depends(current_user),session:Session=Depends(db)):
  allow(pid,user,session);_,packet=build(session,pid,dataset_id,uploads,body)
  return {k:packet[k] for k in ('metadata','preview_sha256','preview')}
 @app.post('/api/projects/{pid}/library/workbooks/{dataset_id}/extract')
 def save(pid:int,dataset_id:int,body:WorkbookExtract,user=Depends(current_user),session:Session=Depends(db)):
  allow(pid,user,session,roles=WRITERS);take_quota(session,pid,'library.xlsx.extract',20)
  try:return extract(session,pid,dataset_id,uploads,body,user.id)
  except Exception:session.rollback();raise

def annotate_context(session,pid,packet,uploads):
 """Enrich the old retrieval packet without changing the protected retrieval module."""
 from .knowledge import document_bytes
 sidecars=session.scalars(select(Dataset).where(Dataset.project_id==pid,Dataset.detail.like(CONTRACT+'\n%')).order_by(Dataset.id.desc()).limit(100)).all()
 references={};available=[]
 for item in sidecars:
  try:
   meta=json.loads(item.detail.split('\n',1)[1]);source=session.scalar(select(Dataset).where(Dataset.id==meta['source_dataset_id'],Dataset.project_id==pid))
   if not source or source.sha256!=meta['source_sha256'] or item.sha256!=meta['text_sha256']:continue
   source_bytes(session,pid,source.id,uploads)
   raw,error=document_bytes(session,item,uploads)
   if error:continue
   references[item.id]=(source,meta)
   available.append(dict(source_dataset_id=source.id,text_dataset_id=item.id,sheet=meta['sheet'],columns=meta['columns'],rows=meta['row_count']))
  except (ValueError,KeyError,TypeError,IndexError,HTTPException):continue
 for citation in packet['citations']:
  match=references.get(citation.get('dataset_id'))
  if match:
   original,meta=match
   citation['source']=f"{original.filename} · {meta['sheet']} · filas {meta['first_row']}–{meta['last_row']}"
   citation['workbook_origin']=dict(filename=original.filename,sha256=original.sha256,source_dataset_id=original.id,
    sheet=meta['sheet'],columns=meta['columns'],source_year_declared=meta['source_year'],source_note_declared=meta['source_note'])
 ids={r['source_dataset_id'] for r in available}
 for skipped in packet['coverage']['not_indexed']:
  if skipped['dataset_id'] in ids:skipped['reason']='original_preserved_selected_columns_available'
 packet['coverage']['workbook_extractions']=available
 return packet
