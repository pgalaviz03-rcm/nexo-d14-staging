"""Source-backed brief cuts, report freezing and project/role boundaries."""
from datetime import datetime,timedelta,timezone
import json
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy import select,func
from app.briefing import build_briefing
from app.briefing_api import BriefingSave
from app.models import NewsArticle,Report,ReportVersion,AuditEvent
from app.report_api import ReportRevision,ReleaseInput
from app.review_api import ReviewInput
from test_manual_reviews import archive,endpoint,add_topic,write

NOW=datetime(2026,10,20,18,tzinfo=timezone.utc)

def ready(a):
    a[-1][0].published_at=NOW-timedelta(hours=2);a[-1][0].ingested_at=NOW-timedelta(hours=1)
    a[-1][1].published_at=NOW-timedelta(hours=2);a[1].commit()

def preview(a,actor=0,pid=None,**values):
    params=dict(start=NOW-timedelta(days=1),end=NOW);params.update(values)
    return endpoint(a[0],'/api/projects/{pid}/briefing')(pid=pid or a[2].id,user=a[4][actor],session=a[1],**params)

def body(packet,**values):
    return BriefingSave(start=packet['filters']['start'],end=packet['filters']['end'],preview_sha256=packet['preview_sha256'],title='Briefing documental',**values)

def save(a,packet,actor=0,pid=None,**values):
    return endpoint(a[0],'/api/projects/{pid}/briefing/reports','POST')(pid=pid or a[2].id,user=a[4][actor],session=a[1],body=body(packet,**values))

def detail(a,rid,actor=0):
    return endpoint(a[0],'/api/projects/{pid}/reports/{report_id}')(pid=a[2].id,report_id=rid,user=a[4][actor],session=a[1])

def test_briefing_is_project_scoped_and_generic(archive):
    ready(archive);p=preview(archive)
    assert p['project_name']=='Own' and p['news_count']==1 and p['news'][0]['title']=='Noticia agua 1'
    assert p['review_status']==dict(unreviewed=1,reviewed=0,needs_check=0)
    assert all(c['project_id']==archive[2].id for c in p['citations'])
    assert 'Noticia agua 2' not in json.dumps(p) and not p['ai_used'] and p['external_calls']==0

def test_empty_cut_does_not_invent_briefing_or_score(archive):
    ready(archive);p=preview(archive,start=NOW-timedelta(hours=1))
    assert p['news_count']==0 and p['citations']==[] and p['pulse']['metrics']['score'] is None
    with pytest.raises(HTTPException) as e:save(archive,p)
    assert e.value.status_code==422 and archive[1].scalar(select(func.count(Report.id)))==0

def test_review_statuses_and_manual_topics_are_counted(archive):
    ready(archive);t=add_topic(archive,'Servicios públicos')
    write(archive,ReviewInput(expected_version=0,status='needs_check',topic_ids=[t['id']],note='Revisar la fuente'))
    p=preview(archive)
    assert p['review_status']['needs_check']==1 and p['topics'][0]['name']=='Servicios públicos'
    assert p['topics'][0]['count']==1 and p['news'][0]['review_status']=='needs_check'

def test_cut_uses_ingestion_only_when_publication_missing_and_excludes_end(archive):
    ready(archive);row=archive[-1][0];row.published_at=None;row.ingested_at=NOW;archive[1].commit()
    assert preview(archive)['news_count']==0
    row.ingested_at=NOW-timedelta(minutes=1);archive[1].commit();p=preview(archive)
    assert p['news_without_publication_date']==1 and p['news'][0]['date_basis']=='ingestion'

def test_bounded_headlines_do_not_truncate_counts(archive):
    ready(archive)
    for i in range(10):archive[1].add(NewsArticle(project_id=archive[2].id,title='Nota '+str(i),url='https://example.org/n/'+str(i),url_hash='n'+str(i),publisher='Fixture',abstract='',origin='csv',published_at=NOW-timedelta(minutes=i+1)))
    archive[1].commit();p=preview(archive)
    assert p['news_count']==11 and len(p['news'])==8 and p['coverage']['news_truncated']
    assert sum(s['count'] for s in p['sources'])==11

def test_preview_hash_ignores_preparation_clock_and_role_flags(archive):
    ready(archive);a=preview(archive);b=preview(archive,actor=2)
    assert a['preview_sha256']==b['preview_sha256'] and a['can_save'] and not b['can_save']

def test_only_explicit_real_pulse_content_is_included(archive):
    ready(archive)
    endpoint(archive[0],'/api/projects/{pid}/pulse/demo','POST')(pid=archive[2].id,user=archive[4][0],session=archive[1])
    p=preview(archive)
    assert p['pulse']['metrics']['mentions']==0 and not any(c['citation'].startswith('P') for c in p['citations'])

def test_cut_freezes_report_sources_and_manual_note(archive):
    ready(archive);p=preview(archive);made=save(archive,p,note='Nota editorial de prueba');snap=detail(archive,made['id'])['snapshot']
    assert snap['mode']=='local_documentary_briefing_v1' and snap['editorial_note']=='Nota editorial de prueba'
    assert snap['briefing']['preview_sha256']==p['preview_sha256'] and not made['published']
    archive[-1][0].abstract='Fuente modificada después';archive[1].commit()
    assert detail(archive,made['id'])['snapshot']==snap

def test_changed_source_rejects_stale_preview_without_report_writes(archive):
    ready(archive);p=preview(archive);archive[-1][0].abstract='Otra versión';archive[1].commit()
    with pytest.raises(HTTPException) as e:save(archive,p,note='Mi nota')
    assert e.value.status_code==409 and archive[1].scalar(select(func.count(Report.id)))==0

def test_saved_briefing_obeys_existing_reader_release_boundary(archive):
    ready(archive);made=save(archive,preview(archive),actor=1)
    with pytest.raises(HTTPException) as e:detail(archive,made['id'],actor=2)
    assert e.value.status_code==404
    endpoint(archive[0],'/api/projects/{pid}/reports/{report_id}/release','POST')(pid=archive[2].id,report_id=made['id'],user=archive[4][0],session=archive[1],body=ReleaseInput(expected_version=1))
    assert detail(archive,made['id'],actor=2)['snapshot']['briefing']['news_count']==1

def test_viewer_cannot_save(archive):
    ready(archive)
    with pytest.raises(HTTPException) as e:save(archive,preview(archive),actor=2)
    assert e.value.status_code==403

@pytest.mark.parametrize('method',['GET','POST'])
def test_foreign_project_access_is_denied(archive,method):
    ready(archive)
    with pytest.raises(HTTPException) as e:
        if method=='GET':preview(archive,actor=3)
        else:save(archive,preview(archive),actor=3)
    assert e.value.status_code==404

def test_browser_cannot_supply_its_own_citations_or_counts(archive):
    ready(archive);fields=body(preview(archive)).model_dump()
    with pytest.raises(ValidationError):BriefingSave(**fields,citations=[{'project_id':123}])
    with pytest.raises(ValidationError):BriefingSave(**fields,news_count=99999)

def test_snapshot_size_limit_is_applied_before_creating_report(archive,monkeypatch):
    from app import briefing_api
    ready(archive);p=preview(archive);monkeypatch.setattr(briefing_api,'MAX_PAYLOAD_BYTES',100)
    with pytest.raises(HTTPException) as e:save(archive,p)
    assert e.value.status_code==422 and archive[1].scalar(select(func.count(Report.id)))==0

def test_generic_report_editor_cannot_replace_a_briefing_cut(archive):
    ready(archive);made=save(archive,preview(archive))
    with pytest.raises(HTTPException) as e:endpoint(archive[0],'/api/projects/{pid}/reports/{report_id}/versions','POST')(pid=archive[2].id,report_id=made['id'],user=archive[4][0],session=archive[1],body=ReportRevision(title='Nuevo título',question='agua',expected_version=1))
    assert e.value.status_code==409 and detail(archive,made['id'])['version']==1

def test_audit_does_not_contain_note_or_source_text(archive):
    ready(archive);save(archive,preview(archive),note='PRIVATE_EDITORIAL_NOTE')
    event=archive[1].scalar(select(AuditEvent).where(AuditEvent.action=='briefing.save'))
    assert 'PRIVATE' not in event.target and ':v1' in event.target

@pytest.mark.parametrize('fields',[dict(start=NOW.replace(tzinfo=None)),dict(end=NOW-timedelta(days=2))])
def test_invalid_windows_are_rejected(archive,fields):
    ready(archive)
    with pytest.raises(HTTPException) as e:preview(archive,**fields)
    assert e.value.status_code==422


def test_local_read_cut_uses_an_actual_sqlite_snapshot(archive):
    ready(archive);preview(archive)
    assert archive[1].connection().connection.driver_connection.in_transaction


def test_local_save_takes_write_lock_before_recomputing_cut(archive):
    ready(archive);p=preview(archive);archive[1].rollback()
    statements=[];driver=archive[1].connection().connection.driver_connection
    driver.set_trace_callback(statements.append)
    try:save(archive,p)
    finally:driver.set_trace_callback(None)
    assert next(sql for sql in statements if sql.startswith('BEGIN'))=='BEGIN IMMEDIATE'


def test_briefing_backup_and_restore_preserve_frozen_cut(archive,monkeypatch):
    import sqlite3
    from pathlib import Path
    from scripts import backup_local as backup
    ready(archive);made=save(archive,preview(archive),note='Nota de recuperación ficticia')
    private=Path(archive[0].state.engine.url.database).parent;uploads=private/'uploads';uploads.mkdir(exist_ok=True)
    key=private/'fixture.key';key.write_text('synthetic-only')
    raw,manifest=backup.make_archive(private,db_file=Path(archive[0].state.engine.url.database),uploads_directory=uploads,secret_file=key)
    monkeypatch.setattr(backup,'dpapi',lambda value,decrypt=False:value)
    file=private/'fixture.nexobak';file.write_bytes(backup.MAGIC+raw)
    restored=backup.restore_backup(file,private/'restored');assert restored['counts']==manifest['counts']
    with sqlite3.connect(private/'restored/storage/nexo.db') as c:
        payload=json.loads(c.execute('select payload from report_versions where report_id=?',(made['id'],)).fetchone()[0])
        assert payload['briefing']['news_count']==1 and payload['editorial_note']=='Nota de recuperación ficticia'
