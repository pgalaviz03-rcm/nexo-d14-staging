"""Daily 08:00 America/Mexico_City project cuts; bounded owner-only manual runs.
No paid provider is invoked by this release. RSS reuses the validated SSRF port.
"""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import json,uuid
from sqlalchemy import select,update,func,text
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from .models import Project,User,FeedSource,AuditEvent
from .refresh_models import ProjectRefreshRun as Run
from .client_access import is_owner
from .actors_api import lock_project
from .controls import take_quota

ZONE=ZoneInfo('America/Mexico_City')
def utc(dt):return dt.replace(tzinfo=timezone.utc)if dt.tzinfo is None else dt.astimezone(timezone.utc)
def now_utc():return datetime.now(timezone.utc)
def next_cut(now):
 local=utc(now).astimezone(ZONE);slot=local.replace(hour=8,minute=0,second=0,microsecond=0)
 if slot<=local:slot+=timedelta(days=1)
 return slot.astimezone(timezone.utc)
def daily_key(now):
 local=utc(now).astimezone(ZONE)
 return 'daily:'+local.date().isoformat() if local.hour>=8 else None

def available(session):
 if session.bind.dialect.name!='postgresql':return True
 return session.execute(text('select version_num from alembic_version')).scalar()=='012_project_refresh'

def status(session,pid,can_refresh=False,now=None):
 now=now or now_utc()
 if not available(session):return dict(can_refresh=False,daily_time='08:00',timezone=str(ZONE),next_scheduled_for=next_cut(now).isoformat(),last_completed_at=None,last_status=None,running=False)
 last=session.scalar(select(Run).where(Run.project_id==pid).order_by(Run.id.desc()).limit(1))
 done=session.scalar(select(Run).where(Run.project_id==pid,Run.status.in_(['succeeded','partial'])).order_by(Run.finished_at.desc()).limit(1))
 active=session.scalar(select(Run.id).where(Run.project_id==pid,Run.active_key=='active'))
 return dict(can_refresh=can_refresh,daily_time='08:00',timezone=str(ZONE),next_scheduled_for=next_cut(now).isoformat(),
  last_completed_at=utc(done.finished_at).isoformat() if done else None,last_status=last.status if last else None,
  running=bool(active),source_scope=['rss'],paid_provider_runs=0)

def admit(session,pid,user,trigger='manual',now=None):
 now=now or now_utc()
 if not is_owner(session,user):raise HTTPException(403,'Solo el superadministrador puede actualizar datos.')
 project=session.get(Project,pid)
 if not project or project.status!='active':raise HTTPException(404,'Proyecto no disponible.')
 if not available(session):raise HTTPException(409,'La actualización se está preparando. Intenta más tarde.')
 key=daily_key(now)if trigger=='daily'else 'manual:'+uuid.uuid4().hex
 if key is None:return None,False
 lock_project(session,pid)
 active=session.scalar(select(Run).where(Run.project_id==pid,Run.active_key=='active'))
 if active:
  if utc(active.created_at)>utc(now)-timedelta(minutes=10):return active,False
  # Never replay an ambiguous/abandoned execution automatically.
  active.status='interrupted';active.active_key=None;active.finished_at=now;session.flush()
 previous=session.scalar(select(Run).where(Run.project_id==pid,Run.slot_key==key))
 if previous:return previous,False
 if trigger=='manual':
  recent=session.scalar(select(Run.id).where(Run.project_id==pid,Run.trigger=='manual',Run.created_at>now-timedelta(hours=1)))
  if recent:raise HTTPException(429,'Ya se solicitó una actualización. Espera una hora antes de iniciar otra.')
  # Admission persists separately; failed attempts also consume the daily cap.
  session.commit();take_quota(session,pid,'refresh.manual',2);lock_project(session,pid)
 row=Run(project_id=pid,slot_key=key,trigger=trigger,requested_by=user.id,status='queued',active_key='active',created_at=now)
 try:
  session.add(row);session.flush();session.add(AuditEvent(project_id=pid,user_id=user.id,action='refresh.request',target=trigger+':'+str(row.id)));session.commit();return row,True
 except IntegrityError:
  session.rollback();existing=session.scalar(select(Run).where(Run.project_id==pid,Run.active_key=='active'))
  if existing:return existing,False
  raise HTTPException(409,'Otra actualización ya está registrada.')from None

def owner_session(sessions,uid):
 s=sessions();s.info['nexo.actor_id']=str(uid)
 user=s.get(User,uid)
 if not user or not is_owner(s,user):s.close();raise HTTPException(403,'Operador de actualización no autorizado.')
 return s,user

def execute_run(sessions,run_id,uid,refresh_feed):
 with sessions()as s:
  s.info['nexo.actor_id']=str(uid);user=s.get(User,uid)
  if not user or not is_owner(s,user):return
  row=s.get(Run,run_id)
  if not row or row.requested_by!=uid:return
  pid=row.project_id
  claimed=s.execute(update(Run).where(Run.id==run_id,Run.project_id==pid,Run.status=='queued').values(status='running',started_at=now_utc())).rowcount
  s.commit()
  if claimed!=1:return
  feeds=s.scalars(select(FeedSource.id).where(FeedSource.project_id==pid,FeedSource.status!='paused').order_by(FeedSource.id).limit(5)).all()
 results=[]
 for fid in feeds:
  try:
   s,user=owner_session(sessions,uid)
   with s:
    # Revalidate the project at execution time; a queued job cannot cross projects.
    p=s.get(Project,pid)
    if not p or p.status!='active':raise HTTPException(404,'Proyecto no disponible.')
    packet=refresh_feed(pid=pid,fid=fid,user=user,session=s)
    results.append(dict(source_id=fid,status='ok',inserted=packet['inserted']))
  except Exception:
   results.append(dict(source_id=fid,status='failed',inserted=0))
 good=sum(x['status']=='ok'for x in results)
 state=('succeeded'if good==len(results)else'partial')if good else'failed'
 with sessions()as s:
  s.info['nexo.actor_id']=str(uid);user=s.get(User,uid)
  if not user or not is_owner(s,user):return
  s.execute(update(Run).where(Run.id==run_id,Run.project_id==pid,Run.status=='running').values(status=state,active_key=None,finished_at=now_utc(),result_json=json.dumps(dict(sources=results,scope=['rss'],paid_provider_runs=0))))
  s.add(AuditEvent(project_id=pid,user_id=uid,action='refresh.complete',target=str(run_id)+':'+state));s.commit()
