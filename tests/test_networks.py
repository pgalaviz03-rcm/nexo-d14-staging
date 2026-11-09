"""Own-account statistics, comparable periods, source contracts and isolation."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from app.network_service import overview
from app.network_port import AccountCapture,AccountCaptureBatch,DisabledAccountReader,AccountSourceUnavailable,normalize_account_export
from app.models import AuditEvent,Membership
from app.pulse_models import PulseAccount,PulseActor
from app.actor_models import ActorProfile
from test_manual_reviews import archive,endpoint
from test_actors import create,call as actors

END=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=1)
START=END-timedelta(days=7);NOW=END+timedelta(days=2)
URL='https://www.facebook.com/public_fixture'

def setup(a,name='Actor A',kind='primary',url=URL):
    return create(a,name=name,kind=kind,channels=[dict(network='facebook',url=url)])['id']
def add(a,actor,at,*,url=URL,network='facebook',demo=False,**metrics):
    row=PulseAccount(project_id=a[2].id,actor_id=actor,network=network,url=url,captured_at=at,metrics=json.dumps(metrics),is_demo=demo,created_by=a[4][0].id)
    a[1].add(row);a[1].commit();return row
def dashboard(a,**kwargs):return overview(a[1],a[2].id,start=START,end=END,now=NOW,**kwargs)
def load(a,items,provider='manual',actor=0):
    return endpoint(a[0],'/api/projects/{pid}/networks/captures','POST')(pid=a[2].id,body=AccountCaptureBatch(provider=provider,items=items),user=a[4][actor],session=a[1])
def capture(actor,**kw):
    return AccountCapture(actor_id=actor,network='facebook',url=URL,captured_at=END-timedelta(hours=1),followers=100,**kw)

def test_registered_reference_is_visible_without_fabricated_counts(archive):
    actor=setup(archive);p=dashboard(archive)
    assert p['selected_actor_id']==actor and len(p['accounts'])==1 and p['selected_account']['status']=='no_captures'
    a=p['selected_account'];assert a['followers'] is None and all(v is None for v in a['current'].values()) and a['series']==[]

def test_stock_growth_has_observation_dates_and_is_never_summed_across_accounts(archive):
    actor=setup(archive);add(archive,actor,START-timedelta(hours=1),followers=100)
    add(archive,actor,END-timedelta(hours=1),followers=115)
    add(archive,actor,END-timedelta(hours=2),url='https://www.facebook.com/second_fixture',followers=900)
    a=dashboard(archive)['selected_account'];assert a['followers']==115 and a['followers_change']==dict(absolute=15,percent=15)
    assert a['followers_baseline_at'] and a['followers_as_of'] and len(dashboard(archive)['accounts'])==2

def test_period_metrics_can_be_collected_after_close_and_compare_exact_windows(archive):
    actor=setup(archive);add(archive,actor,END-timedelta(hours=1),followers=100)
    add(archive,actor,END+timedelta(hours=1),metrics_from=START.isoformat(),metrics_to=END.isoformat(),interactions=50,views=200,reach=80,posts=3)
    add(archive,actor,START+timedelta(hours=1),metrics_from=(START-(END-START)).isoformat(),metrics_to=START.isoformat(),interactions=25,views=100,reach=60,posts=2)
    p=dashboard(archive)['selected_account'];assert p['current']['interactions']==50 and p['changes']['interactions']==dict(absolute=25,percent=100)
    assert p['current']['posts']==3 and p['interactions_per_100_followers']==50 and p['activity_captured_at']

def test_overlapping_and_undeclared_periods_are_not_added_or_compared(archive):
    actor=setup(archive);add(archive,actor,END-timedelta(hours=1),followers=100,views=500,interactions=50)
    add(archive,actor,END+timedelta(hours=1),metrics_from=(START-timedelta(days=1)).isoformat(),metrics_to=END.isoformat(),views=900)
    p=dashboard(archive)['selected_account'];assert p['followers']==100 and p['current']['views'] is None and p['current']['interactions'] is None

def test_missing_and_zero_counters_remain_distinct(archive):
    actor=setup(archive);add(archive,actor,END,followers=0,metrics_from=START.isoformat(),metrics_to=END.isoformat(),views=0,interactions=0)
    p=dashboard(archive)['selected_account'];assert p['followers']==0 and p['current']['views']==0 and p['current']['reach'] is None
    assert p['interactions_per_100_followers'] is None

def test_comparison_uses_same_network_and_period_with_one_reference_per_actor(archive):
    a=setup(archive);b=setup(archive,'Actor B','comparator','https://www.facebook.com/comparator_fixture')
    add(archive,a,END,followers=100);add(archive,b,END,url='https://www.facebook.com/comparator_fixture',followers=200)
    p=dashboard(archive);assert p['comparison_network']=='facebook' and len(p['comparison'])==2
    assert [r['account']['followers'] for r in p['comparison']]==[100,200]

def test_foreign_actor_or_account_cannot_be_selected(archive):
    setup(archive)
    foreign=actors(archive,method='POST',actor=3,pid=archive[3].id,body=__import__('app.actors_api',fromlist=['ActorCreate']).ActorCreate(name='Foreign actor',kind='primary'))['id']
    with pytest.raises(HTTPException) as e:dashboard(archive,actor_id=foreign)
    assert e.value.status_code==404
    with pytest.raises(HTTPException) as e:dashboard(archive,account_url='https://www.facebook.com/not_registered')
    assert e.value.status_code==404

def test_future_capture_is_not_visible_and_stale_point_has_no_period_growth(archive):
    actor=setup(archive);add(archive,actor,START-timedelta(days=30),followers=100);add(archive,actor,NOW+timedelta(hours=1),followers=999)
    p=dashboard(archive)['selected_account'];assert p['followers']==100 and p['status']=='stale' and p['followers_change']['absolute'] is None

def test_stale_followers_are_not_a_fresh_activity_ratio_denominator(archive):
    actor=setup(archive);add(archive,actor,START-timedelta(days=30),followers=100)
    add(archive,actor,END+timedelta(hours=1),metrics_from=START.isoformat(),metrics_to=END.isoformat(),interactions=50)
    assert dashboard(archive)['selected_account']['interactions_per_100_followers'] is None

def test_latest_followers_after_cut_keep_own_observation_date(archive):
    actor=setup(archive);add(archive,actor,END-timedelta(hours=1),followers=100)
    add(archive,actor,END+timedelta(hours=1),followers=110,metrics_from=START.isoformat(),metrics_to=END.isoformat(),interactions=50)
    a=dashboard(archive)['selected_account'];assert a['followers']==110 and a['current']['interactions']==50
    assert a['interactions_per_100_followers']==50 and a['ratio_followers_as_of']!=(a['followers_as_of'])

def test_activity_only_capture_does_not_erase_last_known_stock(archive):
    actor=setup(archive);add(archive,actor,END-timedelta(hours=1),followers=100)
    add(archive,actor,END+timedelta(hours=1),metrics_from=START.isoformat(),metrics_to=END.isoformat(),interactions=50)
    assert dashboard(archive)['selected_account']['followers']==100

def test_capture_timestamps_normalize_offsets_to_utc(archive):
    actor=setup(archive);local=(END-timedelta(hours=1)).astimezone(timezone(timedelta(hours=-6)))
    row=AccountCapture(actor_id=actor,network='facebook',url=URL,captured_at=local,followers=100)
    assert row.captured_at.utcoffset()==timedelta(0);load(archive,[row])
    assert dashboard(archive)['selected_account']['followers_as_of']==(END-timedelta(hours=1)).isoformat()

def test_paused_reference_and_archived_actors_do_not_enter_comparison(archive):
    actor=setup(archive);row=archive[1].get(ActorProfile,actor);channels=json.loads(row.channels_json);channels[0]['enabled']=False;row.channels_json=json.dumps(channels);archive[1].commit()
    add(archive,actor,END,followers=100);assert dashboard(archive)['accounts']==[]
    a=archive[1].get(PulseActor,actor);a.active=False;archive[1].commit();assert dashboard(archive)['actors']==[]

def test_query_bound_is_explicit(archive,monkeypatch):
    import app.network_service as service
    actor=setup(archive);add(archive,actor,START,followers=100);add(archive,actor,END,followers=110)
    monkeypatch.setattr(service,'MAX_RECORDS',1);assert dashboard(archive)['coverage_bounded']

def test_capture_import_is_idempotent_and_keeps_provenance(archive):
    actor=setup(archive);row=capture(actor)
    assert load(archive,[row])['inserted']==1 and load(archive,[row])['duplicates']==1
    stored=archive[1].scalar(select(PulseAccount));assert json.loads(stored.metrics)['provider']=='manual'
    assert archive[1].scalar(select(func.count()).select_from(PulseAccount))==1

def test_conflicting_same_timestamp_never_rewrites_history(archive):
    actor=setup(archive);row=capture(actor);load(archive,[row])
    with pytest.raises(HTTPException) as e:load(archive,[row.model_copy(update={'followers':999})])
    assert e.value.status_code==409 and json.loads(archive[1].scalar(select(PulseAccount)).metrics)['followers']==100

def test_bad_reference_rolls_back_the_whole_batch(archive):
    actor=setup(archive);a=capture(actor);b=capture(actor).model_copy(update={'url':'https://www.facebook.com/not_registered','captured_at':END-timedelta(hours=2)})
    with pytest.raises(HTTPException):load(archive,[a,b])
    assert archive[1].scalar(select(func.count()).select_from(PulseAccount))==0

def test_own_membership_cannot_import_another_project_actor(archive):
    from app.actors_api import ActorCreate
    foreign=actors(archive,method='POST',actor=3,pid=archive[3].id,body=ActorCreate(name='Foreign actor',kind='primary',channels=[dict(network='facebook',url=URL)]))['id']
    with pytest.raises(HTTPException) as e:load(archive,[capture(foreign)])
    assert e.value.status_code==422 and archive[1].scalar(select(func.count()).select_from(PulseAccount))==0

def test_future_timestamp_rejected_before_any_snapshot_is_stored(archive):
    actor=setup(archive);future=capture(actor).model_copy(update={'captured_at':datetime.now(timezone.utc)+timedelta(days=1)})
    with pytest.raises(HTTPException) as e:load(archive,[future])
    assert e.value.status_code==422 and archive[1].scalar(select(func.count()).select_from(PulseAccount))==0

def test_import_quota_blocks_without_creating_captures(archive):
    from app.models import UsageCounter
    actor=setup(archive);archive[1].add(UsageCounter(project_id=archive[2].id,action='networks.import',bucket=datetime.now(timezone.utc).strftime('%Y-%m-%d'),used=20));archive[1].commit()
    with pytest.raises(HTTPException) as e:load(archive,[capture(actor)])
    assert e.value.status_code==429 and archive[1].scalar(select(func.count()).select_from(PulseAccount))==0

def test_populated_snapshot_and_reference_survive_backup_restore(archive,monkeypatch):
    import sqlite3
    from scripts import backup_local as backup
    actor=setup(archive);load(archive,[capture(actor)])
    private=Path(archive[0].state.engine.url.database).parent;uploads=private/'uploads';uploads.mkdir(exist_ok=True)
    key=private/'fixture.key';key.write_text('synthetic-only')
    raw,manifest=backup.make_archive(private,db_file=Path(archive[0].state.engine.url.database),uploads_directory=uploads,secret_file=key)
    monkeypatch.setattr(backup,'dpapi',lambda value,decrypt=False:value)
    file=private/'network-fixture.nexobak';file.write_bytes(backup.MAGIC+raw)
    assert backup.restore_backup(file,private/'restored')['counts']==manifest['counts']
    with sqlite3.connect(private/'restored/storage/nexo.db') as c:
        stored=json.loads(c.execute('SELECT metrics FROM pulse_accounts').fetchone()[0]);assert stored['followers']==100 and stored['provider']=='manual'
        assert URL in c.execute('SELECT channels_json FROM actor_profiles').fetchone()[0]

@pytest.mark.parametrize('actor',[2,3])
def test_reader_and_foreign_client_cannot_import(archive,actor):
    a=setup(archive)
    with pytest.raises(HTTPException) as e:load(archive,[capture(a)],actor=actor)
    assert e.value.status_code in {403,404}

def test_consultor_can_import_but_dashboard_remains_project_scoped(archive):
    a=setup(archive);assert load(archive,[capture(a)],actor=1)['inserted']==1
    get=endpoint(archive[0],'/api/projects/{pid}/networks')
    p=get(pid=archive[2].id,user=archive[4][2],session=archive[1],start=START,end=END)
    assert not p['can_import'] and p['project_id']==archive[2].id
    with pytest.raises(HTTPException) as e:get(pid=archive[2].id,user=archive[4][3],session=archive[1],start=START,end=END)
    assert e.value.status_code==404

@pytest.mark.parametrize('values',[dict(views=2),dict(followers=-1),dict(followers=True),dict(followers='100'),dict(followers=9007199254740992),dict(followers=100,metrics_from=START,metrics_to=END)])
def test_capture_contract_rejects_ambiguous_or_invalid_measurements(values):
    with pytest.raises(ValidationError):AccountCapture(actor_id=1,network='facebook',url=URL,captured_at=END-timedelta(hours=1),**values)

def test_period_cannot_exceed_observation_or_finish_in_future(archive):
    setup(archive)
    with pytest.raises(HTTPException):overview(archive[1],archive[2].id,start=START,end=NOW+timedelta(seconds=1),now=NOW)
    with pytest.raises(ValidationError):AccountCapture(actor_id=1,network='facebook',url=URL,captured_at=START,metrics_from=START,metrics_to=END,views=2)

def test_real_reader_is_disabled_even_with_environment_token(monkeypatch):
    monkeypatch.setenv('APIFY_TOKEN','SYNTHETIC_UNUSED')
    with pytest.raises(AccountSourceUnavailable):DisabledAccountReader().read(network='facebook',url=URL,external_id='',limit=1,timeout_seconds=20)

def test_export_mapping_uses_trusted_actor_and_url_not_exported_scope():
    result=normalize_account_export([dict(fans=100,actor_id=999,url='https://wrong.invalid')],{'followers':'fans'},actor_id=1,network='facebook',url=URL,collected_at=END)
    assert result.items[0].actor_id==1 and result.items[0].url==URL and result.provider=='apify_export'
    with pytest.raises(ValueError):normalize_account_export([{}],{'followers':'nested.value'},actor_id=1,network='facebook',url=URL,collected_at=END)

def test_provider_urls_and_audit_do_not_accept_credentials(archive):
    with pytest.raises(ValidationError):AccountCapture(actor_id=1,network='facebook',url=URL+'?access_token=synthetic',captured_at=END,followers=1)
    actor=setup(archive);load(archive,[capture(actor)])
    events=' '.join(r.target for r in archive[1].scalars(select(AuditEvent)))
    assert URL not in events and 'followers' not in events
