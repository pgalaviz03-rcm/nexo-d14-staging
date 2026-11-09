"""Private preferences, unique piece coding, scheduling and no-send boundary."""
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from app.models import NewsArticle,ReportVersion,AuditEvent
from app.delivery_models import BriefingSchedule,DeliveryJob,ContentAssessment
from app.delivery_api import ScheduleInput,MessagePreview
from app.delivery import next_occurrence,DisabledSender,DeliveryUnavailable,unseal,message_text
from app.content_assessment_api import AssessmentInput,source_values,fingerprint
from app.pulse_api import ConfigInput
from test_manual_reviews import archive,endpoint
from test_briefing import ready,preview,save,NOW
from test_pulse import call as pulse_call,add_actor,ingest,post

def delivery(a,suffix='',method='GET',actor=0,**args):return endpoint(a[0],'/api/projects/{pid}/briefing/delivery'+suffix,method)(pid=a[2].id,user=a[4][actor],session=a[1],**args)
def configure(a,actor=0,**args):return delivery(a,method='PUT',actor=actor,body=ScheduleInput(**args))
def assess(a,source=None,kind='news',actor=0,expected=0,**labels):
    row=source or a[-1][0]
    return endpoint(a[0],'/api/projects/{pid}/briefing/assessments/{kind}/{source_id}','PUT')(pid=a[2].id,kind=kind,source_id=row.id,user=a[4][actor],session=a[1],body=AssessmentInput(expected_version=expected,source_sha256=fingerprint(source_values(row)),**labels))
def add_news(a,n):
    result=[]
    for i in range(n):
        row=NewsArticle(project_id=a[2].id,title='Registro '+str(i),url='https://example.org/piece/'+str(i),url_hash='piece'+str(i),publisher='Fixture',abstract='Contenido público ficticio',origin='csv',published_at=NOW-timedelta(hours=1));a[1].add(row);result.append(row)
    a[1].commit();return result

def test_unclassified_content_never_invents_mockery_or_emotion(archive):
    ready(archive);a=preview(archive)['content_analytics']
    assert a['pieces']==1 and a['tone_classified']==0 and a['mood_index'] is None and a['mockery_percentage'] is None
    assert all(r['percentage'] is None for r in a['emotions'])

def test_piece_percentages_have_independent_denominators(archive):
    ready(archive);pulse_call(archive,'/config','PUT',body=ConfigInput(min_classified=3))
    rows=[archive[-1][0]]+add_news(archive,2)
    for row,t,e,m in zip(rows,['positive','negative','neutral'],['joy','anger','sadness'],[True,False,False]):assess(archive,row,sentiment=t,emotion=e,mockery=m)
    a=preview(archive)['content_analytics'];assert a['pieces']==3 and a['tone_classified']==3 and a['mood_index']==50
    assert all(r['percentage']==33.33 for r in a['tone']) and a['mockery_percentage']==33.33 and a['emotion_classified']==3

def test_same_url_across_news_and_pulse_is_one_piece(archive):
    ready(archive);actor=add_actor(archive)['id'];ingest(archive,[post(actor).model_copy(update={'url':archive[-1][0].url})])
    assert preview(archive)['content_analytics']['pieces']==1

def test_conflicting_labels_for_same_url_stay_unknown(archive):
    from app.pulse_models import PulseDocument
    ready(archive);actor=add_actor(archive)['id'];ingest(archive,[post(actor).model_copy(update={'url':archive[-1][0].url})])
    assess(archive,sentiment='positive');doc=archive[1].scalar(select(PulseDocument));assess(archive,doc,kind='pulse',sentiment='negative')
    a=preview(archive)['content_analytics'];assert a['pieces']==1 and a['tone_classified']==0

def test_changed_source_invalidates_piece_labels(archive):
    ready(archive);assess(archive,sentiment='positive',mockery=True);archive[-1][0].abstract='Fuente corregida';archive[1].commit()
    assert preview(archive)['content_analytics']['tone_classified']==0
    rows=endpoint(archive[0],'/api/projects/{pid}/briefing/assessments')(pid=archive[2].id,start=NOW-timedelta(days=1),end=NOW,user=archive[4][0],session=archive[1])
    assert rows['items'][0]['stale'] and rows['items'][0]['mockery'] is None

def test_classification_is_optimistic_and_project_scoped(archive):
    ready(archive);assess(archive,sentiment='positive')
    with pytest.raises(HTTPException) as e:assess(archive,sentiment='negative')
    assert e.value.status_code==409
    with pytest.raises(HTTPException) as e:assess(archive,archive[-1][1],sentiment='negative')
    assert e.value.status_code==404

def test_viewer_cannot_classify_but_can_prepare_own_schedule(archive):
    ready(archive)
    with pytest.raises(HTTPException) as e:assess(archive,actor=2,sentiment='positive')
    assert e.value.status_code==403
    configure(archive,actor=2,enabled=True)
    assert delivery(archive,actor=2)['settings']['enabled'] and delivery(archive)['settings']['version']==0

def test_schedule_destination_encrypted_and_not_returned(archive):
    destination='synthetic-private@test.invalid'
    result=configure(archive,destination=destination,authorized_destination=True,enabled=True)
    row=archive[1].get(BriefingSchedule,(archive[2].id,archive[4][0].id))
    assert destination not in row.destination_ciphertext and unseal(row.destination_ciphertext)==destination
    assert destination not in json.dumps(result) and 'destination_ciphertext' not in result and result['actual_delivery_enabled'] is False
    assert all(destination not in e.target for e in archive[1].scalars(select(AuditEvent)))

def test_schedule_channel_change_never_reuses_previous_destination(archive):
    configure(archive,destination='fixture@test.invalid',authorized_destination=True)
    result=configure(archive,expected_version=1,channel='telegram')
    assert result['destination_masked'] is None

def test_schedule_clear_and_stale_version(archive):
    configure(archive,destination='fixture@test.invalid',authorized_destination=True)
    assert configure(archive,expected_version=1,clear_destination=True)['destination_masked'] is None
    with pytest.raises(HTTPException) as e:configure(archive,expected_version=1)
    assert e.value.status_code==409

def test_destination_requires_explicit_authorization(archive):
    with pytest.raises(HTTPException) as e:configure(archive,destination='fixture@test.invalid')
    assert e.value.status_code==422
    with pytest.raises(HTTPException):configure(archive,destination='https://example.org/private',authorized_destination=True)

def test_whatsapp_and_private_user_ids_cannot_be_injected():
    with pytest.raises(ValidationError):ScheduleInput(channel='whatsapp')
    with pytest.raises(ValidationError):ScheduleInput(user_id=2)
    with pytest.raises(ValidationError):ScheduleInput(local_time='25:00')

def test_unknown_timezone_rejected(archive):
    with pytest.raises(HTTPException) as e:configure(archive,timezone='Unknown/Nowhere')
    assert e.value.status_code==422

def test_foreign_user_cannot_read_project_delivery(archive):
    with pytest.raises(HTTPException) as e:delivery(archive,actor=3)
    assert e.value.status_code==404

def test_local_message_preview_has_emotions_mockery_and_risks(archive):
    ready(archive);result=delivery(archive,'/preview','POST',body=MessagePreview(start=NOW-timedelta(days=1),end=NOW))
    assert all(t in result['text'] for t in ['Alegría','Ira','Sorpresa','Miedo','Tristeza','Burla','Pendientes','Alertas'])
    assert not result['actual_delivery_enabled'] and result['external_calls']==0
    assert 'Sin dato %' in result['text']

def test_simulation_is_idempotent_and_never_sends(archive):
    configure(archive,enabled=True)
    first=delivery(archive,'/simulate','POST');second=delivery(archive,'/simulate','POST')
    assert first['id']==second['id'] and second['duplicate'] and first['state']=='waiting_review'
    assert archive[1].scalar(select(func.count(DeliveryJob.id)))==1
    assert not delivery(archive,actor=2)['jobs']
    configure(archive,expected_version=1,enabled=False)
    assert archive[1].get(DeliveryJob,first['id']).state=='cancelled'

def test_simulation_never_uses_unreleased_report(archive):
    ready(archive);save(archive,preview(archive));configure(archive,enabled=True)
    assert delivery(archive,'/simulate','POST')['state']=='waiting_review'

def test_released_briefing_can_be_prepared_but_provider_remains_blocked(archive):
    from app.report_api import ReleaseInput
    now=datetime.now(timezone.utc);archive[-1][0].published_at=now-timedelta(hours=1);archive[1].commit()
    p=preview(archive,start=now-timedelta(days=1),end=now);made=save(archive,p)
    endpoint(archive[0],'/api/projects/{pid}/reports/{report_id}/release','POST')(pid=archive[2].id,report_id=made['id'],body=ReleaseInput(expected_version=1),user=archive[4][0],session=archive[1])
    configure(archive,enabled=True,destination='fixture@test.invalid',authorized_destination=True)
    result=delivery(archive,'/simulate','POST');job=archive[1].get(DeliveryJob,result['id'])
    assert job.state=='blocked_provider' and job.report_id==made['id'] and job.is_simulation
    assert job.message and len(job.message.encode('utf-16-le'))//2<=3500

def test_send_port_ignores_provider_tokens(archive,monkeypatch):
    for key in ['TELEGRAM_BOT_TOKEN','SENDGRID_API_KEY','NEXO_DELIVERY_ENABLED']:monkeypatch.setenv(key,'SYNTHETIC_NOT_REAL')
    with pytest.raises(DeliveryUnavailable):DisabledSender().send(destination='unused',text='fixture',idempotency_key='fixture')
    with pytest.raises(HTTPException) as e:delivery(archive,'/send','POST')
    assert e.value.status_code==409

def test_old_reports_do_not_invent_new_analytics(archive):
    ready(archive);p=preview(archive);p.pop('content_analytics')
    assert 'antes del desglose' in message_text(p)

def schedule(**args):return SimpleNamespace(timezone='America/Mexico_City',frequency='daily',local_time='07:00',weekday=0,**args)

def test_daily_and_weekday_next_occurrence():
    s=schedule();at=datetime(2026,10,20,12,59,tzinfo=timezone.utc)
    assert next_occurrence(s,at)==datetime(2026,10,20,13,tzinfo=timezone.utc)
    s.frequency='weekdays';assert next_occurrence(s,datetime(2026,10,23,14,tzinfo=timezone.utc)).weekday()==0

def test_weekly_and_dst_skip_nonexistent_hour_and_second_fold():
    s=schedule();s.frequency='weekly';s.weekday=2
    assert next_occurrence(s,datetime(2026,10,20,14,tzinfo=timezone.utc)).weekday()==2
    s.frequency='daily';s.timezone='America/New_York';s.local_time='02:30'
    assert next_occurrence(s,datetime(2026,3,8,6,59,tzinfo=timezone.utc))==datetime(2026,3,9,6,30,tzinfo=timezone.utc)
    s.local_time='01:30';assert next_occurrence(s,datetime(2026,11,1,5,40,tzinfo=timezone.utc)).day==2

def test_database_rejects_non_simulated_jobs(archive):
    configure(archive,enabled=True)
    archive[1].add(DeliveryJob(project_id=archive[2].id,user_id=archive[4][0].id,schedule_version=1,scheduled_for=NOW,channel='email',state='blocked_provider',is_simulation=False))
    with pytest.raises(IntegrityError):archive[1].commit()
    archive[1].rollback()


def test_delivery_backup_restore_preserves_encrypted_preferences_and_labels(archive,monkeypatch):
    from pathlib import Path
    import sqlite3
    from scripts import backup_local as backup
    ready(archive);assess(archive,sentiment='neutral',mockery=False)
    configure(archive,enabled=True,destination='synthetic@test.invalid',authorized_destination=True);delivery(archive,'/simulate','POST')
    private=Path(archive[0].state.engine.url.database).parent;uploads=private/'uploads';uploads.mkdir(exist_ok=True)
    key=private/'fixture.key';key.write_text('synthetic-only')
    raw,manifest=backup.make_archive(private,db_file=Path(archive[0].state.engine.url.database),uploads_directory=uploads,secret_file=key)
    monkeypatch.setattr(backup,'dpapi',lambda value,decrypt=False:value)
    file=private/'delivery-fixture.nexobak';file.write_bytes(backup.MAGIC+raw);restored=backup.restore_backup(file,private/'restored-delivery')
    assert restored['counts']==manifest['counts']
    with sqlite3.connect(private/'restored-delivery/storage/nexo.db') as c:
        assert unseal(c.execute('select destination_ciphertext from briefing_schedules').fetchone()[0])=='synthetic@test.invalid'
        assert c.execute('select sentiment,mockery from content_assessments').fetchone()==('neutral',0)
        assert c.execute('select state,is_simulation from delivery_jobs').fetchone()==('waiting_review',1)
