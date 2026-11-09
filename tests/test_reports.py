"""Local report snapshots, scoped releases, stale writes and recovery."""
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError

from app.models import Report,ReportVersion,ReportRelease,AuditEvent,Membership
from app.report_api import ReportInput,ReportRevision,ReleaseInput
from test_manual_reviews import archive,endpoint


def call(a,suffix='',method='GET',actor=0,pid=None,**kwargs):
    app,s,p,foreign,users,articles=a
    return endpoint(app,'/api/projects/{pid}/reports'+suffix,method)(pid=pid or p.id,user=users[actor],session=s,**kwargs)


def create(a,**fields):
    return call(a,method='POST',body=ReportInput(title='Informe documental',question='agua',**fields))


def revise(a,rid,expected=1,**fields):
    return call(a,'/{report_id}/versions','POST',report_id=rid,body=ReportRevision(
        title='Versión actualizada',question='agua',expected_version=expected,**fields))


def release(a,rid,expected=1,actor=0):
    return call(a,'/{report_id}/release','POST',actor=actor,report_id=rid,body=ReleaseInput(expected_version=expected))


def detail(a,rid,actor=0):return call(a,'/{report_id}',report_id=rid,actor=actor)


def test_report_saves_only_server_scoped_sources(archive):
    made=create(archive,note='Nota de revisión')
    result=detail(archive,made['id']);snap=result['snapshot']
    assert result['version']==1 and len(result['sha256'])==64
    assert not snap['ai_used'] and snap['external_calls']==0
    assert all(c['project_id']==archive[2].id for c in snap['context']['citations'])
    assert 'Noticia agua 2' not in json.dumps(snap)
    with pytest.raises(ValidationError):ReportInput(title='Informe',question='agua',citations=[{'project_id':999}])


def test_snapshots_survive_changes_to_the_original_source(archive):
    rid=create(archive)['id'];one=detail(archive,rid)
    archive[-1][0].abstract='Texto de agua cambiado después';archive[1].commit()
    revise(archive,rid,note='Nueva nota')
    old=call(archive,'/{report_id}/versions/{version}',report_id=rid,version=1)
    assert old['snapshot']==one['snapshot'] and old['sha256']==one['sha256']
    assert detail(archive,rid)['snapshot']['editorial_note']=='Nueva nota'


def test_stale_revision_does_not_overwrite_or_append(archive):
    rid=create(archive)['id'];revise(archive,rid)
    with pytest.raises(HTTPException) as error:revise(archive,rid,1,note='Stale')
    assert error.value.status_code==409
    assert detail(archive,rid)['version']==2
    assert archive[1].scalar(select(func.count(ReportVersion.id)))==2


def test_viewer_sees_only_released_version_even_with_a_new_draft(archive):
    rid=create(archive)['id']
    assert call(archive,actor=2)['items']==[]
    with pytest.raises(HTTPException) as error:detail(archive,rid,2)
    assert error.value.status_code==404
    release(archive,rid);revise(archive,rid)
    assert detail(archive,rid,2)['version']==1
    assert call(archive,actor=2)['items'][0]['title']=='Informe documental'
    assert call(archive,'/{report_id}/versions',actor=2,report_id=rid)[0]['version']==1
    with pytest.raises(HTTPException) as error:
        call(archive,'/{report_id}/versions/{version}',actor=2,report_id=rid,version=2)
    assert error.value.status_code==404
    release(archive,rid,2)
    assert detail(archive,rid,2)['version']==2


def test_analyst_writes_but_cannot_release_and_viewer_cannot_write(archive):
    made=call(archive,method='POST',actor=1,body=ReportInput(title='Analista',question='agua'))
    with pytest.raises(HTTPException) as error:release(archive,made['id'],actor=1)
    assert error.value.status_code==403
    with pytest.raises(HTTPException) as error:
        call(archive,method='POST',actor=2,body=ReportInput(title='Lector',question='agua'))
    assert error.value.status_code==403


def test_editor_can_release(archive):
    membership=archive[1].scalar(select(Membership).where(Membership.user_id==archive[4][1].id))
    membership.role='editor';archive[1].commit()
    rid=create(archive)['id'];assert release(archive,rid,actor=1)['published_version']==1


@pytest.mark.parametrize('method,suffix,extra',[
 ('GET','',{}),('GET','/{report_id}',{'report_id':1}),
 ('GET','/{report_id}/versions',{'report_id':1}),
 ('GET','/{report_id}/versions/{version}',{'report_id':1,'version':1}),
 ('GET','/{report_id}/versions/{version}/export',{'report_id':1,'version':1}),
 ('POST','',{'body':ReportInput(title='Ajeno',question='agua')}),
 ('POST','/{report_id}/versions',{'report_id':1,'body':ReportRevision(title='Ajeno',question='agua',expected_version=1)}),
 ('POST','/{report_id}/release',{'report_id':1,'body':ReleaseInput(expected_version=1)})])
def test_foreign_members_cannot_access_any_report_route(archive,method,suffix,extra):
    create(archive)
    with pytest.raises(HTTPException) as error:call(archive,suffix,method,actor=3,**extra)
    assert error.value.status_code==404


def test_release_rejects_stale_or_duplicate_publication(archive):
    rid=create(archive)['id'];revise(archive,rid)
    with pytest.raises(HTTPException) as error:release(archive,rid,1)
    assert error.value.status_code==409
    release(archive,rid,2)
    with pytest.raises(HTTPException) as error:release(archive,rid,2)
    assert error.value.status_code==409
    assert archive[1].scalar(select(func.count(ReportRelease.id)))==1


def test_no_matches_cannot_be_saved_as_cited_report(archive):
    with pytest.raises(HTTPException) as error:
        call(archive,method='POST',body=ReportInput(title='Sin datos',question='inexistenteword'))
    assert error.value.status_code==422
    assert archive[1].scalar(select(func.count(Report.id)))==0


def test_invalid_unicode_is_rejected_before_any_write(archive):
    # Request validation rejects the malformed string before the route runs.
    with pytest.raises(ValidationError):create(archive,note='Invalid \ud800 text')
    assert archive[1].scalar(select(func.count(Report.id)))==0


def test_tampered_snapshot_is_not_returned_or_released(archive):
    rid=create(archive)['id'];row=archive[1].scalar(select(ReportVersion));row.payload='{}';archive[1].commit()
    for action in [lambda:detail(archive,rid),lambda:release(archive,rid)]:
        with pytest.raises(HTTPException) as error:action()
        assert error.value.status_code==409


def test_report_version_cannot_reference_a_foreign_project(archive):
    rid=create(archive)['id'];s=archive[1]
    s.add(ReportVersion(project_id=archive[3].id,report_id=rid,version=2,payload='{}',sha256='x',created_by=archive[4][3].id))
    with pytest.raises(IntegrityError):s.commit()
    s.rollback()


def test_export_is_the_stored_snapshot_and_does_not_generate(archive):
    rid=create(archive)['id'];release(archive,rid)
    response=call(archive,'/{report_id}/versions/{version}/export',actor=2,report_id=rid,version=1)
    result=json.loads(response.body)
    assert result['snapshot']==detail(archive,rid,2)['snapshot']
    assert response.headers['cache-control']=='no-store'
    assert 'attachment' in response.headers['content-disposition']


def test_versions_and_publications_survive_reopening(archive):
    rid=create(archive)['id'];release(archive,rid)
    with archive[0].state.SessionLocal() as reopened:
        assert reopened.scalar(select(Report).where(Report.id==rid)).current_version==1
        assert reopened.scalar(select(ReportVersion)).sha256
        assert reopened.scalar(select(ReportRelease)).version==1


def test_report_audit_has_ids_not_content_and_routes_are_append_only(archive):
    rid=create(archive,note='PRIVATE_NOTE')['id'];revise(archive,rid);release(archive,rid,2)
    events=archive[1].scalars(select(AuditEvent)).all()
    assert len(events)==3 and all('PRIVATE_NOTE' not in e.target for e in events)
    routes=[r for r in archive[0].routes if '/reports' in r.path]
    assert all(not {'PUT','PATCH','DELETE'} & r.methods for r in routes)
    assert all({d.call.__name__ for d in r.dependant.dependencies}=={'db','current_user'} for r in routes)


def test_invalid_report_fields_and_version_caps():
    for fields in [dict(title='  ',question='agua'),dict(title='Informe',question='agua',note=None),
                   dict(title='Informe',question='agua',days=2)]:
        with pytest.raises(ValidationError):ReportInput(**fields)
    with pytest.raises(ValidationError):ReportRevision(title='Informe',question='agua',expected_version=50)


def test_report_migration_is_idempotent_and_preserves_data(archive):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    rid=create(archive)['id'];release(archive,rid)
    path=Path(__file__).resolve().parents[1]/'migrations/versions/004_reports.py'
    spec=importlib.util.spec_from_file_location('reports_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with archive[0].state.engine.begin() as connection:
        module.op=Operations(MigrationContext.configure(connection));module.upgrade();module.upgrade()
    assert detail(archive,rid)['version']==1


def test_report_backup_and_isolated_restore_keep_snapshots(archive,tmp_path,monkeypatch):
    import sqlite3
    from scripts import backup_local as backup
    rid=create(archive,note='Nota conservada')['id'];release(archive,rid)
    private=Path(archive[0].state.engine.url.database).parent
    uploads=private/'uploads';uploads.mkdir(exist_ok=True)
    secret=private/'test-session.key';secret.write_text('synthetic-test-only')
    raw,manifest=backup.make_archive(private,db_file=Path(archive[0].state.engine.url.database),
        uploads_directory=uploads,secret_file=secret)
    monkeypatch.setattr(backup,'dpapi',lambda value,decrypt=False:value)
    file=private/'synthetic-report-backup.nexobak';file.write_bytes(backup.MAGIC+raw)
    recovered=backup.restore_backup(file,private/'isolated-restore')
    assert recovered['counts']==manifest['counts']
    with sqlite3.connect(private/'isolated-restore/storage/nexo.db') as db:
        payload=db.execute('select payload from report_versions where report_id=?',(rid,)).fetchone()[0]
        assert json.loads(payload)['editorial_note']=='Nota conservada'
        assert db.execute('select count(*) from report_releases').fetchone()[0]==1
