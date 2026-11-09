"""Local project alert evaluation and versioned operational review. No delivery."""
from datetime import datetime
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field,AwareDatetime
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .apify_port import Strict,Network
from .models import AuditEvent
from .alert_models import AlertIncident,AlertEvent
from .alert_service import overview,preview,detail,latest,evidence,TRANSITIONS
from .actors_api import lock_project
from .controls import take_quota

class AlertCut(Strict):
    start:AwareDatetime
    end:AwareDatetime
    actor_id:int=Field(default=0,strict=True,ge=0)
    network:Literal['all','press','facebook','instagram','x','tiktok','youtube','other']='all'
class AlertReview(Strict):
    expected_version:int=Field(strict=True,ge=0,le=999)
    status:Literal['open','acknowledged','resolved','dismissed']
    note:str=Field(default='',max_length=1000)

def install_alert_api(app,db,current_user,allow):
    @app.get('/api/projects/{pid}/alerts')
    def dashboard(pid:int,actor_id:int=0,network:str='all',state:str='all',start:datetime|None=None,end:datetime|None=None,
            user=Depends(current_user),session:Session=Depends(db)):
        _,member=allow(pid,user,session)
        return dict(**overview(session,pid,actor_id=actor_id,network=network,state=state,start=start,end=end),
            can_review=member.role in {'admin','editor','analyst'},can_manage_rules=member.role in {'admin','editor'})
    @app.get('/api/projects/{pid}/alerts/{alert_id}')
    def read(pid:int,alert_id:int,user=Depends(current_user),session:Session=Depends(db)):
        _,member=allow(pid,user,session)
        return dict(**detail(session,pid,alert_id),can_review=member.role in {'admin','editor','analyst'})
    @app.post('/api/projects/{pid}/alerts/evaluate')
    def evaluate(pid:int,body:AlertCut,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'})
        take_quota(session,pid,'alerts.evaluate',48);lock_project(session,pid)
        packet=preview(session,pid,**body.model_dump());start=datetime.fromisoformat(packet['window']['start']);end=datetime.fromisoformat(packet['window']['end'])
        inserted=duplicates=0
        try:
            for reading in packet['readings']:
                if reading['status']!='triggered':continue
                existing=session.scalar(select(AlertIncident.id).where(AlertIncident.project_id==pid,AlertIncident.rule_id==reading['id'],
                    AlertIncident.network==body.network,AlertIncident.period_from==start,AlertIncident.period_to==end))
                if existing:duplicates+=1;continue
                if session.scalar(select(func.count()).select_from(AlertIncident).where(AlertIncident.project_id==pid))>=10000:raise HTTPException(409,'Revisa la conservación del proyecto antes de registrar más incidentes.')
                raw,digest=evidence(session,pid,reading,start,end,body.network)
                session.add(AlertIncident(project_id=pid,rule_id=reading['id'],actor_id=reading['actor_id'],is_demo=False,network=body.network,
                    period_from=start,period_to=end,snapshot_json=raw,snapshot_sha256=digest,created_by=user.id));session.flush();inserted+=1
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='alerts.evaluate',target=f'new:{inserted}:duplicate:{duplicates}'))
            session.commit();return dict(inserted=inserted,duplicates=duplicates,evaluable=sum(r['status'] in {'triggered','clear'} for r in packet['readings']),external_calls=0)
        except (HTTPException,IntegrityError) as exc:
            session.rollback()
            if isinstance(exc,HTTPException):raise
            raise HTTPException(409,'El corte se registró en paralelo. Actualiza antes de reintentar.') from None
    @app.post('/api/projects/{pid}/alerts/{alert_id}/reviews')
    def review(pid:int,alert_id:int,body:AlertReview,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'})
        take_quota(session,pid,'alerts.review',100);lock_project(session,pid)
        incident=session.scalar(select(AlertIncident).where(AlertIncident.project_id==pid,AlertIncident.id==alert_id))
        if not incident:raise HTTPException(404,'Incidente no disponible.')
        last=latest(session,pid,alert_id);version=last.version if last else 0;state=last.status if last else 'open'
        if body.expected_version!=version:raise HTTPException(409,'Otra persona actualizó el incidente. Recarga para ver el estado actual.')
        if body.status not in TRANSITIONS[state]:raise HTTPException(422,'Elige una transición válida para el estado actual.')
        note=body.note.strip()
        if body.status in {'resolved','dismissed','open'} and len(note)<3:raise HTTPException(422,'Escribe el motivo de cierre, descarte o reapertura.')
        try:
            session.add(AlertEvent(project_id=pid,alert_id=alert_id,version=version+1,previous_status=state,status=body.status,note=note,created_by=user.id))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='alerts.review',target=f'{alert_id}:v{version+1}:{body.status}'))
            session.commit();return detail(session,pid,alert_id)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'El estado cambió en paralelo. Recarga antes de reintentar.') from None
