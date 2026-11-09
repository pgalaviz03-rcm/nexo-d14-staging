"""Findings, evidence freezing, optimistic review, roles and project boundaries."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,hashlib,sqlite3
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from app.alert_models import AlertIncident,AlertEvent
from app.alert_api import AlertCut,AlertReview
from app.alert_service import overview,preview,detail
from app.alert_port import DisabledAlertNotifier,AlertDeliveryUnavailable
from app.pulse_models import PulseActor,PulseRule,PulseBatch,PulseDocument,PulseMention,PulseConfig
from app.pulse_api import RuleInput
from app.pulse_service import overview as pulse_overview
from app.models import Membership,UsageCounter,AuditEvent
from test_manual_reviews import archive,endpoint
from test_pulse import add_actor,call as pulse

END=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)-timedelta(hours=1);START=END-timedelta(days=1)
def seed(a,*,n=3,label=None,metric='mentions',threshold=3,minimum=1,previous=0):
    actor=add_actor(a)['id'];rid=pulse(a,'/rules','POST',body=RuleInput(actor_id=actor,name='Synthetic threshold',metric=metric,threshold=threshold,min_mentions=minimum))['id']
    batch=PulseBatch(project_id=a[2].id,provider='synthetic',dataset_ref='',sha256='fixture',is_demo=False,created_by=a[4][0].id);a[1].add(batch);a[1].flush()
    for i in range(n+previous):
        at=END-timedelta(hours=1) if i<n else START-timedelta(hours=1)
        d=PulseDocument(project_id=a[2].id,batch_id=batch.id,network='facebook',external_id=str(i),url='https://example.org/fixture/'+str(i),title='Literal <script>fixture</script> '+str(i),text='',published_at=at,collected_at=END,is_demo=False)
        a[1].add(d);a[1].flush();a[1].add(PulseMention(project_id=a[2].id,document_id=d.id,actor_id=actor,is_demo=False,sentiment=label,method='manual-review' if label else 'unclassified'))
    a[1].commit();return actor,rid
def get(a,**kw):return overview(a[1],a[2].id,start=START,end=END,**kw)
def evaluate(a,*,user=0,pid=None,**kw):return endpoint(a[0],'/api/projects/{pid}/alerts/evaluate','POST')(pid=pid or a[2].id,body=AlertCut(start=START,end=END,**kw),user=a[4][user],session=a[1])
def review(a,aid,version=0,state='acknowledged',note='',user=0,pid=None):return endpoint(a[0],'/api/projects/{pid}/alerts/{alert_id}/reviews','POST')(pid=pid or a[2].id,alert_id=aid,body=AlertReview(expected_version=version,status=state,note=note),user=a[4][user],session=a[1])
def first(a):return a[1].scalar(select(AlertIncident.id))
def count(a,model):return a[1].scalar(select(func.count()).select_from(model))

def test_empty_dashboard_is_readonly_and_generic(archive):
    p=get(archive);assert p['incidents']==[] and p['readings']==[] and p['counts']['open']==0 and p['external_calls']==0 and count(archive,AlertIncident)==0

def test_preview_does_not_record_until_explicit_evaluation(archive):
    seed(archive);p=get(archive);assert p['readings'][0]['status']=='triggered' and count(archive,AlertIncident)==0
    assert evaluate(archive)['inserted']==1 and get(archive)['counts']['open']==1

def test_repeat_cut_deduplicates_without_reopening_resolved(archive):
    seed(archive);evaluate(archive);aid=first(archive);review(archive,aid,state='resolved',note='Fixture reviewed')
    r=evaluate(archive);assert r['inserted']==0 and r['duplicates']==1 and count(archive,AlertIncident)==1 and get(archive)['incidents'][0]['status']=='resolved'

def test_snapshot_hash_and_sources_remain_after_source_changes(archive):
    seed(archive);evaluate(archive);aid=first(archive);d=detail(archive[1],archive[2].id,aid)
    row=archive[1].scalar(select(AlertIncident));assert hashlib.sha256(row.snapshot_json.encode()).hexdigest()==d['snapshot_sha256']
    source=archive[1].scalar(select(PulseDocument));source.title='Changed later';archive[1].commit()
    assert detail(archive[1],archive[2].id,aid)['snapshot']==d['snapshot'] and d['snapshot']['sources'][0]['title'].startswith('Literal')

def test_evidence_cap_does_not_change_denominator(archive):
    seed(archive,n=25);evaluate(archive);d=detail(archive[1],archive[2].id,first(archive))
    assert len(d['snapshot']['sources'])==20 and d['snapshot']['sources_bounded'] and d['snapshot']['reading']['mentions']==25

def test_negative_alert_waits_for_stored_classification_coverage(archive):
    seed(archive,n=25,metric='negative_share',threshold=50);p=get(archive)
    assert p['readings'][0]['reason']=='classification_pending' and evaluate(archive)['inserted']==0

def test_negative_and_spike_evaluation_match_pulse(archive):
    actor,rid=seed(archive,n=25,label='negative',metric='negative_share',threshold=50,previous=10)
    p=get(archive);q=pulse_overview(archive[1],archive[2].id,start=START,end=END)
    assert p['readings'][0]['value']==q['alerts'][0]['value']==100
    pulse(archive,'/rules','POST',body=RuleInput(actor_id=actor,name='Synthetic spike',metric='mention_spike',threshold=50,min_mentions=1))
    p=get(archive);assert p['readings'][1]['value']==150 and p['readings'][1]['status']=='triggered'

def test_spike_without_baseline_and_rule_minimum_remain_pending(archive):
    actor,rid=seed(archive,metric='mention_spike',threshold=50)
    assert get(archive)['readings'][0]['reason']=='baseline_pending'
    archive[1].get(PulseRule,rid).min_mentions=20;archive[1].commit();assert get(archive)['readings'][0]['reason']=='insufficient_mentions'

def test_paused_rules_archived_actors_and_demo_are_not_evaluated(archive):
    actor,rid=seed(archive);archive[1].get(PulseRule,rid).active=False;archive[1].commit()
    assert get(archive)['readings'][0]['status']=='paused' and evaluate(archive)['inserted']==0
    archive[1].get(PulseActor,actor).active=False;archive[1].commit();assert get(archive)['readings']==[]

def test_network_filters_and_state_filters_are_real(archive):
    seed(archive);assert evaluate(archive,network='press')['inserted']==0;evaluate(archive)
    assert len(get(archive,state='open')['incidents'])==1 and get(archive,state='resolved')['incidents']==[]
    assert get(archive,network='press')['incidents']==[]

def test_review_reopen_and_full_append_only_history(archive):
    seed(archive);evaluate(archive);aid=first(archive)
    for version,state,note in [(0,'acknowledged',''),(1,'resolved','Reviewed evidence'),(2,'open','New review requested'),(3,'dismissed','Duplicate situation')]:review(archive,aid,version,state,note,user=1)
    d=detail(archive[1],archive[2].id,aid);assert d['status']=='dismissed' and d['version']==4 and len(d['history'])==4 and count(archive,AlertIncident)==1

def test_stale_expected_version_cannot_overwrite_state(archive):
    seed(archive);evaluate(archive);aid=first(archive);review(archive,aid)
    with pytest.raises(HTTPException) as e:review(archive,aid,state='resolved',note='Stale change')
    assert e.value.status_code==409 and count(archive,AlertEvent)==1

@pytest.mark.parametrize('state,note',[('open','reopen wrongly'),('resolved',''),('dismissed','a')])
def test_invalid_transition_or_missing_closure_reason_rejected(archive,state,note):
    seed(archive);evaluate(archive)
    with pytest.raises(HTTPException) as e:review(archive,first(archive),state=state,note=note)
    assert e.value.status_code==422 and count(archive,AlertEvent)==0

@pytest.mark.parametrize('user',[2,3])
def test_reader_and_foreign_client_cannot_evaluate_or_review(archive,user):
    seed(archive);evaluate(archive);aid=first(archive)
    with pytest.raises(HTTPException) as e:evaluate(archive,user=user)
    assert e.value.status_code in {403,404}
    with pytest.raises(HTTPException) as e:review(archive,aid,user=user)
    assert e.value.status_code in {403,404} and count(archive,AlertEvent)==0

def test_foreign_actor_or_incident_and_revoked_access_are_hidden(archive):
    seed(archive);evaluate(archive);aid=first(archive)
    with pytest.raises(HTTPException):detail(archive[1],archive[3].id,aid)
    foreign=add_actor(archive,pid=archive[3].id,actor=3)['id']
    with pytest.raises(HTTPException):get(archive,actor_id=foreign)
    member=archive[1].scalar(select(Membership).where(Membership.project_id==archive[2].id,Membership.user_id==archive[4][0].id));archive[1].delete(member);archive[1].commit()
    with pytest.raises(HTTPException) as e:endpoint(archive[0],'/api/projects/{pid}/alerts/{alert_id}')(pid=archive[2].id,alert_id=aid,user=archive[4][0],session=archive[1])
    assert e.value.status_code==404

def test_reader_can_read_but_cannot_manage_and_get_causes_no_writes(archive):
    seed(archive);evaluate(archive);before=count(archive,AuditEvent)
    p=endpoint(archive[0],'/api/projects/{pid}/alerts')(pid=archive[2].id,user=archive[4][2],session=archive[1],actor_id=0,network='all',state='all',start=START,end=END)
    assert not p['can_review'] and not p['can_manage_rules'] and count(archive,AuditEvent)==before

def test_quota_and_project_storage_limit_are_enforced(archive,monkeypatch):
    seed(archive);archive[1].add(UsageCounter(project_id=archive[2].id,action='alerts.evaluate',bucket=datetime.now(timezone.utc).strftime('%Y-%m-%d'),used=48));archive[1].commit()
    with pytest.raises(HTTPException) as e:evaluate(archive)
    assert e.value.status_code==429 and count(archive,AlertIncident)==0

def test_incident_query_limit_explicit(archive,monkeypatch):
    import app.alert_service as service
    actor,rid=seed(archive);pulse(archive,'/rules','POST',body=RuleInput(actor_id=actor,name='Another rule',metric='mentions',threshold=1,min_mentions=1));evaluate(archive)
    monkeypatch.setattr(service,'MAX_INCIDENTS',1);p=get(archive);assert p['incidents_bounded'] and len(p['incidents'])==1

def test_offsets_normalize_and_future_invalid_cuts_are_rejected(archive):
    seed(archive)
    with pytest.raises(HTTPException):preview(archive[1],archive[2].id,start=START,end=datetime.now(timezone.utc)+timedelta(days=1))
    with pytest.raises(HTTPException):preview(archive[1],archive[2].id,start=END,end=START)
    with pytest.raises(ValidationError):AlertCut(start=START.replace(tzinfo=None),end=END)
    with pytest.raises(HTTPException):get(archive,state='unknown')

@pytest.mark.parametrize('fields',[dict(expected_version=True,status='resolved'),dict(expected_version=-1,status='open'),dict(expected_version=1000,status='open'),dict(expected_version=0,status='sent'),dict(expected_version=0,status='open',created_by=999),dict(expected_version=0,status='open',note='x'*1001)])
def test_review_contract_forbids_forged_identity_and_invalid_input(fields):
    with pytest.raises(ValidationError):AlertReview(**fields)

def test_notification_boundary_is_closed_even_with_tokens(monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','synthetic-unused')
    with pytest.raises(AlertDeliveryUnavailable):DisabledAlertNotifier().notify(project_id=1,incident_id=1,channel='telegram',snapshot_sha256='fixture',idempotency_key='fixture')

def test_populated_findings_and_reviews_survive_isolated_recovery(archive,monkeypatch):
    from scripts import backup_local as backup
    seed(archive);evaluate(archive);review(archive,first(archive),state='resolved',note='Fixture complete')
    private=Path(archive[0].state.engine.url.database).parent;uploads=private/'uploads';uploads.mkdir(exist_ok=True);key=private/'fixture.key';key.write_text('fixture-only')
    raw,manifest=backup.make_archive(private,db_file=Path(archive[0].state.engine.url.database),uploads_directory=uploads,secret_file=key);monkeypatch.setattr(backup,'dpapi',lambda data,decrypt=False:data)
    file=private/'alerts-fixture.nexobak';file.write_bytes(backup.MAGIC+raw);assert backup.restore_backup(file,private/'restore')['counts']==manifest['counts']
    with sqlite3.connect(private/'restore/storage/nexo.db') as c:assert c.execute('SELECT status,note FROM alert_events').fetchone()==('resolved','Fixture complete') and c.execute('PRAGMA foreign_key_check').fetchone() is None
