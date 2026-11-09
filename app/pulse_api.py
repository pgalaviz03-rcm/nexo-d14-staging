"""Local PULSO API. Membership, strict contracts and no provider calls."""
from datetime import datetime,timezone
import hashlib,json
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import Field,AwareDatetime,model_validator
from sqlalchemy import select,update,func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .apify_port import Strict,Network,Sentiment,Emotion,ImportBatch,ConnectorPlan,DisabledApifyReader,ApifyUnavailable,public_url
from .pulse_models import PulseConfig,PulseActor,PulseBatch,PulseDocument,PulseMention,PulseAccount,PulseRule
from .models import AuditEvent
from .pulse_service import overview,utc

WRITERS={'admin','editor','analyst'}
MANAGERS={'admin','editor'}


class ConfigInput(Strict):
    territory:str=Field(default='',max_length=160)
    min_classified:int=Field(default=20,ge=3,le=1000)
    expected_version:int=Field(default=0,ge=0)
    connector:ConnectorPlan=Field(default_factory=ConnectorPlan)


class ActorInput(Strict):
    name:str=Field(min_length=2,max_length=120)
    kind:Literal['primary','comparator']='comparator'


class ActorUpdate(ActorInput):
    active:bool=True
    expected_version:int=Field(ge=1)


class Classification(Strict):
    sentiment:Sentiment|None=None
    emotion:Emotion|None=None
    expected_version:int=Field(ge=0)


class AccountInput(Strict):
    actor_id:int=Field(ge=1)
    network:Network
    url:str=Field(max_length=2000)
    captured_at:AwareDatetime
    metrics_from:AwareDatetime|None=None
    metrics_to:AwareDatetime|None=None
    followers:int|None=Field(default=None,ge=0,le=9007199254740991,strict=True)
    posts:int|None=Field(default=None,ge=0,le=9007199254740991,strict=True)
    views:int|None=Field(default=None,ge=0,le=9007199254740991,strict=True)
    impressions:int|None=Field(default=None,ge=0,le=9007199254740991,strict=True)
    reach:int|None=Field(default=None,ge=0,le=9007199254740991,strict=True)
    interactions:int|None=Field(default=None,ge=0,le=9007199254740991,strict=True)

    @model_validator(mode='after')
    def metric_period(self):
        if (self.metrics_from is None)!=(self.metrics_to is None):raise ValueError('Indica ambas fechas del periodo de métricas o ninguna.')
        if self.metrics_from and self.metrics_to<=self.metrics_from:raise ValueError('El periodo de métricas debe avanzar en el tiempo.')
        return self


class RuleInput(Strict):
    actor_id:int=Field(ge=1)
    name:str=Field(min_length=2,max_length=100)
    metric:Literal['mentions','negative_share','mention_spike']
    threshold:int=Field(ge=1,le=1000000)
    min_mentions:int=Field(default=20,ge=1,le=10000)


class RuleState(Strict):
    active:bool


def actor_record(a):return dict(id=a.id,name=a.name,kind=a.kind,active=a.active,is_demo=a.is_demo,version=a.version)


def import_posts(session,pid,body,user_id,*,demo=False):
    raw=body.model_dump_json()
    if len(raw.encode())>2_000_000:raise HTTPException(422,'Máximo 2 MB por lote.')
    ids={actor for item in body.items for actor in item.actor_ids}
    actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.id.in_(ids),
        PulseActor.is_demo==demo,PulseActor.active.is_(True))).all()
    if {a.id for a in actors}!=ids:raise HTTPException(422,'Un actor no pertenece al proyecto, está archivado o es de otro modo de datos.')
    batch=PulseBatch(project_id=pid,provider=body.provider,dataset_ref=body.dataset_ref,
        sha256=hashlib.sha256(raw.encode()).hexdigest(),is_demo=demo,created_by=user_id)
    inserted=duplicates=0
    try:
        session.add(batch);session.flush()
        for item in body.items:
            row=session.scalar(select(PulseDocument).where(PulseDocument.project_id==pid,
                PulseDocument.network==item.network,PulseDocument.external_id==item.external_id,PulseDocument.is_demo==demo))
            if row:
                duplicates+=1
                old=row.collected_at.replace(tzinfo=timezone.utc) if row.collected_at.tzinfo is None else row.collected_at
                if utc(item.collected_at)>old:
                    row.collected_at=utc(item.collected_at)
                    if item.views is not None:row.views=item.views
                    if item.interactions is not None:row.interactions=item.interactions
            else:
                row=PulseDocument(project_id=pid,batch_id=batch.id,network=item.network,external_id=item.external_id,
                    url=public_url(item.url),title=item.title,text=item.text,published_at=utc(item.published_at),
                    collected_at=utc(item.collected_at),views=item.views,interactions=item.interactions,is_demo=demo)
                session.add(row);session.flush();inserted+=1
            for actor in item.actor_ids:
                if session.get(PulseMention,(row.id,actor)) is None:
                    session.add(PulseMention(project_id=pid,document_id=row.id,actor_id=actor,is_demo=demo,method='unclassified'))
        session.add(AuditEvent(project_id=pid,user_id=user_id,action='pulse.import',target=f'{batch.id}:new:{inserted}:seen:{duplicates}'))
        session.commit();return dict(batch_id=batch.id,inserted=inserted,duplicates=duplicates,external_calls=0)
    except IntegrityError:
        session.rollback();raise HTTPException(409,'El lote cambió o contiene referencias incompatibles. Recarga antes de reintentar.') from None


def install_pulse_api(app,db,current_user,allow):
    @app.get('/api/projects/{pid}/pulse/config')
    def get_config(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        project,member=allow(pid,user,session)
        config=session.get(PulseConfig,pid)
        actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid).order_by(PulseActor.id).limit(100)).all()
        rules=session.scalars(select(PulseRule).where(PulseRule.project_id==pid).order_by(PulseRule.id).limit(100)).all()
        return dict(project=dict(id=project.id,name=project.name,slug=project.slug),
            territory=config.territory if config else '',min_classified=config.min_classified if config else 20,
            version=config.version if config else 0,connector=json.loads(config.connector) if config else ConnectorPlan().model_dump(),
            actors=[actor_record(a) for a in actors],
            rules=[dict(id=r.id,actor_id=r.actor_id,name=r.name,metric=r.metric,threshold=r.threshold,
                min_mentions=r.min_mentions,active=r.active,is_demo=r.is_demo) for r in rules],
            can_manage=member.role in MANAGERS,can_import=member.role in WRITERS,
            role=member.role,provider_enabled=False,external_calls=0,
            visual_review=__import__('os').getenv('NEXO_VISUAL_REVIEW')=='true')

    @app.put('/api/projects/{pid}/pulse/config')
    def configure(pid:int,body:ConfigInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS)
        try:
            values=dict(territory=body.territory.strip(),min_classified=body.min_classified,
                connector=body.connector.model_dump_json(),version=body.expected_version+1)
            if body.expected_version==0:session.add(PulseConfig(project_id=pid,**values))
            else:
                changed=session.execute(update(PulseConfig).where(PulseConfig.project_id==pid,PulseConfig.version==body.expected_version)
                    .values(**values),execution_options={'synchronize_session':False})
                if changed.rowcount!=1:
                    session.rollback();raise HTTPException(409,'La configuración cambió. Recárgala.')
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='pulse.configure',target=f'v{body.expected_version+1}'))
            session.commit();session.expire_all();return dict(version=body.expected_version+1)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'La configuración ya existe o cambió.') from None

    @app.post('/api/projects/{pid}/pulse/actors')
    def add_actor(pid:int,body:ActorInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS)
        from .actors_api import lock_project
        lock_project(session,pid)
        name=' '.join(body.name.split())
        if len(name)<2:raise HTTPException(422,'Indica el nombre del actor público.')
        if name.casefold() in {' '.join(n.split()).casefold() for n in session.scalars(select(PulseActor.name).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False)))}:
            raise HTTPException(409,'Ese nombre ya está registrado en el proyecto.')
        if session.scalar(select(func.count(PulseActor.id)).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False)))>=50:
            raise HTTPException(409,'Máximo 50 actores reales por proyecto en esta entrega.')
        row=PulseActor(project_id=pid,name=name,kind=body.kind,is_demo=False,created_by=user.id)
        try:
            session.add(row);session.flush();session.add(AuditEvent(project_id=pid,user_id=user.id,action='pulse.actor',target=str(row.id)))
            session.commit();return actor_record(row)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'Ya existe el nombre o un actor principal activo.') from None

    @app.put('/api/projects/{pid}/pulse/actors/{actor_id}')
    def edit_actor(pid:int,actor_id:int,body:ActorUpdate,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS)
        from .actors_api import lock_project
        lock_project(session,pid)
        name=' '.join(body.name.split())
        if len(name)<2:raise HTTPException(422,'El nombre requiere al menos dos caracteres.')
        if name.casefold() in {' '.join(n.split()).casefold() for n in session.scalars(select(PulseActor.name).where(PulseActor.project_id==pid,
            PulseActor.id!=actor_id,PulseActor.is_demo.is_(False)))}:
            raise HTTPException(409,'Ese nombre ya pertenece a otra ficha del proyecto.')
        try:
            changed=session.execute(update(PulseActor).where(PulseActor.id==actor_id,PulseActor.project_id==pid,
                PulseActor.version==body.expected_version,PulseActor.is_demo.is_(False)).values(name=name,kind=body.kind,
                    active=body.active,version=body.expected_version+1),execution_options={'synchronize_session':False})
            if changed.rowcount!=1:
                session.rollback();raise HTTPException(409,'El actor no está disponible o cambió.')
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='pulse.actor.update',target=f'{actor_id}:v{body.expected_version+1}'))
            session.commit();session.expire_all();return actor_record(session.get(PulseActor,actor_id))
        except IntegrityError:
            session.rollback();raise HTTPException(409,'El nombre o la función principal ya están en uso.') from None

    @app.post('/api/projects/{pid}/pulse/import')
    def ingest(pid:int,body:ImportBatch,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=WRITERS);return import_posts(session,pid,body,user.id)

    @app.put('/api/projects/{pid}/pulse/documents/{document_id}/actors/{actor_id}/classification')
    def classify(pid:int,document_id:int,actor_id:int,body:Classification,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=WRITERS)
        changed=session.execute(update(PulseMention).where(PulseMention.project_id==pid,
            PulseMention.document_id==document_id,PulseMention.actor_id==actor_id,PulseMention.is_demo.is_(False),
            PulseMention.version==body.expected_version).values(sentiment=body.sentiment,emotion=body.emotion,
                method='human_review:v1',reviewed_by=user.id,version=body.expected_version+1),execution_options={'synchronize_session':False})
        if changed.rowcount!=1:
            session.rollback();raise HTTPException(409,'La clasificación cambió o no está disponible.')
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='pulse.classify',target=f'{document_id}:{actor_id}:v{body.expected_version+1}'))
        session.commit();session.expire_all();return dict(version=body.expected_version+1)

    @app.get('/api/projects/{pid}/pulse/documents')
    def documents(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        rows=session.execute(select(PulseDocument,PulseMention).join(PulseMention,PulseMention.document_id==PulseDocument.id)
            .where(PulseDocument.project_id==pid,PulseMention.project_id==pid,PulseDocument.is_demo.is_(False))
            .order_by(PulseDocument.id.desc()).limit(100)).all()
        return [dict(id=d.id,title=d.title,url=d.url,actor_id=m.actor_id,sentiment=m.sentiment,emotion=m.emotion,
                     version=m.version,method=m.method) for d,m in rows]

    @app.post('/api/projects/{pid}/pulse/accounts')
    def account(pid:int,body:AccountInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=WRITERS)
        actor=session.scalar(select(PulseActor).where(PulseActor.id==body.actor_id,PulseActor.project_id==pid,
            PulseActor.is_demo.is_(False),PulseActor.active.is_(True)))
        if not actor:raise HTTPException(422,'Actor no disponible.')
        try:url=public_url(body.url)
        except ValueError as exc:raise HTTPException(422,str(exc))
        row=PulseAccount(project_id=pid,actor_id=body.actor_id,network=body.network,url=url,captured_at=utc(body.captured_at),
            metrics=json.dumps(body.model_dump(mode='json',exclude={'actor_id','network','url','captured_at'})),created_by=user.id,is_demo=False)
        try:
            session.add(row);session.flush();session.add(AuditEvent(project_id=pid,user_id=user.id,action='pulse.account',target=str(row.id)))
            session.commit();return dict(id=row.id)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'Ya existe una captura para esa cuenta y fecha.') from None

    @app.post('/api/projects/{pid}/pulse/rules')
    def rule(pid:int,body:RuleInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS)
        if body.metric=='negative_share' and body.threshold>100:raise HTTPException(422,'El porcentaje máximo es 100.')
        actor=session.scalar(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.id==body.actor_id,PulseActor.is_demo.is_(False),PulseActor.active.is_(True)))
        if not actor:raise HTTPException(422,'Actor no disponible.')
        if session.scalar(select(func.count(PulseRule.id)).where(PulseRule.project_id==pid))>=100:raise HTTPException(409,'Máximo 100 reglas por proyecto.')
        row=PulseRule(project_id=pid,**body.model_dump(),created_by=user.id,is_demo=False)
        session.add(row);session.flush();session.add(AuditEvent(project_id=pid,user_id=user.id,action='pulse.rule',target=str(row.id)))
        session.commit();return dict(id=row.id)

    @app.patch('/api/projects/{pid}/pulse/rules/{rule_id}')
    def rule_state(pid:int,rule_id:int,body:RuleState,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS)
        changed=session.execute(update(PulseRule).where(PulseRule.project_id==pid,PulseRule.id==rule_id,
            PulseRule.is_demo.is_(False)).values(active=body.active),execution_options={'synchronize_session':False})
        if changed.rowcount!=1:session.rollback();raise HTTPException(404,'Regla no disponible.')
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='pulse.rule.state',target=str(rule_id)))
        session.commit();return dict(id=rule_id,active=body.active)

    @app.get('/api/projects/{pid}/pulse')
    def dashboard(pid:int,actor_id:int=0,start:datetime|None=None,end:datetime|None=None,network:str='all',demo:bool=False,
                  user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session);return overview(session,pid,actor_id=actor_id,start=start,end=end,network=network,demo=demo)

    @app.post('/api/projects/{pid}/pulse/apify/sync')
    def sync(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS)
        try:DisabledApifyReader().read('',limit=500)
        except ApifyUnavailable as exc:raise HTTPException(409,str(exc))

    @app.post('/api/projects/{pid}/pulse/demo')
    def demo_data(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS)
        from .pulse_demo import ensure_demo
        return ensure_demo(session,pid,user.id)
