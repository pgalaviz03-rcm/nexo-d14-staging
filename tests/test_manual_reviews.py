"""Durable project-scoped labels, optimistic edits and read-only history API."""
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.main import create_app
from app.models import User,Project,Membership,NewsArticle,Topic,ArticleReview,ReviewTopic,ReviewChange
from app.review_api import TopicInput,TopicUpdate,ReviewInput


@pytest.fixture
def archive(tmp_path,monkeypatch):
    monkeypatch.setenv('NEXO_ENV','local');monkeypatch.setenv('NEXO_LOCAL_WORKSPACE','true')
    app=create_app('sqlite:///'+str(tmp_path/'reviews.sqlite'),str(tmp_path/'uploads'))
    with app.state.SessionLocal() as s:
        users=[User(email=role+'@test.invalid',password_hash='unused',active=True)
               for role in ('admin','analyst','viewer','foreign')]
        p=Project(slug='own',name='Own');foreign=Project(slug='other',name='Other')
        s.add_all(users+[p,foreign]);s.flush()
        s.add_all([Membership(project_id=p.id,user_id=u.id,role=role)
                   for u,role in zip(users[:3],('admin','analyst','viewer'))])
        s.add(Membership(project_id=foreign.id,user_id=users[3].id,role='admin'))
        articles=[NewsArticle(project_id=project.id,title='Noticia agua '+str(n),url='https://example.org/'+str(n),
                             url_hash=str(n),publisher='Fixture',origin='csv',abstract='Cobertura documental')
                  for n,project in enumerate((p,foreign),1)]
        s.add_all(articles);s.commit()
        yield app,s,p,foreign,users,articles
    app.state.engine.dispose()


def endpoint(app,path,method='GET'):
    return next(r.endpoint for r in app.routes if r.path==path and method in r.methods)


def add_topic(archive,name='Agua'):
    app,s,p,foreign,users,articles=archive
    return endpoint(app,'/api/projects/{pid}/topics','POST')(p.id,TopicInput(name=name),users[0],s)


def write(archive,body,*,actor=0,article=None,pid=None):
    app,s,p,foreign,users,articles=archive
    return endpoint(app,'/api/projects/{pid}/reviews/{article_id}','PUT')(
        pid or p.id,article or articles[0].id,body,users[actor],s)


def test_topic_names_deduplicate_after_normalization(archive):
    first=add_topic(archive,'  Agua   pública ')
    assert first['name']=='Agua pública' and first['version']==1
    with pytest.raises(HTTPException) as rejected:add_topic(archive,'AGUA pública')
    assert rejected.value.status_code==409


def test_review_survives_reopening_and_tracks_versions(archive):
    app,s,p,foreign,users,articles=archive;t=add_topic(archive)
    one=write(archive,ReviewInput(expected_version=0,topic_ids=[t['id']],note='Fuente revisada'))
    two=write(archive,ReviewInput(expected_version=1,topic_ids=[],status='needs_check',note='Falta confirmar fecha'))
    assert (one['version'],two['version'])==(1,2)
    with app.state.SessionLocal() as reopened:
        review=reopened.scalar(select(ArticleReview).where(ArticleReview.article_id==articles[0].id))
        assert review.note=='Falta confirmar fecha' and review.version==2
        revisions=reopened.scalars(select(ReviewChange).order_by(ReviewChange.version)).all()
        assert len(revisions)==2 and json.loads(revisions[0].snapshot)['topics'][0]['name']=='Agua'
        assert reopened.scalar(select(ReviewTopic.review_id)) is None


def test_stale_edit_cannot_overwrite_saved_review(archive):
    write(archive,ReviewInput(expected_version=0,note='Primero'))
    write(archive,ReviewInput(expected_version=1,note='Segundo'))
    with pytest.raises(HTTPException) as rejected:write(archive,ReviewInput(expected_version=1,note='Viejo'))
    assert rejected.value.status_code==409
    assert archive[1].scalar(select(ArticleReview)).note=='Segundo'
    assert len(archive[1].scalars(select(ReviewChange)).all())==2


def test_topic_edit_conflicts_and_history_keeps_old_name(archive):
    app,s,p,foreign,users,articles=archive;t=add_topic(archive)
    write(archive,ReviewInput(expected_version=0,topic_ids=[t['id']]))
    edit=endpoint(app,'/api/projects/{pid}/topics/{topic_id}','PUT')
    edited=edit(p.id,t['id'],TopicUpdate(name='Servicios públicos',active=True,expected_version=1),users[0],s)
    assert edited['version']==2
    with pytest.raises(HTTPException) as rejected:
        edit(p.id,t['id'],TopicUpdate(name='Nombre viejo',active=True,expected_version=1),users[0],s)
    assert rejected.value.status_code==409
    assert json.loads(s.scalar(select(ReviewChange)).snapshot)['topics'][0]['name']=='Agua'


def test_archived_topic_retained_but_cannot_be_assigned_anew(archive):
    app,s,p,foreign,users,articles=archive;t=add_topic(archive)
    write(archive,ReviewInput(expected_version=0,topic_ids=[t['id']]))
    endpoint(app,'/api/projects/{pid}/topics/{topic_id}','PUT')(
        p.id,t['id'],TopicUpdate(name='Agua',active=False,expected_version=1),users[0],s)
    write(archive,ReviewInput(expected_version=1,topic_ids=[t['id']],note='Conserva etiqueta histórica'))
    write(archive,ReviewInput(expected_version=2,topic_ids=[]))
    with pytest.raises(HTTPException) as rejected:write(archive,ReviewInput(expected_version=3,topic_ids=[t['id']]))
    assert rejected.value.status_code==422


@pytest.mark.parametrize('role_index',[1,2])
def test_only_administrative_roles_manage_topics(archive,role_index):
    app,s,p,foreign,users,articles=archive
    with pytest.raises(HTTPException) as rejected:
        endpoint(app,'/api/projects/{pid}/topics','POST')(p.id,TopicInput(name='Agua'),users[role_index],s)
    assert rejected.value.status_code==403


def test_analyst_can_review_viewer_cannot(archive):
    assert write(archive,ReviewInput(expected_version=0),actor=1)['version']==1
    with pytest.raises(HTTPException) as rejected:write(archive,ReviewInput(expected_version=1),actor=2)
    assert rejected.value.status_code==403


def test_foreign_project_and_article_are_hidden(archive):
    app,s,p,foreign,users,articles=archive
    with pytest.raises(HTTPException) as rejected:write(archive,ReviewInput(expected_version=0),pid=foreign.id)
    assert rejected.value.status_code==404
    with pytest.raises(HTTPException) as rejected:write(archive,ReviewInput(expected_version=0),article=articles[1].id)
    assert rejected.value.status_code==404


def test_cross_project_topic_rejected_by_api_and_database(archive):
    app,s,p,foreign,users,articles=archive
    t=endpoint(app,'/api/projects/{pid}/topics','POST')(foreign.id,TopicInput(name='Otro proyecto'),users[3],s)
    with pytest.raises(HTTPException) as rejected:write(archive,ReviewInput(expected_version=0,topic_ids=[t['id']]))
    assert rejected.value.status_code==422
    write(archive,ReviewInput(expected_version=0))
    rid=s.scalar(select(ArticleReview.id))
    s.add(ReviewTopic(review_id=rid,topic_id=t['id'],project_id=p.id))
    with pytest.raises(IntegrityError):s.commit()
    s.rollback()


def test_filters_and_history_remain_scoped(archive):
    app,s,p,foreign,users,articles=archive;t=add_topic(archive)
    write(archive,ReviewInput(expected_version=0,topic_ids=[t['id']],status='needs_check'))
    listing=endpoint(app,'/api/projects/{pid}/reviews')
    assert len(listing(p.id,status='needs_check',topic_id=t['id'],user=users[2],session=s)['articles'])==1
    assert listing(p.id,status='unreviewed',user=users[2],session=s)['articles']==[]
    history=endpoint(app,'/api/projects/{pid}/reviews/{article_id}/history')
    assert history(p.id,articles[0].id,users[2],s)['changes'][0]['actor_id']==users[0].id
    with pytest.raises(HTTPException) as rejected:history(p.id,articles[1].id,users[0],s)
    assert rejected.value.status_code==404
    assert not any(r.path.endswith('/history') and ('PUT' in r.methods or 'DELETE' in r.methods) for r in app.routes)


def test_composite_reference_rejects_foreign_article_even_without_api(archive):
    app,s,p,foreign,users,articles=archive
    s.add(ArticleReview(project_id=p.id,article_id=articles[1].id,status='reviewed',reviewed_by=users[0].id))
    with pytest.raises(IntegrityError):s.commit()
    s.rollback()


def test_reopening_an_old_schema_creates_review_tables_without_changing_news(tmp_path,monkeypatch):
    from sqlalchemy import create_engine,text
    from app.models import Base
    url='sqlite:///'+str(tmp_path/'old.sqlite')
    engine=create_engine(url)
    core=[t for t in Base.metadata.sorted_tables if t.name not in {'topics','article_reviews','review_topics','review_changes'}]
    Base.metadata.create_all(engine,tables=core)
    with engine.begin() as conn:
        conn.execute(text('DROP INDEX uq_article_id_project_review'))
        conn.execute(text("INSERT INTO projects(id,slug,name,status) VALUES(1,'old','Old','active')"))
        conn.execute(text("INSERT INTO news_articles(project_id,title,url,url_hash,publisher,abstract,origin) VALUES(1,'Original','https://example.org/old','old','Source','','csv')"))
    engine.dispose();monkeypatch.setenv('NEXO_ENV','local')
    app=create_app(url,str(tmp_path/'uploads'))
    with app.state.SessionLocal() as session:
        assert session.scalar(select(NewsArticle)).title=='Original'
        assert session.scalar(select(ArticleReview)) is None
        assert session.execute(text("SELECT count(*) FROM sqlite_master WHERE type='index' AND name='uq_article_id_project_review'")).scalar()==1
    app.state.engine.dispose()


def test_local_migration_is_idempotent(archive):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    app=archive[0]
    path=Path(__file__).resolve().parents[1]/'migrations/versions/003_manual_reviews.py'
    spec=importlib.util.spec_from_file_location('review_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with app.state.engine.begin() as connection:
        module.op=Operations(MigrationContext.configure(connection));module.upgrade();module.upgrade()
    assert add_topic(archive)['name']=='Agua'


def test_null_note_rejected_before_any_review_is_written(archive):
    with pytest.raises(HTTPException) as rejected:
        write(archive,ReviewInput(expected_version=0,note='Texto\x00inválido'))
    assert rejected.value.status_code==422
    assert archive[1].scalar(select(ArticleReview)) is None
