"""Atalaya account publications; no participant identities or network calls."""
from datetime import datetime,timezone
from typing import Literal
import hashlib,json
from fastapi import HTTPException
from pydantic import Field,field_validator,model_validator
from sqlalchemy import ForeignKey,ForeignKeyConstraint,UniqueConstraint,Index,String,Text,DateTime,select
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base
from .apify_port import Strict,public_url
from .actors_api import PublicChannel
from .pulse_models import PulseActor,PulseMention,PulseDocument
from .actor_models import ActorProfile
from .pulse_service import window
from .network_service import aware
from .news_review import iso_utc

NETWORKS=('facebook','instagram','tiktok','x','youtube')
MAX_CAPTURES=100
class FidelityCapture(Base):
    __tablename__='fidelity_captures'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False)
    actor_id:Mapped[int]=mapped_column(nullable=False)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    network:Mapped[str]=mapped_column(String(20),nullable=False)
    account_url:Mapped[str]=mapped_column(Text,nullable=False)
    captured_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    payload_json:Mapped[str]=mapped_column(Text,nullable=False)
    sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    source_kind:Mapped[str]=mapped_column(String(30),default='atalaya_import',nullable=False)
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    __table_args__=(ForeignKeyConstraint(['actor_id','project_id','is_demo'],['pulse_actors.id','pulse_actors.project_id','pulse_actors.is_demo'],name='fk_fidelity_actor'),
        UniqueConstraint('project_id','actor_id','network','account_url','captured_at',name='uq_fidelity_capture'),
        Index('ix_fidelity_project_capture','project_id','actor_id','captured_at'))

class Publication(Strict):
    url:str=Field(max_length=2000,min_length=10)
    published_at:datetime
    text:str=Field(default='',max_length=1000)
    reactions:int|None=Field(default=None,strict=True,ge=0,le=9007199254740991)
    comments:int|None=Field(default=None,strict=True,ge=0,le=9007199254740991)
    shares:int|None=Field(default=None,strict=True,ge=0,le=9007199254740991)
    followers:int|None=Field(default=None,strict=True,ge=0,le=9007199254740991)
    @field_validator('reactions','comments','shares','followers',mode='before')
    @classmethod
    def missing_sentinel(cls,v):return None if type(v) is int and v==-1 else v
    @model_validator(mode='after')
    def coherent(self):
        self.url=public_url(self.url)
        if self.published_at.tzinfo is None:raise ValueError('La fecha necesita zona horaria.')
        self.published_at=self.published_at.astimezone(timezone.utc)
        return self

class AtalayaPublicationBatch(Strict):
    contract:Literal['atalaya-publications-v1']='atalaya-publications-v1'
    actor_id:int=Field(strict=True,gt=0)
    network:Literal['facebook','instagram','tiktok','x','youtube']
    account_url:str=Field(max_length=1500)
    captured_at:datetime
    publications:list[Publication]=Field(min_length=1,max_length=500)
    @model_validator(mode='after')
    def coherent(self):
        self.account_url=PublicChannel(network=self.network,url=self.account_url).url
        if self.captured_at.tzinfo is None:raise ValueError('La captura necesita zona horaria.')
        self.captured_at=self.captured_at.astimezone(timezone.utc)
        if any(p.published_at>self.captured_at for p in self.publications):raise ValueError('Publicación posterior a la captura.')
        for p in self.publications:PublicChannel(network=self.network,url=p.url)
        if len({p.url for p in self.publications})!=len(self.publications):raise ValueError('Publicaciones duplicadas en el lote.')
        return self

def context(session,pid,actor_id=0,network='all',account_url=''):
    if network not in ('all',)+NETWORKS:raise HTTPException(422,'Red no admitida para esta vista.')
    actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.active.is_(True),PulseActor.is_demo.is_(False))
        .order_by(PulseActor.kind.desc(),PulseActor.id).limit(50)).all()
    actor=next((a for a in actors if a.id==actor_id),None) if actor_id else next((a for a in actors if a.kind=='primary'),actors[0] if actors else None)
    if actor_id and actor is None:raise HTTPException(404,'Actor no disponible en este proyecto.')
    profile=session.scalar(select(ActorProfile).where(ActorProfile.project_id==pid,ActorProfile.actor_id==actor.id)) if actor else None
    refs=json.loads(profile.channels_json) if profile else []
    accounts=[dict(network=r['network'],url=r['url']) for r in refs if r.get('enabled',True) and r['network'] in NETWORKS
              and (network=='all' or network==r['network'])]
    if account_url:
        accounts=[r for r in accounts if r['url']==account_url]
        if not accounts:raise HTTPException(404,'Cuenta no disponible en este proyecto.')
    return actor,accounts

def fingerprint(body):
    value=body.model_dump(mode='json');value['publications']=sorted(value['publications'],key=lambda p:p['url'])
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return raw,hashlib.sha256(raw.encode()).hexdigest()

def activity(session,pid,*,actor_id=0,network='all',account_url='',start=None,end=None,now=None):
    now=now or datetime.now(timezone.utc);start,end=window(start,end,now=now)
    if end>now:raise HTTPException(422,'El periodo no puede terminar en el futuro.')
    actor,accounts=context(session,pid,actor_id,network,account_url)
    records=[]
    if actor:
        records=session.scalars(select(FidelityCapture).where(FidelityCapture.project_id==pid,FidelityCapture.actor_id==actor.id,
            FidelityCapture.is_demo.is_(False),FidelityCapture.captured_at<=now).order_by(FidelityCapture.captured_at.desc(),FidelityCapture.id.desc()).limit(MAX_CAPTURES+1)).all()
    bounded=len(records)>MAX_CAPTURES;records=records[:MAX_CAPTURES]
    latest={};permitted={(a['network'],a['url']) for a in accounts}
    for r in records:
        key=(r.network,r.account_url)
        if key in permitted:latest.setdefault(key,r)
    rows=[];account_rows=[];last_at=None;synthetic=False
    for key,capture in latest.items():
        observations=json.loads(capture.payload_json)['publications'];captured=aware(capture.captured_at)
        last_at=max(last_at,captured) if last_at else captured;synthetic=synthetic or capture.source_kind=='synthetic'
        followers=next((p['followers'] for p in sorted(observations,key=lambda p:p['published_at'],reverse=True) if p.get('followers') is not None),None)
        account_rows.append(dict(network=key[0],url=key[1],followers=followers,captured_at=iso_utc(captured)))
        for p in observations:
            when=datetime.fromisoformat(p['published_at'])
            if not start<=when<end:continue
            values=[p.get(k) for k in ('reactions','comments','shares')]
            count=sum(v for v in values if v is not None) if any(v is not None for v in values) else None
            rows.append(dict(**p,network=key[0],account_url=key[1],account_name=actor.name,interactions=count,
                partial=any(v is None for v in values),engagement_rate=round(100*count/p['followers'],2) if count is not None and p.get('followers') else None))
    rows.sort(key=lambda p:(p['published_at'],p['url']),reverse=True)
    values=[r['interactions'] for r in rows]
    interactions=sum(v for v in values if v is not None) if any(v is not None for v in values) else None
    follower_values=[a['followers'] for a in account_rows]
    followers=sum(follower_values) if follower_values and all(v is not None for v in follower_values) else None
    complete_denominator=len(latest)==len(accounts) and bool(accounts) and followers is not None and followers>0
    if len(latest)!=len(accounts):followers=None
    mentions=[]
    if actor and not account_url:
        q=select(PulseDocument).join(PulseMention,(PulseMention.document_id==PulseDocument.id)&(PulseMention.project_id==pid)&(PulseMention.is_demo==False)).where(
            PulseDocument.project_id==pid,PulseDocument.is_demo.is_(False),PulseMention.actor_id==actor.id,PulseDocument.published_at>=start,PulseDocument.published_at<end)
        if network!='all':q=q.where(PulseDocument.network==network)
        docs=session.scalars(q.distinct().order_by(PulseDocument.published_at.desc(),PulseDocument.id.desc()).limit(501)).all()
        mentions=[dict(url=d.url,published_at=iso_utc(d.published_at),network=d.network,text=d.title,interactions=d.interactions) for d in docs[:500]]
        bounded=bounded or len(docs)>500
    return dict(project_id=pid,actor_id=actor.id if actor else None,actor_name=actor.name if actor else '',
        window=dict(start=iso_utc(start),end=iso_utc(end)),accounts=account_rows,registered_accounts=accounts,
        summary=dict(publications=len(rows) if latest else None,interactions=interactions,followers=followers,
            engagement_rate=round(100*interactions/followers,2) if interactions is not None and complete_denominator else None,
            account_count=len(latest),mentions=len(mentions) if actor and not account_url else None),
        publications=rows,mentions=mentions,mentions_scope='actor' if not account_url else 'not_attributed_to_account',
        partial_counters=any(r['partial'] for r in rows),latest_capture=iso_utc(last_at),
        source_kind='synthetic' if synthetic else 'atalaya_import' if latest else 'empty',
        coverage_bounded=bounded,query_limit=MAX_CAPTURES,external_calls=0,provider_enabled=False,
        rate_definition='Interacciones disponibles en publicaciones del periodo / seguidores de las cuentas seleccionadas × 100.',
        followers_definition='Suma de contadores de cuentas; no personas distintas.')
