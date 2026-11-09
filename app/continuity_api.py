"""Local, project-authorized aggregate continuity routes."""
from datetime import datetime,timezone
import json
from fastapi import Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .models import AuditEvent
from .pulse_models import PulseActor
from .actor_models import ActorProfile
from .continuity_models import AudienceSnapshot
from .continuity_port import AudienceBatch
from .continuity_service import overview
from .actors_api import lock_project
from .controls import take_quota

def install_continuity_api(app,db,current_user,allow):
    from .fidelity_api import install_fidelity_api
    install_fidelity_api(app,db,current_user,allow)
    @app.get('/api/projects/{pid}/continuity')
    def dashboard(pid:int,actor_id:int=0,network:str='all',account_url:str='',measurement:str='',start:datetime|None=None,end:datetime|None=None,
            user=Depends(current_user),session:Session=Depends(db)):
        _,member=allow(pid,user,session)
        return dict(**overview(session,pid,actor_id=actor_id,network=network,account_url=account_url,measurement=measurement,start=start,end=end),
            can_import=member.role in {'admin','editor','analyst'})

    @app.post('/api/projects/{pid}/continuity/captures')
    def ingest(pid:int,body:AudienceBatch,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'})
        if len(body.model_dump_json().encode())>1_000_000:raise HTTPException(422,'Máximo 1 MB por lote.')
        take_quota(session,pid,'continuity.import',20);lock_project(session,pid)
        ids={r.actor_id for r in body.items}
        actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.id.in_(ids),PulseActor.active.is_(True),PulseActor.is_demo.is_(False))).all()
        if {a.id for a in actors}!=ids:raise HTTPException(422,'Actor ajeno, archivado o de demostración.')
        profiles={p.actor_id:p for p in session.scalars(select(ActorProfile).where(ActorProfile.project_id==pid,ActorProfile.actor_id.in_(ids))).all()}
        now=datetime.now(timezone.utc);added=duplicates=0
        try:
            for item in body.items:
                profile=profiles.get(item.actor_id);refs=json.loads(profile.channels_json) if profile else []
                if not any(r['network']==item.network and r['url']==item.url and r.get('enabled',True) for r in refs):raise HTTPException(422,'Registra y activa esta cuenta en Actores.')
                if item.captured_at>now:raise HTTPException(422,'La captura no puede estar fechada en el futuro.')
                data=item.model_dump();identity={k:data[k] for k in ('actor_id','network','url','measurement_id','period_from','period_to','captured_at')}
                existing=session.scalar(select(AudienceSnapshot).filter_by(project_id=pid,provider=body.provider,**identity))
                if existing:
                    from .network_service import aware
                    if any((aware(getattr(existing,k)) if isinstance(v,datetime) else getattr(existing,k))!=v for k,v in data.items()):
                        raise HTTPException(409,'Ya existe un corte distinto con esa identidad. El historial se conserva.')
                    duplicates+=1;continue
                session.add(AudienceSnapshot(project_id=pid,provider=body.provider,created_by=user.id,is_demo=False,**data));session.flush();added+=1
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='continuity.import',target=f'new:{added}:duplicate:{duplicates}'))
            session.commit();return dict(inserted=added,duplicates=duplicates,external_calls=0)
        except (HTTPException,IntegrityError) as exc:
            session.rollback()
            if isinstance(exc,HTTPException):raise
            raise HTTPException(409,'El lote cambió durante la carga. Actualiza y reintenta.') from None
