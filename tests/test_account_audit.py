"""Read-only quality checks over project-owned aggregate account captures."""
from datetime import timedelta
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from app.account_audit import audit_accounts
from app.actor_models import ActorProfile
from app.pulse_models import PulseActor,PulseAccount
from app.models import AuditEvent
from test_manual_reviews import archive,endpoint
from test_networks import setup,add,START,END,NOW,URL

def audit(a,**kw):return audit_accounts(a[1],a[2].id,start=START,end=END,now=NOW,**kw)
def row(a):return audit(a)['items'][0]
def reviewed(a,actor):
 p=a[1].get(ActorProfile,actor);r=json.loads(p.channels_json);r[0]['review']='reviewed';p.channels_json=json.dumps(r);a[1].commit()
def pair(a,actor,provider='manual'):
 add(a,actor,END,provider=provider,metrics_from=START.isoformat(),metrics_to=END.isoformat(),interactions=10,views=0)
 add(a,actor,START,provider=provider,metrics_from=(START-(END-START)).isoformat(),metrics_to=START.isoformat(),interactions=5,views=0)

def test_registered_references_exist_without_any_captures(archive):
 setup(archive);p=audit(archive);r=p['items'][0]
 assert p['counts']==dict(accounts=1,registered=1,with_captures=0,comparable=0,pending=1)
 assert r['state']=='no_captures' and r['latest_capture_at'] is None and r['fields']['followers']=='missing'

def test_same_provider_exact_periods_align_without_summing(archive):
 actor=setup(archive);reviewed(archive,actor);pair(archive,actor)
 r=row(archive);assert r['state']=='ready' and r['comparable_fields']==['views','interactions']
 assert r['fields']['views']=='available' and r['fields']['followers']=='missing' and r['issues']==[]

def test_review_of_reference_is_not_assumed(archive):
 actor=setup(archive);pair(archive,actor);r=row(archive)
 assert not r['reference_reviewed'] and r['state']=='needs_review' and 'reference_unreviewed' in r['issues']

@pytest.mark.parametrize('value',[True,-1,'20',1.5,9007199254740992])
def test_invalid_counters_are_never_available_or_zero(archive,value):
 actor=setup(archive);add(archive,actor,END,followers=value,provider='manual');r=row(archive)
 assert r['fields']['followers']=='invalid' and 'invalid_counter' in r['issues']

def test_zero_is_a_real_available_counter(archive):
 actor=setup(archive);add(archive,actor,END,followers=0,provider='manual');assert row(archive)['fields']['followers']=='available'

@pytest.mark.parametrize('raw',['{broken secret-example','[]','null','"secret-example"','x'*32769],ids=['malformed','array','null','scalar','oversize'])
def test_legacy_invalid_json_has_safe_diagnostic_and_no_raw_leak(archive,raw):
 actor=setup(archive);r=add(archive,actor,END,followers=20);r.metrics=raw;archive[1].commit()
 result=audit(archive);assert 'invalid_payload' in result['items'][0]['issues']
 assert 'secret-example' not in json.dumps(result) and all(v=='missing' for v in result['items'][0]['fields'].values())

def test_unknown_properties_and_provider_strings_never_leave_parser(archive):
 actor=setup(archive);add(archive,actor,END,followers=20,provider='secret-example',token='secret-example')
 r=row(archive);assert r['latest_origin'] is None and 'secret-example' not in json.dumps(r)

def test_future_captures_are_detected_but_never_qualify_as_latest(archive):
 actor=setup(archive);add(archive,actor,END,followers=20,provider='manual');add(archive,actor,NOW+timedelta(days=1),followers=999)
 r=row(archive);assert 'future_capture' in r['issues'] and r['latest_origin']=='manual'
 assert r['latest_capture_at']==END.isoformat()

def test_capture_without_valid_period_cannot_supply_activity_comparison(archive):
 actor=setup(archive);add(archive,actor,END,interactions=20,provider='manual',metrics_from=True,metrics_to='tomorrow')
 r=row(archive);assert 'invalid_period' in r['issues'] and not r['comparable_fields']

def test_activity_period_cannot_end_after_capture(archive):
 actor=setup(archive);add(archive,actor,END-timedelta(days=1),views=0,provider='manual',metrics_from=START.isoformat(),metrics_to=END.isoformat())
 assert 'invalid_period' in row(archive)['issues'] and row(archive)['period_capture_at'] is None

def test_adjacent_periods_with_different_origins_are_not_compared(archive):
 actor=setup(archive);pair(archive,actor);older=archive[1].scalar(select(PulseAccount).where(PulseAccount.captured_at==START))
 d=json.loads(older.metrics);d['provider']='apify_export';older.metrics=json.dumps(d);archive[1].commit()
 r=row(archive);assert not r['comparable_fields'] and 'origin_mismatch' in r['issues']

def test_overlapping_period_does_not_count_as_previous(archive):
 actor=setup(archive);pair(archive,actor);older=archive[1].scalar(select(PulseAccount).where(PulseAccount.captured_at==START))
 d=json.loads(older.metrics);d['metrics_to']=(START-timedelta(hours=1)).isoformat();older.metrics=json.dumps(d);archive[1].commit()
 assert row(archive)['previous_capture_at'] is None

def test_latest_fields_do_not_claim_values_from_older_capture(archive):
 actor=setup(archive);add(archive,actor,START,followers=100,provider='manual')
 add(archive,actor,END,views=50,provider='manual',metrics_from=START.isoformat(),metrics_to=END.isoformat())
 assert row(archive)['fields']['followers']=='missing'

def test_paused_references_and_archived_actors_remain_visible(archive):
 actor=setup(archive);pair(archive,actor);reviewed(archive,actor)
 p=archive[1].get(ActorProfile,actor);refs=json.loads(p.channels_json);refs[0]['enabled']=False;p.channels_json=json.dumps(refs);archive[1].commit()
 assert row(archive)['state']=='paused' and audit(archive)['counts']['comparable']==0
 archive[1].get(PulseActor,actor).active=False;archive[1].commit();assert not row(archive)['actor_active']

def test_unregistered_capture_visible_but_not_active(archive):
 actor=setup(archive);add(archive,actor,END,url='https://www.facebook.com/another_public',followers=10)
 p=audit(archive);r=next(r for r in p['items'] if not r['registered']);assert r['state']=='unregistered' and not r['enabled']

def test_unsafe_reference_payload_not_echoed_in_response(archive):
 actor=setup(archive);p=archive[1].get(ActorProfile,actor);p.channels_json=json.dumps([dict(network='facebook',url='https://www.facebook.com/person?token=secret-example')]);archive[1].commit()
 r=row(archive);assert r['url'] is None and r['issues']==['invalid_reference'] and 'secret-example' not in json.dumps(r)

def test_unsafe_capture_reference_has_diagnostic_without_link(archive):
 actor=setup(archive);add(archive,actor,END,url='https://www.facebook.com/person?token=secret-example',followers=10)
 r=row(archive);assert 'invalid_capture_reference' in r['issues'] and 'secret-example' not in json.dumps(r)

def test_old_capture_retains_date_and_is_identified(archive):
 actor=setup(archive);add(archive,actor,START-timedelta(days=30),followers=10)
 assert 'old_capture' in row(archive)['issues']

def test_filters_and_bounds_are_explicit(archive,monkeypatch):
 import app.account_audit as module
 actor=setup(archive);pair(archive,actor);monkeypatch.setattr(module,'MAX_RECORDS',1)
 p=audit(archive,actor_id=actor,network='facebook');assert p['coverage_bounded'] and len(p['items'])==1
 assert audit(archive,network='youtube')['items']==[]

@pytest.mark.parametrize('kwargs',[dict(network='nope'),dict(actor_id=-1),dict(start=START.replace(tzinfo=None)),dict(end=NOW+timedelta(days=1)),dict(start=END-timedelta(days=91))])
def test_invalid_query_is_rejected(archive,kwargs):
 with pytest.raises(HTTPException) as e:audit_accounts(archive[1],archive[2].id,now=NOW,**(dict(start=START,end=END)|kwargs))
 assert e.value.status_code==422

def test_membership_gate_and_no_mutations(archive):
 setup(archive);get=endpoint(archive[0],'/api/projects/{pid}/account-audit')
 before=archive[1].scalar(select(func.count()).select_from(AuditEvent))
 for user in archive[4][:3]:
  result=get(pid=archive[2].id,user=user,session=archive[1],start=START,end=END)
  assert result['project_id']==archive[2].id and result['external_calls']==0
 with pytest.raises(HTTPException) as e:get(pid=archive[2].id,user=archive[4][3],session=archive[1],start=START,end=END)
 assert e.value.status_code==404 and archive[1].scalar(select(func.count()).select_from(AuditEvent))==before

def test_foreign_and_demo_actors_are_not_exposed_or_selectable(archive):
 actor=setup(archive);s=archive[1];foreign=PulseActor(project_id=archive[3].id,name='FOREIGN',kind='primary',is_demo=False,created_by=archive[4][3].id)
 demo=PulseActor(project_id=archive[2].id,name='DEMO',kind='comparator',is_demo=True,created_by=archive[4][0].id)
 s.add_all([foreign,demo]);s.commit()
 assert [a['id'] for a in audit(archive)['actors']]==[actor]
 for a in [foreign,demo]:
  with pytest.raises(HTTPException) as e:audit(archive,actor_id=a.id)
  assert e.value.status_code==404

def test_no_outbound_call_even_with_provider_tokens(archive,monkeypatch):
 import socket
 actor=setup(archive);pair(archive,actor);monkeypatch.setenv('APIFY_TOKEN','synthetic-token')
 def fail(*args,**kwargs):raise AssertionError('External network access')
 monkeypatch.setattr(socket,'create_connection',fail);monkeypatch.setattr(socket,'getaddrinfo',fail)
 assert audit(archive)['external_calls']==0

def test_extreme_legacy_date_overflow_is_a_diagnostic_not_a_server_error(archive):
 actor=setup(archive);add(archive,actor,END,views=20,provider='manual',metrics_from=START.isoformat(),metrics_to='9999-12-31T23:59:59-01:00')
 assert 'invalid_period' in row(archive)['issues']

def test_diagnostic_does_not_copy_or_rewrite_snapshot_data(archive):
 actor=setup(archive);r=add(archive,actor,END,followers=20,token='secret-example');before=r.metrics
 audit(archive);archive[1].refresh(r)
 assert r.metrics==before and archive[1].scalar(select(func.count()).select_from(PulseAccount))==1
