"""Project account dashboard and atomic offline snapshot ingestion."""
from datetime import datetime,timezone
import json
from fastapi import Depends,HTTPException,Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .models import AuditEvent
from .pulse_models import PulseActor,PulseAccount
from .actor_models import ActorProfile
from .network_port import AccountCaptureBatch
from .network_service import overview,aware,COUNTERS
from .actors_api import lock_project
from .controls import take_quota

def install_network_api(app,db,current_user,allow):
    @app.get('/api/projects/{pid}/networks')
    def dashboard(pid:int,actor_id:int=0,network:str='all',account_url:str='',start:datetime|None=None,end:datetime|None=None,
            user=Depends(current_user),session:Session=Depends(db)):
        _,member=allow(pid,user,session)
        return dict(**overview(session,pid,actor_id=actor_id,network=network,account_url=account_url,start=start,end=end),
            can_import=member.role in {'admin','editor','analyst'})

    @app.post('/api/projects/{pid}/networks/captures')
    def ingest(pid:int,body:AccountCaptureBatch,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'})
        if len(body.model_dump_json().encode())>1_000_000:raise HTTPException(422,'Máximo 1 MB por lote.')
        take_quota(session,pid,'networks.import',20);lock_project(session,pid)
        ids={r.actor_id for r in body.items}
        actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.id.in_(ids),
            PulseActor.active.is_(True),PulseActor.is_demo.is_(False))).all()
        profiles={p.actor_id:p for p in session.scalars(select(ActorProfile).where(ActorProfile.project_id==pid,ActorProfile.actor_id.in_(ids))).all()}
        if {a.id for a in actors}!=ids:raise HTTPException(422,'Una cuenta hace referencia a un actor ajeno, archivado o de demostración.')
        now=datetime.now(timezone.utc);added=duplicates=0
        try:
            for item in body.items:
                profile=profiles.get(item.actor_id);refs=json.loads(profile.channels_json) if profile else []
                if not any(r['network']==item.network and r['url']==item.url and r.get('enabled',True) for r in refs):
                    raise HTTPException(422,'Registra y activa esta referencia pública en Actores antes de cargar sus capturas.')
                if item.captured_at>now:raise HTTPException(422,'La captura no puede estar fechada en el futuro.')
                values=item.model_dump(mode='json',exclude={'actor_id','network','url','captured_at'});values['provider']=body.provider
                existing=session.scalar(select(PulseAccount).where(PulseAccount.project_id==pid,PulseAccount.actor_id==item.actor_id,
                    PulseAccount.network==item.network,PulseAccount.url==item.url,PulseAccount.captured_at==item.captured_at,PulseAccount.is_demo.is_(False)))
                if existing:
                    if json.loads(existing.metrics)!=values:raise HTTPException(409,'Ya existe una captura distinta con esa cuenta y fecha. El historial no se sobrescribe.')
                    duplicates+=1;continue
                session.add(PulseAccount(project_id=pid,actor_id=item.actor_id,network=item.network,url=item.url,captured_at=item.captured_at,
                    metrics=json.dumps(values,ensure_ascii=False,sort_keys=True),created_by=user.id,is_demo=False));session.flush();added+=1
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='networks.import',target=f'new:{added}:duplicate:{duplicates}'))
            session.commit();return dict(inserted=added,duplicates=duplicates,external_calls=0)
        except (HTTPException,IntegrityError) as exc:
            session.rollback()
            if isinstance(exc,HTTPException):raise
            raise HTTPException(409,'El lote cambió durante la carga. Actualiza antes de reintentarlo.') from None
