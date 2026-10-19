import os,io,tempfile
from pathlib import Path
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from app.main import create_app
from app.models import User,Project,Membership,SectionMetric,Base
from app.security import make_hash

@pytest.fixture
def setup(monkeypatch,tmp_path):
    monkeypatch.setenv('NEXO_SECRET_KEY','test-only-'+'z'*54)
    app=create_app('sqlite:///'+str(tmp_path/'nexo_test.sqlite'),storage_dir=str(tmp_path/'files'))
    with app.state.SessionLocal() as s:
        alice=User(email='alice@test.local',password_hash=make_hash('localpassword12345'))
        bob=User(email='bob@test.local',password_hash=make_hash('localpassword12345'))
        s.add_all([alice,bob]);s.flush()
        a=Project(slug='a',name='Proyecto A');b=Project(slug='b',name='Proyecto B')
        s.add_all([a,b]);s.flush()
        s.add_all([Membership(user_id=alice.id,project_id=a.id,role='admin'),Membership(user_id=bob.id,project_id=b.id,role='viewer')])
        s.add(SectionMetric(project_id=a.id,section=521,election_year=2024,nominal_list=802,territorial_votes=487,polling_places=2,null_votes=17,source='prueba'))
        s.add(SectionMetric(project_id=b.id,section=999,election_year=2024,nominal_list=400,territorial_votes=200,polling_places=1,null_votes=3,source='privado'))
        s.commit();aid=a.id;bid=b.id
    with TestClient(app) as client:yield client,aid,bid

def token(client,email):
    r=client.post('/api/auth/login',json={'email':email,'password':'localpassword12345'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

def test_auth_projects_and_data_isolation(setup):
    c,a,b=setup
    assert c.get('/api/projects').status_code==401
    ah=token(c,'alice@test.local')
    assert [p['slug'] for p in c.get('/api/projects',headers=ah).json()]==['a']
    assert c.get(f'/api/projects/{b}/summary',headers=ah).status_code==404
    assert c.get(f'/api/projects/{b}/sections',headers=ah).status_code==404
    assert c.get(f'/api/projects/{b}/datasets',headers=ah).status_code==404
    assert c.get(f'/api/projects/{a}/sections',headers=ah).json()[0]['id']==521
    bh=token(c,'bob@test.local')
    assert c.get(f'/api/projects/{a}/sections',headers=bh).status_code==404

def test_upload_and_project_boundaries(setup):
    c,a,b=setup
    h=token(c,'alice@test.local')
    content=b'seccion,ejemplo\n521,40\n522,30\n'
    payload={'file':('estudio.csv',content,'text/csv')}
    response=c.post(f'/api/projects/{a}/datasets',headers=h,files=payload)
    assert response.status_code==200,response.text
    assert response.json()['records']==2
    assert c.post(f'/api/projects/{a}/datasets',headers=h,files=payload).status_code==409
    assert len(c.get(f'/api/projects/{a}/datasets',headers=h).json())==1
    assert c.get(f'/api/projects/{b}/datasets',headers=h).status_code==404
    viewer=token(c,'bob@test.local')
    assert c.post(f'/api/projects/{b}/datasets',headers=viewer,files=payload).status_code==403

def test_validation_invalid_file(setup):
    c,a,b=setup
    h=token(c,'alice@test.local')
    assert c.post(f'/api/projects/{a}/datasets',headers=h,files={'file':('malware.exe',b'malware')}).status_code==400
    assert c.post(f'/api/projects/{a}/datasets',headers=h,files={'file':('bad.kml',b'not xml')}).status_code==422
    assert c.post(f'/api/projects/{a}/datasets',headers=h,files={'file':('x.csv',b'a,b\n1,2', 'text/csv')}).status_code==200
    assert c.post(f'/api/projects/{a}/datasets',headers=h,files={'file':('too-large.csv',b'c'*(12*1024*1024+1))}).status_code==413
