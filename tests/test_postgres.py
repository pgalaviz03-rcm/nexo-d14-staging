"""Integration tests for a disposable PostgreSQL, never production.
Set NEXO_TEST_APP_URL and NEXO_TEST_OWNER_URL only in an isolated test database.
"""
import os
import pytest
from sqlalchemy import text,select
from app.database import create_database
from app.models import User,Project,Membership,SectionMetric
from app.preflight import check_database

pytestmark=pytest.mark.skipif(not os.getenv('NEXO_TEST_APP_URL'),reason='No PostgreSQL TCP test database configured')


@pytest.fixture
def pg():
    assert os.getenv('NEXO_TEST_ISOLATED')=='true','Disposable DB acknowledgement required'
    owner,Admin=create_database(os.environ['NEXO_TEST_OWNER_URL'])
    engine,Runtime=create_database(os.environ['NEXO_TEST_APP_URL'])
    with Admin() as s:
        u=User(email='pg-test@example.invalid',password_hash='TEST_ONLY')
        p=Project(slug='pg-test',name='Test');s.add_all([u,p]);s.flush()
        s.add(Membership(user_id=u.id,project_id=p.id,role='admin'))
        s.add(SectionMetric(project_id=p.id,section=999,election_year=2024,nominal_list=10,
            territorial_votes=5,polling_places=1,null_votes=0,source='fixture'))
        s.commit();uid=u.id;pid=p.id
    yield engine,Runtime,uid,pid
    engine.dispose();owner.dispose()


def test_actor_survives_commits_and_does_not_leak(pg):
    engine,Runtime,uid,pid=pg
    check_database(engine)
    with Runtime() as s:
        s.info['nexo.actor_id']=str(uid)
        assert s.scalar(select(SectionMetric).where(SectionMetric.project_id==pid))
        s.commit()
        assert s.scalar(select(SectionMetric).where(SectionMetric.project_id==pid))
        s.rollback()
        assert s.scalar(select(SectionMetric).where(SectionMetric.project_id==pid))
    with Runtime() as s:
        assert not s.scalar(select(SectionMetric))
        assert s.execute(text("UPDATE memberships SET role='admin'")).rowcount==0
