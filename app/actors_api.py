"""Generic public-actor directory; references are stored, never fetched here."""
from datetime import datetime,timezone
from typing import Literal
from urllib.parse import urlsplit
import json
from fastapi import Depends,HTTPException
from pydantic import Field,model_validator
from sqlalchemy import select,func,update,text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError,OperationalError
from .models import AuditEvent
from .pulse_models import PulseActor,PulseMention,PulseAccount
from .actor_models import ActorProfile
from .apify_port import Strict,Network,public_url
from .pulse_api import actor_record,MANAGERS

HOSTS={'facebook':('facebook.com',),'instagram':('instagram.com',),'x':('x.com','twitter.com'),
    'tiktok':('tiktok.com',),'youtube':('youtube.com','youtu.be')}

class PublicChannel(Strict):
    network:Network
    url:str=Field(min_length=10,max_length=1500)
    external_id:str=Field(default='',max_length=160,pattern=r'^[A-Za-z0-9_@.:-]*$')
    enabled:bool=True
    review:Literal['unreviewed','reviewed']='unreviewed'

    @model_validator(mode='after')
    def safe_reference(self):
        self.url=public_url(self.url)
        host=urlsplit(self.url).hostname
        if self.network in HOSTS and not any(host==h or host.endswith('.'+h) for h in HOSTS[self.network]):
            raise ValueError('El dominio debe corresponder a la red elegida.')
        if self.network in HOSTS and urlsplit(self.url).path=='/':raise ValueError('Indica el enlace del perfil, no solo la portada de la red.')
        return self

class ProfileFields(Strict):
    name:str=Field(min_length=2,max_length=120)
    public_role:str=Field(default='',max_length=160)
    organization:str=Field(default='',max_length=160)
    territory:str=Field(default='',max_length=160)
    description:str=Field(default='',max_length=1500)
    aliases:list[str]=Field(default_factory=list,max_length=12)
    channels:list[PublicChannel]=Field(default_factory=list,max_length=12)

    @model_validator(mode='after')
    def clean(self):
        for field in ('name','public_role','organization','territory'):
            value=' '.join(getattr(self,field).split())
            if any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('Texto no admitido.')
            setattr(self,field,value)
        if len(self.name)<2:raise ValueError('Indica el nombre público.')
        if any(ord(c)<32 and c not in '\n\r\t' for c in self.description):raise ValueError('Descripción no admitida.')
        aliases=[' '.join(x.split()) for x in self.aliases]
        if any(not 2<=len(x)<=80 or any(ord(c)<32 or ord(c)==127 for c in x) for x in aliases):raise ValueError('Cada nombre alternativo debe tener entre 2 y 80 caracteres.')
        if len({x.casefold() for x in aliases})!=len(aliases):raise ValueError('Hay nombres alternativos repetidos.')
        self.aliases=aliases
        keys=[(c.network,c.url) for c in self.channels]
        if len(set(keys))!=len(keys):raise ValueError('Hay cuentas repetidas en la ficha.')
        return self

class ActorCreate(ProfileFields):
    kind:Literal['primary','comparator']='comparator'

class ProfileUpdate(ProfileFields):
    expected_actor_version:int=Field(ge=1)
    expected_profile_version:int=Field(ge=0)

class ActorState(Strict):
    active:bool
    expected_version:int=Field(ge=1)

class MakePrimary(Strict):
    expected_version:int=Field(ge=1)
    previous_primary_id:int|None=None
    previous_primary_version:int|None=None

    @model_validator(mode='after')
    def paired(self):
        if (self.previous_primary_id is None)!=(self.previous_primary_version is None):raise ValueError('La referencia al principal requiere su versión.')
        return self

def profile_values(body,user_id,version):
    return dict(public_role=body.public_role,organization=body.organization,territory=body.territory,
        description=body.description.strip(),aliases_json=json.dumps(body.aliases,ensure_ascii=False),
        channels_json=json.dumps([c.model_dump() for c in body.channels],ensure_ascii=False),
        updated_by=user_id,version=version,updated_at=datetime.now(timezone.utc))

def lock_project(session,pid):
    if session.bind.dialect.name=='sqlite':
        connection=session.connection()
        if not connection.connection.driver_connection.in_transaction:
            try:connection.exec_driver_sql('BEGIN IMMEDIATE')
            except OperationalError:raise HTTPException(409,'El proyecto está ocupado. Intenta guardar otra vez.') from None
    else:session.execute(text('SELECT pg_advisory_xact_lock(:scope,:pid)'),{'scope':7852,'pid':pid})

def install_actors_api(app,db,current_user,allow):
    @app.get('/api/projects/{pid}/actors')
    def listing(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        project,member=allow(pid,user,session)
        actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False)).order_by(
            PulseActor.active.desc(),PulseActor.kind.desc(),PulseActor.name,PulseActor.id).limit(51)).all()
        profiles={p.actor_id:p for p in session.scalars(select(ActorProfile).where(ActorProfile.project_id==pid)).all()}
        mentions=dict(session.execute(select(PulseMention.actor_id,func.count()).where(PulseMention.project_id==pid,PulseMention.is_demo.is_(False)).group_by(PulseMention.actor_id)).all())
        captures={i:(n,t.isoformat() if t else None) for i,n,t in session.execute(select(PulseAccount.actor_id,func.count(),func.max(PulseAccount.captured_at)).where(
            PulseAccount.project_id==pid,PulseAccount.is_demo.is_(False)).group_by(PulseAccount.actor_id)).all()}
        items=[]
        for actor in actors[:50]:
            p=profiles.get(actor.id);count,stamp=captures.get(actor.id,(0,None))
            items.append(dict(**actor_record(actor),profile_version=p.version if p else 0,
                **{key:getattr(p,key) if p else '' for key in ('public_role','organization','territory','description')},
                aliases=json.loads(p.aliases_json) if p else [],channels=json.loads(p.channels_json) if p else [],
                mentions_in_archive=mentions.get(actor.id,0),account_snapshots=count,last_snapshot_at=stamp))
        return dict(project=dict(id=project.id,name=project.name),items=items,can_manage=member.role in MANAGERS,
            truncated=len(actors)>50,limit=50,external_calls=0)

    @app.post('/api/projects/{pid}/actors')
    def create(pid:int,body:ActorCreate,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS);lock_project(session,pid)
        if session.scalar(select(func.count()).select_from(PulseActor).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False)))>=50:
            raise HTTPException(409,'Este proyecto admite hasta 50 actores, incluidos los archivados.')
        # Normalize and case-fold in Python over the bounded directory, including legacy entries.
        existing=session.scalars(select(PulseActor.name).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False))).all()
        if body.name.casefold() in {' '.join(n.split()).casefold() for n in existing}:raise HTTPException(409,'Ese nombre ya está registrado en el proyecto.')
        try:
            row=PulseActor(project_id=pid,name=body.name,kind=body.kind,is_demo=False,created_by=user.id)
            session.add(row);session.flush()
            session.add(ActorProfile(actor_id=row.id,project_id=pid,is_demo=False,**profile_values(body,user.id,1)))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='actors.create',target=str(row.id)))
            session.commit();return dict(id=row.id,version=row.version,profile_version=1)
        except IntegrityError:session.rollback();raise HTTPException(409,'El nombre o el actor principal ya están registrados. Actualiza el directorio.') from None

    @app.put('/api/projects/{pid}/actors/{actor_id}')
    def edit(pid:int,actor_id:int,body:ProfileUpdate,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS);lock_project(session,pid)
        row=session.scalar(select(PulseActor).where(PulseActor.id==actor_id,PulseActor.project_id==pid,PulseActor.is_demo.is_(False)))
        if row is None:raise HTTPException(404,'Actor no disponible en este proyecto.')
        others=session.scalars(select(PulseActor.name).where(PulseActor.project_id==pid,PulseActor.id!=actor_id,PulseActor.is_demo.is_(False))).all()
        if body.name.casefold() in {' '.join(n.split()).casefold() for n in others}:raise HTTPException(409,'Ese nombre ya pertenece a otra ficha del proyecto.')
        try:
            changed=session.execute(update(PulseActor).where(PulseActor.id==actor_id,PulseActor.project_id==pid,
                PulseActor.version==body.expected_actor_version).values(name=body.name,version=body.expected_actor_version+1),execution_options={'synchronize_session':False})
            if changed.rowcount!=1:raise HTTPException(409,'La ficha cambió. Recarga el directorio antes de guardar.')
            values=profile_values(body,user.id,body.expected_profile_version+1)
            if body.expected_profile_version==0:session.add(ActorProfile(actor_id=actor_id,project_id=pid,is_demo=False,**values))
            else:
                changed=session.execute(update(ActorProfile).where(ActorProfile.actor_id==actor_id,ActorProfile.project_id==pid,
                    ActorProfile.version==body.expected_profile_version).values(**values),execution_options={'synchronize_session':False})
                if changed.rowcount!=1:raise HTTPException(409,'La ficha cambió. Recarga el directorio antes de guardar.')
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='actors.profile',target=f'{actor_id}:v{body.expected_profile_version+1}'))
            session.commit();session.expire_all();return dict(id=actor_id,version=body.expected_actor_version+1,profile_version=body.expected_profile_version+1)
        except (IntegrityError,HTTPException) as exc:
            session.rollback()
            if isinstance(exc,HTTPException):raise
            raise HTTPException(409,'La ficha ya existe o cambió. Actualiza el directorio.') from None

    @app.patch('/api/projects/{pid}/actors/{actor_id}/state')
    def state(pid:int,actor_id:int,body:ActorState,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS);lock_project(session,pid)
        row=session.scalar(select(PulseActor).where(PulseActor.id==actor_id,PulseActor.project_id==pid,PulseActor.is_demo.is_(False)))
        if row is None:raise HTTPException(404,'Actor no disponible en este proyecto.')
        kind=row.kind
        if body.active and kind=='primary' and session.scalar(select(PulseActor.id).where(PulseActor.project_id==pid,
            PulseActor.id!=actor_id,PulseActor.is_demo.is_(False),PulseActor.active.is_(True),PulseActor.kind=='primary')):
            kind='comparator'
        try:
            changed=session.execute(update(PulseActor).where(PulseActor.id==actor_id,PulseActor.project_id==pid,PulseActor.is_demo.is_(False),
                PulseActor.version==body.expected_version).values(active=body.active,kind=kind,version=body.expected_version+1),execution_options={'synchronize_session':False})
            if changed.rowcount!=1:raise HTTPException(409,'El actor cambió o ya no está disponible. Actualiza el directorio.')
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='actors.state',target=f'{actor_id}:{int(body.active)}'))
            session.commit();session.expire_all();return dict(version=body.expected_version+1)
        except (IntegrityError,HTTPException) as exc:
            session.rollback()
            if isinstance(exc,HTTPException):raise
            raise HTTPException(409,'Ya existe un actor principal activo. Reactiva esta ficha después de cambiar el principal.') from None

    @app.post('/api/projects/{pid}/actors/{actor_id}/primary')
    def primary(pid:int,actor_id:int,body:MakePrimary,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles=MANAGERS);lock_project(session,pid)
        rows=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False),PulseActor.active.is_(True))).all()
        target=next((r for r in rows if r.id==actor_id),None);old=next((r for r in rows if r.kind=='primary'),None)
        if not target:raise HTTPException(404,'Actor activo no disponible.')
        if target.version!=body.expected_version or (old.id if old else None)!=body.previous_primary_id or (old.version if old else None)!=body.previous_primary_version:
            raise HTTPException(409,'El principal o la ficha cambiaron. Actualiza el directorio.')
        if old and old.id==actor_id:return dict(id=target.id,version=target.version)
        try:
            # Demote and flush first to satisfy the existing unique active-primary index.
            if old:
                changed=session.execute(update(PulseActor).where(PulseActor.id==old.id,PulseActor.project_id==pid,PulseActor.version==old.version,
                    PulseActor.kind=='primary',PulseActor.active.is_(True)).values(kind='comparator',version=old.version+1),execution_options={'synchronize_session':False})
                if changed.rowcount!=1:raise HTTPException(409,'El principal cambió. Actualiza el directorio.')
            changed=session.execute(update(PulseActor).where(PulseActor.id==actor_id,PulseActor.project_id==pid,PulseActor.version==body.expected_version,
                PulseActor.active.is_(True)).values(kind='primary',version=body.expected_version+1),execution_options={'synchronize_session':False})
            if changed.rowcount!=1:raise HTTPException(409,'El actor cambió. Actualiza el directorio.')
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='actors.primary',target=str(actor_id)))
            session.commit();session.expire_all();return dict(id=actor_id,version=body.expected_version+1)
        except (IntegrityError,HTTPException) as exc:
            session.rollback()
            if isinstance(exc,HTTPException):raise
            raise HTTPException(409,'El principal cambió. Actualiza el directorio.') from None
