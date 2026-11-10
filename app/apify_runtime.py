"""Durable, owner-authorized Facebook collection. Reserves cost before any POST.
One short tick starts OR observes one remote run. Unknown starts are never replayed.
"""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import json,uuid
from zoneinfo import ZoneInfo
from pydantic import Field,model_validator
from fastapi import HTTPException
from sqlalchemy import select
from .apify_port import Strict
from .apify_catalog import BY_KEY,ExecutionInput
from .configuration import IntegrationSetting,secret_cipher,MediaOutlet
from .actor_models import ActorProfile
from .pulse_models import PulseActor
from .models import User,Project,AuditEvent
from .refresh_models import ProjectRefreshRun as Run
from .client_access import is_owner
from .actors_api import lock_project
from .apify_http import ApifyHTTP,ProviderError,ident
from .facebook_ingest import ingest,fburl

KEYS=('facebook.posts','facebook.profile','facebook.comments','facebook.reactions')
ZONE=ZoneInfo('America/Mexico_City')
def now():return datetime.now(timezone.utc)
def encode(value):return json.dumps(value,ensure_ascii=False)


def settings(row):return json.loads(row.config_json) if row else {}
def execution(config):return ExecutionInput(**{**config.get('_apify_execution',{}),'expected_version':0})
def public_execution(config):
 policy=execution(config);month=now().astimezone(ZONE).strftime('%Y-%m')
 reserved=sum(int(e['cents']) for e in config.get('_apify_ledger',[]) if e['month']==month)
 return dict(**policy.model_dump(mode='json',exclude={'expected_version'}),reserved_this_month_usd=f'{reserved/100:.2f}',supported_processes=list(KEYS),verified_at=config.get('_apify_verified_at'))

def pending_test(session,pid):
 config=settings(session.get(IntegrationSetting,(pid,'apify')))
 return execution(config).mode=='test' and not any(e.get('test') for e in config.get('_apify_ledger',[]))

def targets(session,pid,limit):
 rows=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.active.is_(True),PulseActor.is_demo.is_(False)).order_by(PulseActor.kind.desc(),PulseActor.id)).all();out=[]
 for actor in rows:
  profile=session.scalar(select(ActorProfile).where(ActorProfile.actor_id==actor.id,ActorProfile.project_id==pid))
  for c in json.loads(profile.channels_json) if profile else []:
   if c['network']=='facebook' and c.get('enabled',True):out.append(dict(actor_id=actor.id,media_id=None,url=c['url'],name=actor.name))
 for m in session.scalars(select(MediaOutlet).where(MediaOutlet.project_id==pid,MediaOutlet.active.is_(True)).order_by(MediaOutlet.id)).all():
  for c in json.loads(m.channels_json):
   if c['network']=='facebook' and c.get('enabled',True):out.append(dict(actor_id=None,media_id=m.id,url=c['url'],name=m.name))
 unique={}
 for t in out:
  key=fburl(t['url'])
  if key in unique:raise ProviderError('ambiguous_registered_account')
  unique[key]=t
 return list(unique.values())[:limit],len(unique)>limit

def initialize(session,pid,trigger):
 row=session.get(IntegrationSetting,(pid,'apify'));config=settings(row);policy=execution(config)
 if policy.mode=='paused':return dict(state='paused',jobs=[],message='Apify está pausado.')
 if trigger=='daily' and policy.mode=='test':return dict(state='paused',jobs=[],message='La prueba se ejecuta solo con el botón del administrador.')
 if not row or not row.secrets_ciphertext:return dict(state='blocked',jobs=[],message='Falta guardar el token de Apify.')
 if config.get('base_url') not in ('','https://api.apify.com','https://api.apify.com/','https://api.apify.com/v2','https://api.apify.com/v2/'):
  return dict(state='blocked',jobs=[],message='La dirección de Apify debe ser https://api.apify.com/v2.')
 try:accounts,bounded=targets(session,pid,policy.account_limit)
 except (ValueError,ProviderError):return dict(state='blocked',jobs=[],message='Revisa las cuentas registradas del proyecto.')
 if not accounts:return dict(state='blocked',jobs=[],message='Registra una cuenta pública de Facebook en Actores o Medios.')
 selected=config.get('apify_processes',{});keys=['facebook.posts'] if policy.mode=='test' else [k for k in KEYS if selected.get(k,{}).get('selected')]
 jobs=[]
 for key in keys:
  plan=selected.get(key,{})
  if key=='facebook.posts' and policy.mode=='test':plan={**plan,'max_items':3,'daily_limit':1}
  chosen=[t for t in accounts if t.get('actor_id')] if key=='facebook.profile' else accounts
  jobs.append(dict(key=key,state='todo',actor_ref=BY_KEY[key]['actor_ref'],max_items=plan.get('max_items',20),daily_limit=plan.get('daily_limit',1),targets=chosen if key in KEYS[:2] else [],since=(now()-timedelta(days=7)).isoformat()))
 return dict(state='running' if jobs else 'blocked',jobs=jobs,posts=[],test=policy.mode=='test',accounts_bounded=bounded,message='' if jobs else 'Selecciona los procesos de Facebook para este proyecto.')

def build_input(job):
 urls=[t['url'] for t in job['targets']]
 if job['key']=='facebook.reactions':return dict(postUrls=urls,reactionType='ALL',resultsLimit=job['max_items'])
 body=dict(startUrls=[dict(url=u) for u in urls])
 if job['key']=='facebook.posts':body.update(resultsLimit=job['max_items'],onlyPostsNewerThan=job['since'],captionText=False)
 if job['key']=='facebook.comments':body.update(resultsLimit=job['max_items'],includeNestedComments=False,viewOption='RECENT_ACTIVITY')
 return body

def reserve(session,row,config,packet,job):
 policy=execution(config);at=now().astimezone(ZONE);month=at.strftime('%Y-%m');day=at.date().isoformat();ledger=config.get('_apify_ledger',[])
 if policy.mode=='paused':raise ProviderError('execution_paused')
 if packet['test'] and (policy.mode!='test' or any(e.get('test') for e in ledger)):raise ProviderError('test_already_reserved')
 if not packet['test'] and not config.get('apify_processes',{}).get(job['key'],{}).get('selected'):raise ProviderError('process_deselected')
 if not packet['test']:
  current=config.get('apify_processes',{}).get(job['key'],{})
  job['daily_limit']=min(job['daily_limit'],current.get('daily_limit',0));job['max_items']=min(job['max_items'],current.get('max_items',20))
 if len(job['targets'])>policy.account_limit:raise ProviderError('account_limit_changed')
 cap=int(policy.per_run_usd*100)
 if cap<=0 or sum(int(e['cents']) for e in ledger if e['month']==month)+cap>int(policy.monthly_budget_usd*100):raise ProviderError('monthly_budget_exhausted')
 limit=job['daily_limit']
 if limit<=0 or sum(e['key']==job['key'] and e['day']==day for e in ledger)>=limit:raise ProviderError('process_daily_limit')
 # Historical reservations stay conservative even if a request fails or is ambiguous.
 if len(ledger)>=5000:raise ProviderError('ledger_review_required')
 ledger.append(dict(key=job['key'],day=day,month=month,cents=cap,refresh_id=row.id,test=packet['test']))
 config['_apify_ledger']=ledger;job.update(state='dispatching',cap_usd=str(policy.per_run_usd),started_at=now().isoformat());return policy

def token_for(row):
 try:token=json.loads(secret_cipher().decrypt(row.secrets_ciphertext.encode())).get('api_token','')
 except Exception:raise ProviderError('credential_decryption') from None
 if not token or '\n' in token or '\r' in token:raise ProviderError('invalid_token_format')
 return token

def finalize(row,result):
 packet=result.get('apify',{});jobs=packet.get('jobs',[])
 if any(j['state'] in ('todo','dispatching','waiting','fetching') for j in jobs):return
 if packet.get('state')=='running':packet['state']='succeeded' if all(j['state']=='succeeded' for j in jobs) else 'partial'
 good=sum(s.get('status')=='ok' for s in result.get('sources',[]))+sum(j['state']=='succeeded' for j in jobs)
 bad=sum(s.get('status')=='failed' for s in result.get('sources',[]))+sum(j['state']!='succeeded' or bool(j.get('warning')) for j in jobs)+(packet.get('state')=='blocked')
 row.status=('partial' if bad else 'succeeded') if good else 'failed';row.active_key=None;row.finished_at=now()

def advance(sessions,run_id,uid,client_factory=ApifyHTTP):
 lease=uuid.uuid4().hex;client=None;operation=None
 with sessions() as s:
  s.info['nexo.actor_id']=str(uid);user=s.get(User,uid)
  if not user or not is_owner(s,user):return
  row=s.get(Run,run_id)
  if not row or row.requested_by!=uid or row.status!='running':return
  lock_project(s,row.project_id);s.refresh(row);result=json.loads(row.result_json);packet=result.get('apify',{})
  if not packet.get('jobs'):return
  if date_utc(result.get('lease_until'))>now():return
  # A process stopped between reserving and storing the run ID cannot be retried.
  for j in packet['jobs']:
   if j['state']=='dispatching':j.update(state='failed',error='ambiguous_start_no_retry')
   if j['state']=='fetching':j['state']='waiting'
  ready=lambda j:j['state']=='todo' and (j['key'] in KEYS[:2] or any(p['key']=='facebook.posts' and p['state']=='succeeded' for p in packet['jobs']))
  job=next((j for j in packet['jobs'] if ready(j)),None) or next((j for j in packet['jobs'] if j['state']=='waiting'),None) or next((j for j in packet['jobs'] if j['state']=='todo'),None)
  if not job:finalize(row,result);row.result_json=encode(result);s.commit();return
  setting=s.get(IntegrationSetting,(row.project_id,'apify'));config=settings(setting)
  try:
   project=s.get(Project,row.project_id)
   if not project or project.status!='active':raise ProviderError('project_inactive')
   if job['state']=='todo':
    if job['key'] in KEYS[2:]:
     # One recent post per observed account, at most five URLs (Free-compatible).
     picked={}
     for t in sorted(packet.get('posts',[]),key=lambda t:t['published_at'],reverse=True):picked.setdefault(t['account_url'],t)
     job['targets']=list(picked.values())[:5]
    if not job['targets']:job.update(state='skipped',error='no_posts_for_process');raise ProviderError('no_posts_for_process')
    # Revalidate configured accounts at dispatch, never borrow from another project.
    current,_=targets(s,row.project_id,5);known={(t.get('actor_id'),t.get('media_id'),fburl(t['url'])) for t in current}
    if any((t.get('actor_id'),t.get('media_id'),fburl(t.get('account_url',t['url']))) not in known for t in job['targets']):raise ProviderError('account_no_longer_registered')
    reserve(s,row,config,packet,job);setting.config_json=encode(config);operation='start'
   else:
    if now()-date_utc(job['started_at'])>timedelta(minutes=12):raise ProviderError('remote_run_expired')
    operation='observe'
   credential=token_for(setting)
  except ProviderError as exc:
   if job['state']!='skipped':job.update(state='failed',error=exc.code)
   finalize(row,result);row.result_json=encode(result);s.commit();return
  result.update(lease_id=lease,lease_until=(now()+timedelta(seconds=50)).isoformat());row.result_json=encode(result);s.commit();pid=row.project_id
 try:
  client=client_factory(credential);credential=''
  if operation=='start':
   remote=client.start(job['actor_ref'],build_input(job),job['cap_usd'],min(500,job['max_items']*len(job['targets'])))
   job.update(run_id=ident(remote['id']),dataset_id=ident(remote['defaultDatasetId']),state='waiting')
   rows=None
  else:
   remote=client.run(job['run_id']);rows=None
   if ident(remote['id'])!=job['run_id'] or ident(remote['defaultDatasetId'])!=job['dataset_id']:raise ProviderError('remote_reference_changed')
   if remote['status'] in ('SUCCEEDED','TIMED-OUT','ABORTED'):
    rows=client.items(job['dataset_id'],min(500,job['max_items']*len(job['targets'])))
   elif remote['status'] in ('FAILED','TIMING-OUT','ABORTING'):raise ProviderError('remote_'+remote['status'].lower())
  failure=None
 except ProviderError as exc:failure=exc.code;remote=None;rows=None
 except Exception:failure='provider_invalid_contract';remote=None;rows=None
 finally:
  if client:client.close()
 with sessions() as s:
  s.info['nexo.actor_id']=str(uid);user=s.get(User,uid)
  if not user or not is_owner(s,user):return
  row=s.get(Run,run_id);lock_project(s,pid);s.refresh(row);result=json.loads(row.result_json)
  if row.status!='running' or result.get('lease_id')!=lease:return
  packet=result['apify'];stored=next(j for j in packet['jobs'] if j['key']==job['key'])
  if failure:
   # GET failures can be retried; POST failures remain ambiguous and are never repeated.
   if operation=='start':stored.update(state='failed',error=failure)
   else:stored['last_poll_error']=failure
  elif operation=='start':
   stored.update(job);result['paid_provider_runs']=result.get('paid_provider_runs',0)+1
   setting=s.get(IntegrationSetting,(pid,'apify'));config=settings(setting);config['_apify_verified_at']=now().isoformat();setting.config_json=encode(config)
  elif rows is not None:
   try:
    at=date_utc(stored.get('captured_at')) if stored.get('captured_at') else now();stored['captured_at']=at.isoformat()
    # Persist the capture identity BEFORE the established importer commits.
    stored['state']='fetching';row.result_json=encode(result);s.commit()
    current,_=targets(s,pid,5);known={(t.get('actor_id'),t.get('media_id'),fburl(t['url'])) for t in current}
    if any((t.get('actor_id'),t.get('media_id'),fburl(t.get('account_url',t['url']))) not in known for t in stored['targets']):raise ProviderError('account_no_longer_registered')
    stats,posts=ingest(s,pid,uid,stored,rows,at);stored.update(state='succeeded',stats=stats,remote_status=remote['status']);packet['posts'].extend(posts)
    if stats['rejected'] or remote['status']!='SUCCEEDED':stored['warning']='partial_provider_output'
   except Exception:
    s.rollback();row=s.get(Run,run_id);lock_project(s,pid);s.refresh(row);result=json.loads(row.result_json);packet=result['apify'];stored=next(j for j in packet['jobs'] if j['key']==job['key']);stored.update(state='failed',error='dataset_ingestion_failed')
  result.pop('lease_id',None);result.pop('lease_until',None);finalize(row,result);row.result_json=encode(result)
  s.add(AuditEvent(project_id=pid,user_id=uid,action='apify.tick',target=stored['key']+':'+stored['state']));s.commit()

def date_utc(value):
 if not value:return datetime.min.replace(tzinfo=timezone.utc)
 d=datetime.fromisoformat(value.replace('Z','+00:00'));return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
