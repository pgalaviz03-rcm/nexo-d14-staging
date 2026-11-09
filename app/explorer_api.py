"""Authorized local archive, citation selection and frozen documentary reports."""
from datetime import datetime,timezone
import json,hashlib
from fastapi import Depends,HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
from .explorer_port import ExplorerQuery,EvidenceSelection,ExplorerReport
from .explorer_service import search,resolve,public_entry,selection
from .models import Report,ReportVersion,AuditEvent
from .report_api import WRITERS,MAX_PAYLOAD_BYTES
from .actors_api import lock_project
from .controls import take_quota

def install_explorer_api(app,db,current_user,allow,uploads):
    @app.get('/api/projects/{pid}/explorer')
    def archive(pid:int,q:str='',kind:str='all',network:str='all',actor_id:int=0,source:str='',start:datetime|None=None,end:datetime|None=None,offset:int=0,
            user=Depends(current_user),session:Session=Depends(db)):
        _,member=allow(pid,user,session)
        try:query=ExplorerQuery(q=q,kind=kind,network=network,actor_id=actor_id,source=source,start=start,end=end,offset=offset)
        except ValidationError:raise HTTPException(422,'Revisa la búsqueda, los filtros y las fechas.') from None
        return dict(**search(session,pid,query,uploads),can_save_report=member.role in WRITERS)
    @app.get('/api/projects/{pid}/explorer/items/{reference}')
    def item(pid:int,reference:str,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        try:EvidenceSelection(references=[reference])
        except ValidationError:raise HTTPException(404,'Fuente no disponible.') from None
        return dict(project_id=pid,**public_entry(resolve(session,pid,reference,uploads),limit=4000),external_calls=0)
    @app.post('/api/projects/{pid}/explorer/selection')
    def prepare(pid:int,body:EvidenceSelection,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        return selection(session,pid,body.references,uploads)
    @app.post('/api/projects/{pid}/explorer/reports')
    def save(pid:int,body:ExplorerReport,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=WRITERS);take_quota(session,pid,'explorer.report',20);lock_project(session,pid)
        title=' '.join(body.title.split())
        if len(title)<3 or any(ord(c)<32 or ord(c)==127 for c in title) or '\x00' in body.note:raise HTTPException(422,'Revisa el título y la nota.')
        packet=selection(session,pid,body.references,uploads)
        if packet['preview_sha256']!=body.preview_sha256:raise HTTPException(409,'Las fuentes cambiaron. Prepara otra vez la selección antes de guardar; tu nota se conserva.')
        payload=dict(mode='explorer_selection_v1',title=title,editorial_note=body.note.strip(),
            context=dict(project_id=pid,question='Selección de evidencias del proyecto',citations=packet['citations'],coverage=dict(bounded=False,not_indexed=[])),
            filters=dict(source_kind='all',days=0,limit=len(body.references)),selection_sha256=packet['preview_sha256'],prepared_at=datetime.now(timezone.utc).isoformat(),
            scope='Selección explícita de fuentes del proyecto; extractos conservados para revisión.',ai_used=False,external_calls=0)
        raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        try:encoded=raw.encode()
        except UnicodeError:raise HTTPException(422,'El informe contiene texto no admitido.') from None
        if len(encoded)>MAX_PAYLOAD_BYTES:raise HTTPException(422,'La selección supera el tamaño permitido.')
        digest=hashlib.sha256(encoded).hexdigest();row=Report(project_id=pid,created_by=user.id,current_version=1)
        session.add(row);session.flush();session.add(ReportVersion(project_id=pid,report_id=row.id,version=1,payload=raw,sha256=digest,created_by=user.id))
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='explorer.report',target=f'{row.id}:sources:{len(body.references)}'))
        session.commit();return dict(id=row.id,version=1,sha256=digest,published=False)
