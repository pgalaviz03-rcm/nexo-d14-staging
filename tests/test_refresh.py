from datetime import datetime,timedelta,timezone
import json
import pytest
from fastapi import HTTPException,BackgroundTasks
from sqlalchemy import select,func
from app.models import FeedSource
from app.refresh_models import ProjectRefreshRun as Run
from app.refresh_service import next_cut,daily_key,admit,status,execute_run
from app.refresh_oidc import verify_scheduler,ISSUER
from test_manual_reviews import archive,endpoint
from test_fidelity import owner

NOW=datetime(2026,11,10,14,0,tzinfo=timezone.utc)
def test_next_cut_and_due_slot_use_aguascalientes():
 assert next_cut(NOW-timedelta(seconds=1))==NOW
 assert next_cut(NOW)==NOW+timedelta(days=1)
 assert daily_key(NOW-timedelta(seconds=1))is None
 assert daily_key(NOW)=='daily:2026-11-10'
@pytest.mark.parametrize('month',[1,4,7,11])
def test_daily_is_1400_utc_throughout_year(month):
 n=datetime(2026,month,3,13,tzinfo=timezone.utc)
 assert next_cut(n).hour==14

def test_reader_cannot_admit_even_legacy_admin(archive):
 a=archive
 with pytest.raises(HTTPException)as e:admit(a[1],a[2].id,a[4][0],now=NOW)
 assert e.value.status_code==403

def test_daily_idempotent_and_shared_across_users(archive):
 a=archive;owner(a);one,new=admit(a[1],a[2].id,a[4][0],'daily',NOW);two,again=admit(a[1],a[2].id,a[4][0],'daily',NOW)
 assert new and not again and one.id==two.id
 one.status='succeeded';one.active_key=None;one.finished_at=NOW;a[1].commit()
 same,new=admit(a[1],a[2].id,a[4][0],'daily',NOW+timedelta(hours=4));assert same.id==one.id and not new
 assert status(a[1],a[2].id,False,NOW)['last_completed_at']==NOW.isoformat()

def test_no_refresh_before_0800(archive):
 a=archive;owner(a);assert admit(a[1],a[2].id,a[4][0],'daily',NOW-timedelta(seconds=1))==(None,False)

def test_manual_deduplicates_active_and_throttles_completed(archive):
 a=archive;owner(a);one,new=admit(a[1],a[2].id,a[4][0],now=NOW);two,new=admit(a[1],a[2].id,a[4][0],now=NOW);assert one.id==two.id and not new
 one.status='succeeded';one.active_key=None;one.finished_at=NOW;a[1].commit()
 with pytest.raises(HTTPException)as e:admit(a[1],a[2].id,a[4][0],now=NOW+timedelta(minutes=1))
 assert e.value.status_code==429

def test_abandoned_daily_is_not_replayed(archive):
 a=archive;owner(a);one,new=admit(a[1],a[2].id,a[4][0],'daily',NOW)
 same,new=admit(a[1],a[2].id,a[4][0],'daily',NOW+timedelta(minutes=11));assert same.id==one.id and not new and same.status=='interrupted'

def test_worker_uses_project_scoped_feeds_once(archive):
 a=archive;owner(a);s=a[1];s.add_all([FeedSource(project_id=a[2].id,created_by=a[4][0].id,title='Own',url='https://example.org/rss'),FeedSource(project_id=a[3].id,created_by=a[4][3].id,title='Other',url='https://other.example/rss')]);s.commit()
 run,_=admit(s,a[2].id,a[4][0],'daily',NOW);calls=[]
 def fetch(**kwargs):calls.append((kwargs['pid'],kwargs['fid']));return dict(inserted=2)
 execute_run(a[0].state.SessionLocal,run.id,a[4][0].id,fetch);execute_run(a[0].state.SessionLocal,run.id,a[4][0].id,fetch)
 s.expire_all();saved=s.get(Run,run.id);assert saved.status=='succeeded'and len(calls)==1 and calls[0][0]==a[2].id
 assert json.loads(saved.result_json)['paid_provider_runs']==0

def test_partial_failure_retains_success_and_redacts_exception(archive):
 a=archive;owner(a);s=a[1]
 s.add_all([FeedSource(project_id=a[2].id,created_by=a[4][0].id,title=str(i),url='https://example.org/'+str(i))for i in range(2)]);s.commit()
 run,_=admit(s,a[2].id,a[4][0],'daily',NOW);calls=[]
 def fetch(**kwargs):
  calls.append(1)
  if len(calls)==1:raise RuntimeError('secret-token-never-persist')
  return dict(inserted=1)
 execute_run(a[0].state.SessionLocal,run.id,a[4][0].id,fetch);s.expire_all();r=s.get(Run,run.id)
 assert r.status=='partial'and'secret-token'not in r.result_json

def test_revoked_owner_cannot_run_queued_job(archive):
 from app.pulse_models import PlatformGrant
 a=archive;owner(a);run,_=admit(a[1],a[2].id,a[4][0],'daily',NOW);g=a[1].get(PlatformGrant,a[4][0].id);g.active=False;a[1].commit()
 execute_run(a[0].state.SessionLocal,run.id,a[4][0].id,lambda **k:pytest.fail('must not call provider'))
 a[1].expire_all();assert a[1].get(Run,run.id).status=='queued'

def test_read_status_does_not_collect_or_expose_results(archive):
 a=archive;owner(a);run,_=admit(a[1],a[2].id,a[4][0],'daily',NOW);before=a[1].scalar(select(func.count()).select_from(Run))
 p=status(a[1],a[2].id,False,NOW);assert not p['can_refresh']and'result_json'not in p and p['running']
 assert a[1].scalar(select(func.count()).select_from(Run))==before

@pytest.fixture
def signed():
 import jwt,time
 from cryptography.hazmat.primitives.asymmetric import rsa
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048);jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()));jwk.update(kid='test',alg='RS256')
 cfg=dict(repository='owner/repo',repository_id='42',operator_id=1,audience='https://nexo.example/internal/daily-refresh')
 n=int(time.time());claims=dict(iss=ISSUER,aud=cfg['audience'],sub='repo:owner/repo:ref:refs/heads/main',iat=n,nbf=n-1,exp=n+300,repository='owner/repo',repository_id='42',ref='refs/heads/main',workflow_ref='owner/repo/.github/workflows/daily-refresh.yml@refs/heads/main',event_name='schedule')
 def token(**changes):return'Bearer '+jwt.encode(dict(claims,**changes),key,algorithm='RS256',headers={'kid':'test'})
 return cfg,[jwk],token

def test_signed_scheduler_accepts_only_expected_repo_workflow(signed):
 cfg,keys,token=signed;assert verify_scheduler(token(),cfg,keys)==1
@pytest.mark.parametrize('change',[{'repository_id':'43'},{'ref':'refs/heads/feature'},{'event_name':'pull_request'},{'aud':'https://attacker.invalid'},{'workflow_ref':'owner/repo/.github/workflows/other.yml@refs/heads/main'},{'exp':1}])
def test_signed_scheduler_rejects_other_scopes(signed,change):
 cfg,keys,token=signed
 with pytest.raises(HTTPException)as e:verify_scheduler(token(**change),cfg,keys)
 assert e.value.status_code==401

def test_manual_daily_cap_cannot_be_bypassed_by_spacing(archive):
 a=archive;owner(a)
 for h in [0,2]:
  row,_=admit(a[1],a[2].id,a[4][0],now=NOW+timedelta(hours=h));row.status='succeeded';row.active_key=None;row.finished_at=NOW+timedelta(hours=h);a[1].commit()
 with pytest.raises(HTTPException)as e:admit(a[1],a[2].id,a[4][0],now=NOW+timedelta(hours=4))
 assert e.value.status_code==429

def test_next_day_gets_a_new_shared_cut(archive):
 a=archive;owner(a);first,_=admit(a[1],a[2].id,a[4][0],'daily',NOW);first.status='succeeded';first.active_key=None;first.finished_at=NOW;a[1].commit()
 second,new=admit(a[1],a[2].id,a[4][0],'daily',NOW+timedelta(days=1));assert new and first.id!=second.id
