"""Collaborator roster and observed activity, with platform-owner imports."""
from datetime import datetime,timezone
import hashlib,json,csv
from io import StringIO
from fastapi import Depends,HTTPException,UploadFile,File,Form,Response
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .fidelity_team import TeamMember,TeamObservation,TeamEvents,parse_roster,registered_posts,team_dashboard
from .client_access import is_owner
from .apify_port import Strict
from .actors_api import lock_project
from .controls import take_quota
from .models import AuditEvent

class TeamMemberInput(Strict):
    code:str=Field(default='',max_length=95)
    name:str=Field(min_length=2,max_length=160)
    facebook:str=Field(default='',max_length=1500)
    instagram:str=Field(default='',max_length=1500)
    tiktok:str=Field(default='',max_length=1500)
    x:str=Field(default='',max_length=1500)

class TeamState(Strict):
    active:bool

def install_team_api(app,db,current_user,allow):
    engine=getattr(app.state,'engine',None)
    if engine is not None and engine.dialect.name=='sqlite':
        TeamMember.__table__.create(bind=engine,checkfirst=True);TeamObservation.__table__.create(bind=engine,checkfirst=True)
    def owner(pid,user,session):
        allow(pid,user,session)
        if not is_owner(session,user):raise HTTPException(403,'Solo el superadministrador gestiona el equipo y sus registros.')

    def save_records(pid,records,sha,user,session,action,limit):
        take_quota(session,pid,action,limit);lock_project(session,pid)
        inserted=updated=unchanged=0
        try:
            existing=session.scalars(select(TeamMember).where(TeamMember.project_id==pid)).all()
            by_key={m.external_key:m for m in existing}
            candidates={m.external_key:dict(profiles=json.loads(m.profiles_json),name=m.display_name,active=m.active) for m in existing}
            for r in records:candidates[r['external_key']]=dict(profiles=r['profiles'],name=r['display_name'],active=True)
            owners={}
            for key,record in candidates.items():
                if not record['active']:continue
                for network,profile in record['profiles'].items():
                    old=owners.setdefault((network,profile),key)
                    if old!=key:raise HTTPException(409,'Una cuenta ya está asignada a otro integrante. Revisa sus códigos.')
            if sum(bool(r['active']) for r in candidates.values())>500:raise HTTPException(422,'Máximo 500 integrantes activos por proyecto.')
            for r in records:
                encoded=json.dumps(r['profiles'],ensure_ascii=False,sort_keys=True);member=by_key.get(r['external_key'])
                if member:
                    if member.display_name==r['display_name'] and member.profiles_json==encoded and member.active:unchanged+=1;continue
                    member.display_name=r['display_name'];member.profiles_json=encoded;member.active=True;member.source_sha256=sha;member.updated_by=user.id;updated+=1
                else:
                    session.add(TeamMember(project_id=pid,external_key=r['external_key'],display_name=r['display_name'],profiles_json=encoded,
                        active=True,source_sha256=sha,updated_by=user.id));inserted+=1
            session.add(AuditEvent(project_id=pid,user_id=user.id,action=action,target=f'new:{inserted}:updated:{updated}:same:{unchanged}'))
            session.commit();return dict(inserted=inserted,updated=updated,unchanged=unchanged,external_calls=0)
        except Exception:session.rollback();raise

    @app.post('/api/projects/{pid}/continuity/team/roster/member')
    def save_member(pid:int,body:TeamMemberInput,user=Depends(current_user),session:Session=Depends(db)):
        owner(pid,user,session)
        text=StringIO();writer=csv.writer(text)
        writer.writerow(['Código','Nombre','Facebook','Instagram','TikTok','X'])
        writer.writerow([body.code,body.name,body.facebook,body.instagram,body.tiktok,body.x])
        raw=text.getvalue().encode('utf-8')
        try:records=parse_roster(raw,'member.csv')
        except ValueError as exc:raise HTTPException(422,str(exc)) from None
        return save_records(pid,records,hashlib.sha256(raw).hexdigest(),user,session,'fidelity.team_member',100)

    @app.get('/api/projects/{pid}/continuity/team')
    def dashboard(pid:int,actor_id:int=0,network:str='all',account_url:str='',start:datetime|None=None,end:datetime|None=None,
                  user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        return dict(**team_dashboard(session,pid,actor_id=actor_id,network=network,account_url=account_url,start=start,end=end),can_manage=is_owner(session,user))

    @app.get('/api/projects/{pid}/continuity/team/{member_id}/profile')
    def member_profile(pid:int,member_id:int,actor_id:int=0,network:str='all',account_url:str='',start:datetime|None=None,end:datetime|None=None,page:int=1,
                       user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        if not 1<=page<=1000:raise HTTPException(422,'Página fuera de rango.')
        member=session.scalar(select(TeamMember).where(TeamMember.id==member_id,TeamMember.project_id==pid,TeamMember.active.is_(True)))
        if not member:raise HTTPException(404,'Integrante no disponible en este proyecto.')
        from .fidelity import activity
        from .network_service import aware
        from .news_review import iso_utc
        packet=activity(session,pid,actor_id=actor_id,network=network,account_url=account_url,start=start,end=end)
        summary=team_dashboard(session,pid,actor_id=actor_id,network=network,account_url=account_url,start=start,end=end)
        row=next(r for r in summary['rows'] if r['member_id']==member_id)
        posts={(p['network'],p['url']):p for p in packet['publications']}
        observed=session.scalars(select(TeamObservation).where(TeamObservation.project_id==pid,TeamObservation.member_id==member_id,
            TeamObservation.actor_id==packet['actor_id'],TeamObservation.post_url.in_([k[1] for k in posts])).order_by(TeamObservation.observed_at.desc()).limit(20001)).all() if packet['actor_id'] else []
        if len(observed)>20000:raise HTTPException(422,'Acota el periodo de la ficha.')
        grouped={}
        for event in observed:
            key=(event.network,event.post_url)
            if key not in posts:continue
            group=grouped.setdefault(key,dict(network=event.network,url=event.post_url,text=posts[key]['text'],published_at=posts[key]['published_at'],
                reaction_recorded=False,comment_recorded=False,identified_comments=0,last_observed=iso_utc(aware(event.observed_at))))
            if event.kind=='reaction':group['reaction_recorded']=True
            if event.kind in ('comment','reply','comment_presence'):group['comment_recorded']=True
            if event.kind in ('comment','reply'):group['identified_comments']+=1
        links=[]
        for n,k in json.loads(member.profiles_json).items():
            if n=='facebook':url='https://facebook.com/profile.php?id='+k[3:] if k.startswith('id:') else 'https://facebook.com/'+k
            else:url='https://'+{'instagram':'instagram.com/','tiktok':'tiktok.com/@','x':'x.com/'}[n]+k
            links.append(dict(network=n,url=url))
        items=list(grouped.values());size=20
        return dict(project_id=pid,member_id=member_id,name=member.display_name,accounts=links,summary=row,
            actor_id=packet['actor_id'],actor_name=packet['actor_name'],window=packet['window'],items=items[(page-1)*size:page*size],
            page=page,page_size=size,total_publications=len(items),external_calls=0,
            basis='Acciones observadas de un integrante registrado; no se deducen opiniones ni se inventan comentarios.')

    @app.get('/api/projects/{pid}/continuity/team/roster')
    def roster(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        owner(pid,user,session)
        rows=session.scalars(select(TeamMember).where(TeamMember.project_id==pid).order_by(TeamMember.active.desc(),TeamMember.id).limit(501)).all()
        return dict(items=[dict(id=m.id,name=m.display_name,profiles=json.loads(m.profiles_json),active=m.active) for m in rows[:500]],bounded=len(rows)>500)

    @app.get('/api/projects/{pid}/continuity/team/template')
    def template(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        owner(pid,user,session)
        text='Código,Nombre,Facebook,Instagram,TikTok,X\r\nE001,Colaborador de ejemplo,equipo.ejemplo,equipo.ejemplo,,\r\n'
        return dict(filename='NEXO_Equipo_Plantilla.csv',csv_text='\ufeff'+text)

    @app.post('/api/projects/{pid}/continuity/team/roster/import')
    async def ingest_roster(pid:int,file:UploadFile=File(...),sheet:str=Form(default=''),user=Depends(current_user),session:Session=Depends(db)):
        owner(pid,user,session);raw=await file.read(2*1024*1024+1);await file.close()
        try:records=parse_roster(raw,file.filename or '',sheet)
        except (ValueError,UnicodeError) as exc:raise HTTPException(422,str(exc)) from None
        return save_records(pid,records,hashlib.sha256(raw).hexdigest(),user,session,'fidelity.team_roster',20)

    @app.patch('/api/projects/{pid}/continuity/team/{member_id}')
    def change_state(pid:int,member_id:int,body:TeamState,user=Depends(current_user),session:Session=Depends(db)):
        owner(pid,user,session);lock_project(session,pid)
        m=session.scalar(select(TeamMember).where(TeamMember.id==member_id,TeamMember.project_id==pid))
        if not m:raise HTTPException(404,'Integrante no disponible.')
        if body.active and not m.active:
            profiles=json.loads(m.profiles_json)
            others=session.scalars(select(TeamMember).where(TeamMember.project_id==pid,TeamMember.id!=m.id,TeamMember.active.is_(True))).all()
            if len(others)>=500:raise HTTPException(422,'Máximo 500 integrantes activos.')
            if any(any(json.loads(o.profiles_json).get(n)==p for n,p in profiles.items()) for o in others):
                raise HTTPException(409,'Una cuenta ya está asignada a otro integrante.')
        m.active=body.active;m.updated_by=user.id
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='fidelity.team_state',target='member:'+str(m.id)))
        session.commit();return dict(id=m.id,active=m.active)

    @app.post('/api/projects/{pid}/continuity/team/events')
    def ingest_events(pid:int,body:TeamEvents,user=Depends(current_user),session:Session=Depends(db)):
        owner(pid,user,session)
        if len(body.model_dump_json().encode())>1_000_000:raise HTTPException(422,'Máximo 1 MB de actividad del equipo.')
        _,posts=registered_posts(session,pid,body.actor_id)
        members={m.id:m for m in session.scalars(select(TeamMember).where(TeamMember.project_id==pid,TeamMember.active.is_(True))).all()}
        now=datetime.now(timezone.utc)
        for e in body.events:
            if e.member_id not in members:raise HTTPException(422,'Integrante ajeno o inactivo.')
            if e.network not in json.loads(members[e.member_id].profiles_json):raise HTTPException(422,'El integrante no tiene esa red registrada.')
            if (e.network,e.post_url) not in posts:raise HTTPException(422,'Incorpora primero las publicaciones de la cuenta de este actor.')
            if e.observed_at>now or e.observed_at<datetime.fromisoformat(posts[(e.network,e.post_url)]['published_at']):
                raise HTTPException(422,'La observación debe ser posterior a la publicación y no estar en el futuro.')
        take_quota(session,pid,'fidelity.team_events',30);lock_project(session,pid)
        inserted=duplicates=0
        try:
            for e in body.events:
                key=hashlib.sha256(e.event_id.encode()).hexdigest() if e.kind in ('comment','reply') else ''
                row=session.scalar(select(TeamObservation).where(TeamObservation.project_id==pid,TeamObservation.member_id==e.member_id,
                    TeamObservation.actor_id==body.actor_id,TeamObservation.network==e.network,TeamObservation.post_url==e.post_url,
                    TeamObservation.kind==e.kind,TeamObservation.source_key==key))
                if row:
                    from .network_service import aware
                    if aware(row.observed_at)<e.observed_at:row.observed_at=e.observed_at
                    duplicates+=1
                else:
                    session.add(TeamObservation(project_id=pid,member_id=e.member_id,actor_id=body.actor_id,is_demo=False,
                        network=e.network,post_url=e.post_url,kind=e.kind,source_key=key,observed_at=e.observed_at,source_kind='local_import'));session.flush();inserted+=1
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='fidelity.team_activity',target=f'new:{inserted}:same:{duplicates}'))
            session.commit();return dict(inserted=inserted,duplicates=duplicates,external_calls=0)
        except Exception:session.rollback();raise
