"""Local-only imports; NEXO identity and project boundaries remain in charge."""
from datetime import datetime,timezone
from fastapi import Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .fidelity import FidelityCapture,AtalayaPublicationBatch,activity,context,fingerprint
from .client_access import is_owner
from .models import AuditEvent
from .controls import take_quota
from .actors_api import lock_project

def install_fidelity_api(app,db,current_user,allow):
    from .fidelity_team_api import install_team_api
    install_team_api(app,db,current_user,allow)
    engine=getattr(app.state,'engine',None)
    if engine is not None and engine.dialect.name=='sqlite':FidelityCapture.__table__.create(bind=engine,checkfirst=True)

    @app.get('/api/projects/{pid}/continuity/activity')
    def dashboard(pid:int,actor_id:int=0,network:str='all',account_url:str='',start:datetime|None=None,end:datetime|None=None,
                  user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        return dict(**activity(session,pid,actor_id=actor_id,network=network,account_url=account_url,start=start,end=end),can_import=is_owner(session,user))

    @app.post('/api/projects/{pid}/continuity/atalaya/import')
    def ingest(pid:int,body:AtalayaPublicationBatch,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        if not is_owner(session,user):raise HTTPException(403,'Solo el superadministrador puede incorporar publicaciones.')
        raw,digest=fingerprint(body)
        if len(raw.encode())>1_000_000:raise HTTPException(422,'Máximo 1 MB de datos normalizados.')
        if body.captured_at>datetime.now(timezone.utc):raise HTTPException(422,'La captura no puede estar en el futuro.')
        _,refs=context(session,pid,body.actor_id,body.network,body.account_url)
        if not refs:raise HTTPException(422,'Registra y activa esta cuenta en Actores.')
        take_quota(session,pid,'fidelity.import',20);lock_project(session,pid)
        try:
            existing=session.scalar(select(FidelityCapture).where(FidelityCapture.project_id==pid,FidelityCapture.actor_id==body.actor_id,
                FidelityCapture.network==body.network,FidelityCapture.account_url==body.account_url,FidelityCapture.captured_at==body.captured_at))
            if existing:
                if existing.sha256!=digest:raise HTTPException(409,'Ya existe otra captura con esa fecha. Se conserva el historial.')
                session.rollback();return dict(inserted=0,duplicates=1,external_calls=0)
            session.add(FidelityCapture(project_id=pid,actor_id=body.actor_id,network=body.network,account_url=body.account_url,
                captured_at=body.captured_at,payload_json=raw,sha256=digest,source_kind='atalaya_import',created_by=user.id,is_demo=False))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='fidelity.import',target='publications:'+str(len(body.publications))))
            session.commit();return dict(inserted=1,duplicates=0,publications=len(body.publications),external_calls=0)
        except (HTTPException,IntegrityError) as exc:
            session.rollback()
            if isinstance(exc,HTTPException):raise
            raise HTTPException(409,'La captura cambió durante la carga. Actualiza y reintenta.') from None
