import json
from datetime import timedelta
import pytest,httpx
from pydantic import ValidationError
from sqlalchemy import select,func
from app.apify_http import ApifyHTTP,ProviderError
from app.apify_catalog import ExecutionInput,BY_KEY
from app.apify_runtime import initialize,advance,now,public_execution,settings
from app.configuration import IntegrationSetting
from app.refresh_models import ProjectRefreshRun as Run
from app.refresh_service import admit,status
from app.pulse_models import PulseDocument,PulseAccount,PulseMention,PlatformGrant
from app.fidelity import FidelityCapture
from app.fidelity_team import TeamObservation
from test_manual_reviews import archive,endpoint
from test_networks import setup,URL
from test_fidelity import owner
from test_fidelity_team import roster
from test_configuration import save,SECRET

def prepare(a,mode='scheduled',keys=None,monthly='1.00',cap='.10'):
 actor=setup(a);owner(a);roster(a)
 plans={k:dict(actor_ref=BY_KEY[k]['actor_ref'],selected=True,max_items=3,daily_limit=1) for k in keys or ('facebook.posts','facebook.profile','facebook.comments','facebook.reactions')}
 save(a,secrets={'api_token':SECRET},apify_processes=plans,apify_execution=dict(mode=mode,monthly_budget_usd=monthly,per_run_usd=cap,account_limit=1))
 row,_=admit(a[1],a[2].id,a[4][0]);row.status='running';row.result_json=json.dumps(dict(sources=[],scope=['facebook'],paid_provider_runs=0,apify=initialize(a[1],a[2].id,'manual')));a[1].commit();return actor,row.id

class FakeClient:
 starts=[];remote={};calls=[]
 def __init__(self,token):assert token==SECRET
 def close(self):pass
 def start(self,actor,body,cap,limit):
  n=str(len(self.starts)+1);self.starts.append((actor,body,cap,limit));self.remote[n]=actor
  return dict(id='run'+n,defaultDatasetId='dataset'+n,status='RUNNING')
 def run(self,rid):return dict(id=rid,defaultDatasetId='dataset'+rid.removeprefix('run'),status='SUCCEEDED')
 def items(self,did,limit):
  actor=self.remote[did.removeprefix('dataset')];self.calls.append(did);time=(now()-timedelta(hours=1)).isoformat();post=URL+'/posts/1'
  if actor.endswith('facebook-posts-scraper'):return [dict(inputUrl=URL,postId='1',url=post,text='Texto público de prueba',time=time,likes=4,comments=1,shares=2)]
  if actor.endswith('facebook-pages-scraper'):return [dict(pageUrl=URL,followers=123)]
  if actor.endswith('facebook-comments-scraper'):return [dict(inputUrl=post,commentId='c1',commentUrl=post+'?comment_id=c1',date=(now()-timedelta(minutes=10)).isoformat(),text='Comentario público observado',profileUrl='https://facebook.com/equipo.uno')]
  return [dict(inputUrl=post,reactorProfileUrl='https://facebook.com/equipo.uno',reactionType='like')]

@pytest.fixture(autouse=True)
def reset_fake():FakeClient.starts=[];FakeClient.remote={};FakeClient.calls=[]

def tick(a,rid,client=FakeClient):advance(a[0].state.SessionLocal,rid,a[4][0].id,client_factory=client);a[1].expire_all();return a[1].get(Run,rid)

def test_full_facebook_chain_reaches_pulse_accounts_fidelity_and_team(archive):
 a=archive;actor,rid=prepare(a)
 for _ in range(9):row=tick(a,rid)
 assert row.status=='succeeded' and row.active_key is None and len(FakeClient.starts)==4
 assert a[1].scalar(select(func.count()).select_from(PulseDocument))==2
 assert a[1].scalar(select(func.count()).select_from(PulseAccount))==1
 assert a[1].scalar(select(func.count()).select_from(FidelityCapture))==1
 assert a[1].scalar(select(func.count()).select_from(TeamObservation))==2
 assert all(m.sentiment is None and m.emotion is None for m in a[1].scalars(select(PulseMention)))
 assert [b for actor,b,cap,limit in FakeClient.starts if actor.endswith('reactions-scraper')][0]['postUrls']==[URL+'/posts/1']
 assert SECRET not in row.result_json
 tick(a,rid);assert len(FakeClient.starts)==4
 p=status(a[1],a[2].id,True);assert p['summary']==dict(rss_inserted=0,rss_failed=0,social_inserted=2,accounts=1,team_events=2)

def test_first_test_only_primary_three_posts_and_one_cost_reservation(archive):
 a=archive;_,rid=prepare(a,mode='test',monthly='.05',cap='.05')
 tick(a,rid);row=tick(a,rid)
 assert row.status=='succeeded' and len(FakeClient.starts)==1
 assert FakeClient.starts[0][1]['resultsLimit']==3 and len(FakeClient.starts[0][1]['startUrls'])==1
 config=settings(a[1].get(IntegrationSetting,(a[2].id,'apify')))
 assert public_execution(config)['reserved_this_month_usd']=='0.05'
 assert '_apify_ledger' not in save(a,expected_version=1)['settings']
 assert public_execution(settings(a[1].get(IntegrationSetting,(a[2].id,'apify'))))['reserved_this_month_usd']=='0.05'

def test_monthly_budget_is_reserved_before_request_and_never_reset_by_generic_save(archive):
 a=archive;_,rid=prepare(a,monthly='.10',cap='.10')
 for _ in range(10):row=tick(a,rid)
 assert len(FakeClient.starts)==1 and row.status=='partial'
 assert any(j.get('error')=='monthly_budget_exhausted' for j in json.loads(row.result_json)['apify']['jobs'])
 save(a,expected_version=1)
 assert public_execution(settings(a[1].get(IntegrationSetting,(a[2].id,'apify'))))['reserved_this_month_usd']=='0.10'

def test_ambiguous_post_is_not_retried_and_reservation_stays(archive):
 class Broken(FakeClient):
  attempts=0
  def start(self,*args):Broken.attempts+=1;raise ProviderError('provider_transport_or_json')
 a=archive;_,rid=prepare(a,mode='test',monthly='.05',cap='.05')
 row=tick(a,rid,Broken);row=tick(a,rid,Broken)
 assert Broken.attempts==1 and row.status=='failed' and SECRET not in row.result_json
 assert public_execution(settings(a[1].get(IntegrationSetting,(a[2].id,'apify'))))['reserved_this_month_usd']=='0.05'

def test_live_lease_prevents_duplicate_worker(archive):
 a=archive;_,rid=prepare(a);row=a[1].get(Run,rid);data=json.loads(row.result_json);data['lease_until']=(now()+timedelta(minutes=1)).isoformat();row.result_json=json.dumps(data);a[1].commit()
 tick(a,rid);assert not FakeClient.starts

def test_crash_after_reservation_never_restarts_unknown_post(archive):
 a=archive;_,rid=prepare(a,mode='test');row=a[1].get(Run,rid);data=json.loads(row.result_json);data['apify']['jobs'][0]['state']='dispatching';row.result_json=json.dumps(data);a[1].commit()
 row=tick(a,rid);assert not FakeClient.starts and row.status=='failed' and 'ambiguous_start_no_retry' in row.result_json

def test_removed_or_foreign_account_never_imported(archive):
 class Foreign(FakeClient):
  def items(self,*args):return [dict(inputUrl='https://facebook.com/foreign',postId='x',url='https://facebook.com/foreign/posts/x',time=now().isoformat(),text='Foreign')]
 a=archive;_,rid=prepare(a,mode='test');tick(a,rid,Foreign);row=tick(a,rid,Foreign)
 assert a[1].scalar(select(func.count()).select_from(PulseDocument))==0 and row.status=='partial'

def test_revoked_owner_cannot_launch_worker(archive):
 a=archive;_,rid=prepare(a);a[1].get(PlatformGrant,a[4][0].id).active=False;a[1].commit();tick(a,rid);assert not FakeClient.starts

def test_reassigned_account_cannot_receive_old_actor_results(archive):
 from app.actor_models import ActorProfile
 a=archive;aid,rid=prepare(a,mode='test');tick(a,rid)
 profile=a[1].get(ActorProfile,aid);profile.channels_json='[]';a[1].commit();row=tick(a,rid)
 assert a[1].scalar(select(func.count()).select_from(PulseDocument))==0 and row.status=='failed'

def test_pausing_policy_stops_new_starts_without_erasing_token(archive):
 a=archive;_,rid=prepare(a)
 saved=save(a,expected_version=1,apify_execution=dict(mode='paused'))
 assert saved['credentials_saved'] and not saved['runtime_enabled']
 for _ in range(5):row=tick(a,rid)
 assert not FakeClient.starts and row.status=='failed'

def test_execution_settings_cannot_be_written_by_consultor(archive):
 from fastapi import HTTPException
 a=archive;prepare(a)
 route=endpoint(a[0],'/api/projects/{pid}/settings/apify/execution','PUT')
 with pytest.raises(HTTPException) as exc:route(pid=a[2].id,body=ExecutionInput(),user=a[4][1],session=a[1])
 assert exc.value.status_code==403

def test_start_receives_only_registered_project_accounts(archive):
 a=archive;_,rid=prepare(a,mode='test',monthly='.05',cap='.05');tick(a,rid)
 urls=[v['url'] for v in FakeClient.starts[0][1]['startUrls']]
 assert urls==[URL] and FakeClient.starts[0][2]=='0.05'

@pytest.mark.parametrize('change',[dict(mode='scheduled'),dict(mode='test',per_run_usd='.20',monthly_budget_usd='1'),dict(mode='test',account_limit=2,per_run_usd='.05',monthly_budget_usd='.05'),dict(per_run_usd='2'),dict(monthly_budget_usd='-1')])
def test_unbounded_or_unfunded_policy_rejected(change):
 with pytest.raises(ValidationError):ExecutionInput(**change)

def test_paused_mode_no_provider_even_with_token(archive):
 a=archive;setup(a);owner(a);save(a,secrets={'api_token':SECRET})
 assert initialize(a[1],a[2].id,'manual')['state']=='paused' and not FakeClient.starts

def test_test_mode_cannot_be_used_by_daily_scheduler(archive):
 a=archive;prepare(a,mode='test');assert initialize(a[1],a[2].id,'daily')['state']=='paused'

def test_http_transport_fixed_origin_bearer_caps_and_no_post_retry():
 calls=[]
 def serve(r):
  calls.append(r);assert r.url.host=='api.apify.com' and r.headers['authorization']=='Bearer '+SECRET and 'token=' not in str(r.url)
  return httpx.Response(201,json={'data':dict(id='r1',defaultDatasetId='d1')})
 c=ApifyHTTP(SECRET,httpx.MockTransport(serve));c.start('apify/facebook-posts-scraper',{'startUrls':[]},'.05',3);c.close()
 assert len(calls)==1 and calls[0].url.params['maxTotalChargeUsd']=='.05' and calls[0].url.params['restartOnError']=='false'

@pytest.mark.parametrize('code',[302,401,403,429,500])
def test_provider_errors_redacted_and_redirects_never_followed(code):
 calls=[]
 def serve(r):calls.append(r);return httpx.Response(code,headers={'location':'https://evil.example'},text=SECRET)
 c=ApifyHTTP(SECRET,httpx.MockTransport(serve))
 with pytest.raises(ProviderError) as e:c.run('r1')
 assert SECRET not in str(e.value) and len(calls)==1;c.close()

def test_malicious_provider_id_cannot_change_HTTP_destination():
 c=ApifyHTTP(SECRET,httpx.MockTransport(lambda r:pytest.fail('Must reject before HTTP')))
 with pytest.raises(ProviderError):c.items('https://evil.example/',1)
 c.close()
