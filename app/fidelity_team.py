"""Registered collaborator activity. Counts only; no political or belief labels."""
from datetime import datetime,timezone
from typing import Literal
from urllib.parse import urlsplit,parse_qs
import csv,hashlib,json,re,unicodedata
from io import StringIO
from fastapi import HTTPException
from pydantic import Field,model_validator
from sqlalchemy import ForeignKey,ForeignKeyConstraint,UniqueConstraint,Index,String,Text,DateTime,select
from sqlalchemy.orm import Mapped,mapped_column
from .models import Base
from .apify_port import Strict
from .actors_api import PublicChannel
from .workbook_evidence import read_workbook,WorkbookInvalid,MAX_FILE
from .fidelity import FidelityCapture,context,activity
from .network_service import aware
from .news_review import iso_utc

HOSTS={'facebook':'facebook.com','instagram':'instagram.com','tiktok':'tiktok.com','x':'x.com'}
def profile_key(network,value):
    value=str(value or '').strip()
    if not value:return ''
    if network=='facebook' and re.fullmatch(r'id:[0-9]+',value):return value
    if len(value)>1500:raise ValueError('Enlace de perfil demasiado largo.')
    if value.startswith(('https://','http://')):
        value=PublicChannel(network=network,url=value).url;p=urlsplit(value)
        host=re.sub(r'^(www|m|mobile|web)\.','',p.hostname.lower())
        if network=='facebook' and p.path.rstrip('/')=='/profile.php':
            ident=(parse_qs(p.query).get('id') or [''])[0]
            if not ident.isdigit():raise ValueError('El perfil de Facebook necesita su identificador.')
            return 'id:'+ident
        value=p.path.strip('/').split('/')[0].lstrip('@')
    else:value=value.lstrip('@')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',value):raise ValueError('Usa un enlace o usuario de la red, no un nombre de persona.')
    return value.lower()

class TeamMember(Base):
    __tablename__='fidelity_team_members'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False)
    external_key:Mapped[str]=mapped_column(String(100),nullable=False)
    display_name:Mapped[str]=mapped_column(String(160),nullable=False)
    profiles_json:Mapped[str]=mapped_column(Text,nullable=False)
    active:Mapped[bool]=mapped_column(default=True,nullable=False)
    source_sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    updated_by:Mapped[int]=mapped_column(ForeignKey('users.id'),nullable=False)
    __table_args__=(UniqueConstraint('id','project_id',name='uq_fidelity_team_scope'),
        UniqueConstraint('project_id','external_key',name='uq_fidelity_team_external'))

class TeamObservation(Base):
    __tablename__='fidelity_team_observations'
    id:Mapped[int]=mapped_column(primary_key=True)
    project_id:Mapped[int]=mapped_column(ForeignKey('projects.id'),nullable=False)
    member_id:Mapped[int]=mapped_column(nullable=False)
    actor_id:Mapped[int]=mapped_column(nullable=False)
    is_demo:Mapped[bool]=mapped_column(default=False,nullable=False)
    network:Mapped[str]=mapped_column(String(20),nullable=False)
    post_url:Mapped[str]=mapped_column(Text,nullable=False)
    kind:Mapped[str]=mapped_column(String(25),nullable=False)
    source_key:Mapped[str]=mapped_column(String(64),nullable=False)
    observed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    source_kind:Mapped[str]=mapped_column(String(30),default='local_import',nullable=False)
    __table_args__=(ForeignKeyConstraint(['member_id','project_id'],['fidelity_team_members.id','fidelity_team_members.project_id'],name='fk_team_observation_member'),
        ForeignKeyConstraint(['actor_id','project_id','is_demo'],['pulse_actors.id','pulse_actors.project_id','pulse_actors.is_demo'],name='fk_team_observation_actor'),
        UniqueConstraint('project_id','member_id','actor_id','network','post_url','kind','source_key',name='uq_team_observation'),
        Index('ix_team_project_actor','project_id','actor_id'))

def header(v):
    v=''.join(c for c in unicodedata.normalize('NFKD',str(v).lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]','',v)
ALIASES={'nombre':'name','name':'name','integrante':'name','colaborador':'name','id':'key','codigo':'key',
         'facebook':'facebook','fb':'facebook','instagram':'instagram','ig':'instagram','tiktok':'tiktok','tt':'tiktok','x':'x','twitter':'x','usuariofacebook':'facebook','perfilfacebook':'facebook','enlacefacebook':'facebook','usuarioinstagram':'instagram','usuariox':'x'}
def parse_roster(raw,filename,sheet=''):
    if not raw or len(raw)>MAX_FILE:raise ValueError('El archivo debe tener como máximo 2 MB.')
    if filename.lower().endswith('.xlsx'):
        books=read_workbook(raw);candidates=[]
        for book in books:
            if sheet and book['name']!=sheet:continue
            for n,cells in sorted(book['rows'].items())[:10]:
                fields={col:ALIASES.get(header(cell['value'])) for col,cell in cells.items()}
                if 'name' in fields.values() and any(k in fields.values() for k in HOSTS):
                    if any(c.get('formula') for c in cells.values()):raise ValueError('Los encabezados deben ser texto, sin fórmulas.')
                    rows=[]
                    for rownum,row in sorted(book['rows'].items()):
                        if rownum<=n:continue
                        mapped={}
                        for col,key in fields.items():
                            if not key or col not in row:continue
                            if row[col].get('formula'):raise ValueError('Fila '+str(rownum)+': usa valores de texto, no fórmulas.')
                            mapped[key]=row[col]['value']
                        if mapped:rows.append((rownum,mapped))
                    candidates.append((book['name'],rows));break
        if len(candidates)!=1:raise ValueError('Elige una sola hoja con columnas Nombre y al menos una red. Si hay varias, indica su nombre.')
        rows=candidates[0][1]
    elif filename.lower().endswith('.csv'):
        text=raw.decode('utf-8-sig')
        try:dialect=csv.Sniffer().sniff(text[:5000],delimiters=',;\t')
        except csv.Error:raise ValueError('El CSV necesita encabezados separados por coma o punto y coma.') from None
        reader=csv.DictReader(StringIO(text),dialect=dialect,strict=True)
        try:raw_rows=list(reader)
        except csv.Error:raise ValueError('El CSV contiene una fila incompleta o comillas sin cerrar.') from None
        if any(None in r for r in raw_rows):raise ValueError('Hay filas con más columnas que los encabezados.')
        rows=[(n,{ALIASES.get(header(k)):v for k,v in row.items() if k and ALIASES.get(header(k))}) for n,row in enumerate(raw_rows,2)]
    else:raise ValueError('Elige un archivo XLSX o CSV UTF-8.')
    if not 1<=len(rows)<=500:raise ValueError('Carga de 1 a 500 integrantes por archivo.')
    prepared={};identities={}
    for n,row in rows:
        name=str(row.get('name','')).strip()
        if not 2<=len(name)<=160 or any(ord(c)<32 or ord(c)==127 for c in name):raise ValueError('Fila '+str(n)+': falta un nombre válido.')
        profiles={}
        for network in HOSTS:
            try:key=profile_key(network,row.get(network,''))
            except ValueError as e:raise ValueError('Fila '+str(n)+', '+network+': '+str(e)) from None
            if key:profiles[network]=key
        if not profiles:raise ValueError('Fila '+str(n)+': incluye al menos una cuenta del integrante.')
        raw_key=str(row.get('key','')).strip()
        if len(raw_key)>95:raise ValueError('El código del integrante excede 100 caracteres.')
        key='code:'+raw_key if raw_key else 'name:'+hashlib.sha256(name.casefold().encode()).hexdigest()
        record=dict(external_key=key,display_name=name,profiles=profiles)
        if key in prepared and prepared[key]!=record:raise ValueError('Hay nombres o códigos repetidos con cuentas distintas. Usa un Código único por integrante.')
        for network,ident in profiles.items():
            previous=identities.setdefault((network,ident),key)
            if previous!=key:raise ValueError('La misma cuenta aparece en dos integrantes distintos.')
        prepared[key]=record
    return list(prepared.values())

class TeamEvent(Strict):
    member_id:int=Field(gt=0,strict=True)
    network:Literal['facebook','instagram','tiktok','x']
    post_url:str=Field(min_length=10,max_length=1500)
    kind:Literal['reaction','comment','reply','comment_presence']
    event_id:str=Field(default='',max_length=300)
    observed_at:datetime
    @model_validator(mode='after')
    def coherent(self):
        self.post_url=PublicChannel(network=self.network,url=self.post_url).url
        if self.observed_at.tzinfo is None:raise ValueError('La observación necesita zona horaria.')
        self.observed_at=self.observed_at.astimezone(timezone.utc)
        if self.kind in ('comment','reply') and not self.event_id:raise ValueError('Los comentarios individuales necesitan su identificador de origen.')
        return self

class TeamEvents(Strict):
    actor_id:int=Field(gt=0,strict=True)
    events:list[TeamEvent]=Field(min_length=1,max_length=5000)

def registered_posts(session,pid,actor_id,network='all',account_url=''):
    actor,refs=context(session,pid,actor_id,network,account_url)
    allowed={(a['network'],a['url']) for a in refs};latest={}
    rows=session.scalars(select(FidelityCapture).where(FidelityCapture.project_id==pid,FidelityCapture.actor_id==actor.id,
        FidelityCapture.is_demo.is_(False)).order_by(FidelityCapture.captured_at.desc(),FidelityCapture.id.desc()).limit(100)).all() if actor else []
    for row in rows:
        key=(row.network,row.account_url)
        if key in allowed:latest.setdefault(key,row)
    posts={}
    for capture in latest.values():
        for p in json.loads(capture.payload_json)['publications']:
            posts[(capture.network,p['url'])]=p
    return actor,posts

def team_dashboard(session,pid,*,actor_id=0,network='all',account_url='',start=None,end=None):
    packet=activity(session,pid,actor_id=actor_id,network=network,account_url=account_url,start=start,end=end)
    actor,posts=registered_posts(session,pid,packet['actor_id'] or 0,network,account_url)
    allowed={(p['network'],p['url']) for p in packet['publications']}
    members=session.scalars(select(TeamMember).where(TeamMember.project_id==pid,TeamMember.active.is_(True)).order_by(TeamMember.id).limit(501)).all()
    events=session.scalars(select(TeamObservation).where(TeamObservation.project_id==pid,TeamObservation.actor_id==actor.id,TeamObservation.member_id.in_([m.id for m in members]),TeamObservation.post_url.in_([k[1] for k in allowed])).order_by(TeamObservation.id).limit(20001)).all() if actor else []
    bounded=len(members)>500 or len(events)>20000
    if bounded:raise HTTPException(422,'Acota el periodo: hay demasiados registros para este corte de equipo.')
    rows=[]
    for member in members[:500]:
        profiles=json.loads(member.profiles_json);eligible={k for k in allowed if k[0] in profiles}
        observations=[e for e in events[:20000] if e.member_id==member.id and (e.network,e.post_url) in eligible]
        touched={(e.network,e.post_url) for e in observations}
        commented={(e.network,e.post_url) for e in observations if e.kind in ('comment','reply','comment_presence')}
        actual=[e for e in observations if e.kind in ('comment','reply')]
        last=max((aware(e.observed_at) for e in observations),default=None)
        rows.append(dict(member_id=member.id,name=member.display_name,networks=[n for n in profiles if network=='all' or n==network],
            reaction_posts=len({(e.network,e.post_url) for e in observations if e.kind=='reaction'}),comment_posts=len(commented),
            comment_events=len(actual) if actual else None,participated_posts=len(touched),eligible_posts=len(eligible),
            participation_percent=round(100*len(touched)/len(eligible),2) if eligible else None,last_observed=iso_utc(last)))
    rows.sort(key=lambda r:(-r['participated_posts'],-r['reaction_posts'],r['name'].casefold()))
    summary=dict(members=len(rows),members_with_records=sum(bool(r['participated_posts']) for r in rows),
        reaction_posts=sum(r['reaction_posts'] for r in rows),comment_posts=sum(r['comment_posts'] for r in rows))
    return dict(project_id=pid,actor_id=packet['actor_id'],window=packet['window'],rows=rows,summary=summary,
        coverage_bounded=bounded,source_kind=packet['source_kind'],external_calls=0,
        scope='Acciones registradas de colaboradores aportados por el proyecto; sin inferencias de opiniones.',
        ranking_basis='Publicaciones con actividad registrada; después reacciones. No es una puntuación de lealtad.',
        community=dict(reactions=observed_total(packet['publications'],'reactions'),
            comments=observed_total(packet['publications'],'comments'),
            shares=observed_total(packet['publications'],'shares'),
            identified_people=False,includes_team=True))


def observed_total(rows,key):
    values=[r[key] for r in rows if r[key] is not None]
    return sum(values) if values else None
