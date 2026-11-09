"""Aggregate continuity definitions, immutability, privacy and tenant isolation."""
from datetime import datetime,timedelta,timezone
import json
import socket
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from app.continuity_models import AudienceSnapshot
from app.continuity_port import AudienceCapture,AudienceBatch,DisabledAudienceReader,AudienceSourceUnavailable,normalize_audience_export
from app.continuity_service import overview
from app.models import Membership,UsageCounter,AuditEvent
from app.actor_models import ActorProfile
from app.pulse_models import PulseActor
from test_manual_reviews import archive,endpoint
from test_networks import setup,URL

END=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=1)
START=END-timedelta(days=7);NOW=END+timedelta(days=2)
def capture(actor,**kw):
    values=dict(actor_id=actor,network='facebook',url=URL,measurement_id='fixture-v1',period_from=START,period_to=END,
        reference_from=START-timedelta(days=7),reference_to=START,captured_at=END+timedelta(hours=1),participants=100,returning=60,reference_participants=120)
    values.update(kw);return AudienceCapture(**values)
def load(a,items,*,actor=0,pid=None,provider='manual'):
    return endpoint(a[0],'/api/projects/{pid}/continuity/captures','POST')(pid=pid or a[2].id,body=AudienceBatch(provider=provider,items=items),user=a[4][actor],session=a[1])
def dashboard(a,**kw):return overview(a[1],a[2].id,start=START,end=END,now=NOW,**kw)
def count(a):return a[1].scalar(select(func.count()).select_from(AudienceSnapshot))

def test_empty_reference_has_no_invented_metrics(archive):
    actor=setup(archive);p=dashboard(archive)
    assert p['selected_actor_id']==actor and p['selected_account']['url']==URL
    assert p['current']['status']=='pending' and p['current']['participants'] is None and p['series']==[]

def test_return_and_retention_use_distinct_denominators(archive):
    actor=setup(archive);load(archive,[capture(actor)])
    c=dashboard(archive)['current'];assert (c['participants'],c['returning'],c['new'],c['return_rate'],c['retention_rate'])==(100,60,40,60,50)

def test_unknown_reference_population_is_not_assumed(archive):
    actor=setup(archive);load(archive,[capture(actor,reference_participants=None)])
    c=dashboard(archive)['current'];assert c['return_rate']==60 and c['retention_rate'] is None

def test_real_zero_return_preserved_for_large_audience(archive):
    actor=setup(archive);load(archive,[capture(actor,returning=0)])
    c=dashboard(archive)['current'];assert c['return_rate']==0 and c['returning']==0 and c['new']==100

@pytest.mark.parametrize('values',[dict(participants=19,returning=10),dict(returning=3),dict(returning=98),dict(returning=60,reference_participants=62),dict(participants=0,returning=0,reference_participants=0)])
def test_small_cells_hidden_in_dashboard_series_and_export_packet(archive,values):
    actor=setup(archive);load(archive,[capture(actor,**values)]);p=dashboard(archive)
    assert p['current']['status']=='limited_sample'
    assert all(p['current'][k] is None for k in ['participants','returning','new','reference_participants','return_rate','retention_rate'])
    assert p['series'][0]['participants'] is None and p['series'][0]['return_rate'] is None

def test_comparable_previous_period_and_percentage_points(archive):
    actor=setup(archive);old=capture(actor,period_from=START-timedelta(days=7),period_to=START,reference_from=START-timedelta(days=14),reference_to=START-timedelta(days=7),participants=120,returning=48,reference_participants=120)
    load(archive,[old,capture(actor)]);p=dashboard(archive)
    assert p['return_rate_change_pp']==20 and p['previous']['return_rate']==40 and len(p['series'])==2

def test_conflicting_reference_base_does_not_publish_change(archive):
    actor=setup(archive);old=capture(actor,period_from=START-timedelta(days=7),period_to=START,reference_from=START-timedelta(days=14),reference_to=START-timedelta(days=7),participants=150,returning=60,reference_participants=150)
    load(archive,[old,capture(actor)]);p=dashboard(archive)
    assert not p['baseline_consistent'] and p['return_rate_change_pp'] is None

def test_different_definition_or_provider_not_compared(archive):
    actor=setup(archive);old=capture(actor,measurement_id='different-v1',period_from=START-timedelta(days=7),period_to=START,reference_from=START-timedelta(days=14),reference_to=START-timedelta(days=7))
    load(archive,[old,capture(actor)]);p=dashboard(archive)
    assert p['previous']['participants'] is None and p['return_rate_change_pp'] is None
    load(archive,[capture(actor)],provider='apify_export');assert len(dashboard(archive)['measurements'])==3

def test_wrong_window_never_added_to_exact_cut(archive):
    actor=setup(archive);load(archive,[capture(actor,period_from=START-timedelta(days=1),reference_from=START-timedelta(days=9),reference_to=START-timedelta(days=1))])
    assert dashboard(archive)['current']['participants'] is None

def test_latest_revision_selected_without_summing(archive):
    actor=setup(archive);load(archive,[capture(actor),capture(actor,captured_at=END+timedelta(hours=2),participants=200)])
    p=dashboard(archive);assert p['current']['participants']==200 and len(p['series'])==1 and count(archive)==2

def test_duplicate_idempotency_and_conflict_preserves_history(archive):
    actor=setup(archive);c=capture(actor);assert load(archive,[c])['inserted']==1 and load(archive,[c])['duplicates']==1
    with pytest.raises(HTTPException) as e:load(archive,[capture(actor,participants=200)])
    assert e.value.status_code==409 and count(archive)==1 and dashboard(archive)['current']['participants']==100

def test_bad_account_rolls_back_whole_batch(archive):
    actor=setup(archive)
    with pytest.raises(HTTPException):load(archive,[capture(actor),capture(actor,url='https://facebook.com/not_registered')])
    assert count(archive)==0

@pytest.mark.parametrize('user',[2,3])
def test_reader_or_foreign_cannot_import(archive,user):
    actor=setup(archive)
    with pytest.raises(HTTPException) as e:load(archive,[capture(actor)],actor=user)
    assert e.value.status_code in (403,404) and count(archive)==0

def test_foreign_actor_cannot_be_bound_to_own_project(archive):
    from test_actors import create
    from app.actors_api import ActorCreate
    actor=endpoint(archive[0],'/api/projects/{pid}/actors','POST')(pid=archive[3].id,body=ActorCreate(name='Foreign',kind='primary',channels=[dict(network='facebook',url=URL)]),user=archive[4][3],session=archive[1])['id']
    with pytest.raises(HTTPException):load(archive,[capture(actor)])
    with pytest.raises(HTTPException):dashboard(archive,actor_id=actor)
    assert count(archive)==0

def test_revoked_member_cannot_read_dashboard(archive):
    actor=setup(archive);load(archive,[capture(actor)]);m=archive[1].scalar(select(Membership).where(Membership.project_id==archive[2].id,Membership.user_id==archive[4][2].id));archive[1].delete(m);archive[1].commit()
    with pytest.raises(HTTPException) as e:endpoint(archive[0],'/api/projects/{pid}/continuity')(pid=archive[2].id,actor_id=0,network='all',account_url='',measurement='',start=START,end=END,user=archive[4][2],session=archive[1])
    assert e.value.status_code==404

def test_paused_reference_excludes_captures(archive):
    actor=setup(archive);load(archive,[capture(actor)]);p=archive[1].get(ActorProfile,actor);refs=json.loads(p.channels_json);refs[0]['enabled']=False;p.channels_json=json.dumps(refs);archive[1].commit()
    assert dashboard(archive)['accounts']==[] and dashboard(archive)['current']['participants'] is None

def test_future_capture_and_quota_block_without_snapshot(archive):
    actor=setup(archive)
    with pytest.raises(HTTPException):load(archive,[capture(actor,captured_at=datetime.now(timezone.utc)+timedelta(days=1))])
    quota=archive[1].scalar(select(UsageCounter).where(UsageCounter.project_id==archive[2].id,UsageCounter.action=='continuity.import'));quota.used=20;archive[1].commit()
    with pytest.raises(HTTPException) as e:load(archive,[capture(actor)])
    assert e.value.status_code==429 and count(archive)==0

@pytest.mark.parametrize('values',[dict(participants=True),dict(returning=101),dict(reference_participants=59),dict(participants=-1),dict(returning=1.5),dict(participants=9007199254740992),dict(reference_to=END),dict(period_to=START),dict(captured_at=START),dict(period_from=START.replace(tzinfo=None)),dict(url='http://127.0.0.1/x'),dict(measurement_id='name@person.example'),dict(participant_ids=['private']),dict(api_key='secret')])
def test_contract_rejects_invalid_counts_dates_identifiers_and_secrets(values):
    with pytest.raises(ValidationError):capture(1,**values)

def test_utc_normalization_and_disabled_provider_never_networks(monkeypatch):
    monkeypatch.setenv('APIFY_TOKEN','fixture');monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('Network must remain disabled'))
    c=capture(1,captured_at=(END+timedelta(hours=1)).astimezone(timezone(timedelta(hours=-6))))
    assert c.captured_at.utcoffset()==timedelta(0)
    with pytest.raises(AudienceSourceUnavailable):DisabledAudienceReader().read_aggregates()

def test_normalizer_uses_explicit_fields_and_trusted_scope():
    c=capture(1).model_dump(mode='json');mapping={k:k for k in ('period_from','period_to','reference_from','reference_to','captured_at','participants','returning','reference_participants')}
    c.update(actor_id=999,url='https://evil.invalid',participant_ids=['never retained'])
    b=normalize_audience_export([c],mapping,actor_id=1,network='facebook',url=URL,measurement_id='fixture-v1')
    assert b.items[0].actor_id==1 and b.items[0].url==URL and 'participant_ids' not in b.model_dump_json()

def test_query_bound_and_audit_contain_no_audience_values(archive,monkeypatch):
    import app.continuity_service as service
    actor=setup(archive);load(archive,[capture(actor),capture(actor,captured_at=END+timedelta(hours=2))]);monkeypatch.setattr(service,'MAX_RECORDS',1)
    assert dashboard(archive)['coverage_bounded']
    audit=archive[1].scalar(select(AuditEvent).where(AuditEvent.action=='continuity.import'));assert audit.target=='new:2:duplicate:0'

def test_populated_continuity_survives_isolated_backup_and_restore(archive,monkeypatch):
    from pathlib import Path
    import sqlite3
    from scripts import backup_local as backup
    actor=setup(archive);load(archive,[capture(actor)])
    private=Path(archive[0].state.engine.url.database).parent;uploads=private/'uploads';uploads.mkdir(exist_ok=True)
    key=private/'fixture.key';key.write_text('synthetic-only')
    raw,manifest=backup.make_archive(private,db_file=Path(archive[0].state.engine.url.database),uploads_directory=uploads,secret_file=key)
    monkeypatch.setattr(backup,'dpapi',lambda data,decrypt=False:data)
    file=private/'continuity-fixture.nexobak';file.write_bytes(backup.MAGIC+raw)
    assert backup.restore_backup(file,private/'restored')['counts']==manifest['counts']
    with sqlite3.connect(private/'restored/storage/nexo.db') as c:
        assert c.execute('SELECT participants,returning_count,reference_participants FROM audience_snapshots').fetchone()==(100,60,120)
        assert c.execute('PRAGMA foreign_key_check').fetchone() is None
