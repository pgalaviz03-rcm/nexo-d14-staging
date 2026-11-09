"""Real PostgreSQL policies and application contracts on a disposable cluster."""
import os,uuid,json
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
from fastapi import FastAPI,Depends,HTTPException
from sqlalchemy import select,text,func
from sqlalchemy.exc import DBAPIError
from cryptography.fernet import Fernet
from app.database import create_database
from app.models import User,Project,Membership,NewsArticle,SectionMetric
from app.pulse_models import PlatformGrant
from app.configuration import MediaOutlet,IntegrationSetting,IntegrationInput,MediaInput
from app.cloud_workspace import ensure_owner_memberships
from app.platform_api import install_platform_api,ProjectInput,UserInput
from app.configuration_api import install_configuration_api
pytestmark=pytest.mark.skipif(not os.getenv('NEXO_TEST_APP_URL'),reason='Isolated PostgreSQL URLs required')

@pytest.fixture
def pg(tmp_path,monkeypatch):
 assert os.environ['NEXO_TEST_ISOLATED']=='true'
 admin,Admin=create_database(os.environ['NEXO_TEST_OWNER_URL']);runtime,Runtime=create_database(os.environ['NEXO_TEST_APP_URL'])
 nonce=uuid.uuid4().hex[:10]
 with Admin() as s:
  users=[User(email=f'{nonce}-{i}@example.invalid',password_hash='external-auth-only',auth_subject=str(uuid.uuid4()),active=True) for i in range(3)]
  projects=[Project(name='Synthetic '+str(i),slug=nonce+'-'+str(i),status='active') for i in range(2)]
  s.add_all(users+projects);s.flush()
  s.add(PlatformGrant(user_id=users[0].id,active=True))
  s.add_all([Membership(project_id=projects[0].id,user_id=users[0].id,role='admin'),Membership(project_id=projects[0].id,user_id=users[1].id,role='admin'),Membership(project_id=projects[1].id,user_id=users[2].id,role='viewer')]);s.commit()
 monkeypatch.setenv('NEXO_STORAGE_DIR',str(tmp_path/'uploads'));monkeypatch.setenv('NEXO_INTEGRATIONS_ENCRYPTION_KEY',Fernet.generate_key().decode())
 yield SimpleNamespace(admin=admin,Admin=Admin,runtime=runtime,Runtime=Runtime,users=users,projects=projects)
 runtime.dispose();admin.dispose()

def actor(s,u):s.info.update({'nexo.actor_id':str(u.id),'nexo.auth_subject':u.auth_subject})
def allow(pid,user,s,roles=None):
 m=s.scalar(select(Membership).where(Membership.user_id==user.id,Membership.project_id==pid));p=s.get(Project,pid)
 if not m or not p:raise HTTPException(404,'Project unavailable')
 if roles and m.role not in roles:raise HTTPException(403,'Role denied')
 return p,m

def app_for(pg):
 app=FastAPI();app.state.engine=pg.runtime;app.state.SessionLocal=pg.Runtime
 def db():
  with pg.Runtime() as s:yield s
 def current_user():raise AssertionError('Direct test must supply a synthetic user')
 install_platform_api(app,db,current_user);install_configuration_api(app,db,current_user,allow)
 return app

def endpoint(app,path,method='GET'):return next(r.endpoint for r in app.routes if getattr(r,'path',None)==path and method in r.methods)

def test_unidentified_session_sees_no_projects_members_or_secrets(pg):
 with pg.Runtime() as s:
  assert not s.scalars(select(Project)).all()
  assert not s.scalars(select(Membership)).all()
  assert not s.scalars(select(IntegrationSetting)).all()

def test_reader_with_legacy_admin_role_cannot_write_media(pg):
 with pg.Runtime() as s:
  actor(s,pg.users[1]);s.add(MediaOutlet(project_id=pg.projects[0].id,name='Forbidden',name_key='forbidden',channels_json='[]',site_url='',active=True,version=1,updated_by=pg.users[1].id))
  with pytest.raises(DBAPIError):s.commit()

def test_reader_only_sees_assigned_project(pg):
 with pg.Runtime() as s:
  actor(s,pg.users[1]);ids=set(s.scalars(select(Project.id)).all());assert pg.projects[0].id in ids and pg.projects[1].id not in ids

def test_owner_has_all_projects_and_memberships_after_sync(pg):
 with pg.Runtime() as s:
  actor(s,pg.users[0]);ensure_owner_memberships(s,pg.users[0]);assert pg.projects[1].id in set(s.scalars(select(Membership.project_id).where(Membership.user_id==pg.users[0].id)).all())
  s.commit();ensure_owner_memberships(s,pg.users[0]);assert s.scalar(select(func.count(Membership.id)).where(Membership.project_id==pg.projects[1].id,Membership.user_id==pg.users[0].id))==1

def test_owner_creates_project_and_keeps_membership(pg,monkeypatch):
 import app.platform_api as mod
 monkeypatch.setattr(mod,'cloud',lambda:True);app=app_for(pg)
 with pg.Runtime() as s:
  actor(s,pg.users[0]);result=endpoint(app,'/api/platform/projects','POST')(body=ProjectInput(name='New synthetic',slug='new-'+uuid.uuid4().hex[:10],owner_user_id=pg.users[1].id),user=pg.users[0],session=s)
  assert s.scalar(select(Membership).where(Membership.user_id==pg.users[0].id,Membership.project_id==result['id'])).role=='admin'
  assert s.scalar(select(Membership).where(Membership.user_id==pg.users[1].id,Membership.project_id==result['id']))

def test_nonowner_cannot_create_project_even_with_legacy_admin(pg):
 with pg.Runtime() as s:
  actor(s,pg.users[1]);s.add(Project(name='Denied',slug='deny-'+uuid.uuid4().hex[:10]))
  with pytest.raises(DBAPIError):s.commit()

def test_owner_links_supabase_subject_without_auth_password(pg,monkeypatch):
 import app.platform_api as mod
 monkeypatch.setattr(mod,'cloud',lambda:True);app=app_for(pg)
 with pg.Runtime() as s:
  actor(s,pg.users[0]);result=endpoint(app,'/api/platform/users','POST')(body=UserInput(email=uuid.uuid4().hex+'@example.invalid',auth_subject=str(uuid.uuid4())),user=pg.users[0],session=s)
  created=s.get(User,result['id']);assert created.auth_subject and created.password_hash=='external-auth-only'

def test_cloud_user_route_rejects_password_instead_of_creating_local_login(pg,monkeypatch):
 import app.platform_api as mod
 monkeypatch.setattr(mod,'cloud',lambda:True);app=app_for(pg)
 with pg.Runtime() as s:
  actor(s,pg.users[0])
  with pytest.raises(HTTPException) as err:endpoint(app,'/api/platform/users','POST')(body=UserInput(email='invalid@example.invalid',password='synthetic-password-only',auth_subject=str(uuid.uuid4())),user=pg.users[0],session=s)
  assert err.value.status_code==422

def test_owner_cannot_reassign_identity_or_change_password_mapping(pg):
 for column in ['email','auth_subject','password_hash']:
  with pg.Runtime() as s:
   actor(s,pg.users[0])
   with pytest.raises(DBAPIError):s.execute(text(f'UPDATE users SET {column}={column} WHERE id=:uid'),{'uid':pg.users[1].id})

def test_runtime_cannot_elevate_platform_grants_or_write_history(pg):
 for query in ["INSERT INTO platform_grants(user_id,active,scope_bindings) VALUES(:uid,true,'{}')",'UPDATE section_metrics SET nominal_list=nominal_list','UPDATE fidelity_team_observations SET kind=kind']:
  with pg.Runtime() as s:
   actor(s,pg.users[0])
   with pytest.raises(DBAPIError):s.execute(text(query),{'uid':pg.users[1].id})

def test_integration_secrets_encrypted_and_unreadable_to_project_reader(pg,monkeypatch):
 import app.configuration_api as mod
 monkeypatch.setattr(mod,'cloud',lambda:True);app=app_for(pg);pid=pg.projects[0].id
 with pg.Runtime() as s:
  actor(s,pg.users[0]);r=endpoint(app,'/api/projects/{pid}/settings/integrations/{kind}','PUT')(pid=pid,kind='apify',body=IntegrationInput(provider='Apify',secrets={'api_token':'fake-test-token'}),user=pg.users[0],session=s)
  assert r['credentials_saved'] and 'fake-test-token' not in json.dumps(r)
  assert 'fake-test-token' not in s.get(IntegrationSetting,(pid,'apify')).secrets_ciphertext
 with pg.Runtime() as s:
  actor(s,pg.users[1]);assert not s.scalars(select(IntegrationSetting).where(IntegrationSetting.project_id==pid)).all()

def test_media_saved_on_real_postgresql_and_visible_after_new_session(pg,monkeypatch):
 import app.configuration_api as mod
 monkeypatch.setattr(mod,'cloud',lambda:True);app=app_for(pg);pid=pg.projects[0].id
 with pg.Runtime() as s:
  actor(s,pg.users[0]);r=endpoint(app,'/api/projects/{pid}/settings/media','POST')(pid=pid,body=MediaInput(name='Public medium',site_url='https://example.org'),user=pg.users[0],session=s)
 with pg.Runtime() as s:
  actor(s,pg.users[0]);rows=endpoint(app,'/api/projects/{pid}/settings/media')(pid=pid,user=pg.users[0],session=s)['items'];assert any(x['id']==r['id'] for x in rows)
 with pg.Runtime() as s:
  actor(s,pg.users[2]);assert not s.get(MediaOutlet,r['id'])

def test_no_data_api_roles_have_new_table_privileges(pg):
 with pg.admin.connect() as c:
  for role in ['anon','authenticated','service_role']:
   for table in ['integration_settings','media_outlets','fidelity_team_members']:
    assert not c.execute(text("SELECT has_table_privilege(:r,:t,'SELECT')"),{'r':role,'t':table}).scalar()

def test_cloud_bridge_installs_full_workspace_on_existing_dependencies(pg,monkeypatch):
 import app.cloud_workspace as bridge
 monkeypatch.setattr(bridge,'cloud',lambda:True)
 app=FastAPI();app.state.engine=pg.runtime;app.state.SessionLocal=pg.Runtime
 def db():
  with pg.Runtime() as s:yield s
 def current_user(request,authorization=None,session=Depends(db)):return pg.users[0]
 @app.get('/api/projects')
 def projects(user=Depends(current_user),session=Depends(db)):return []
 bridge.install(app)
 paths={getattr(r,'path',None) for r in app.routes}
 assert {'/api/projects/{pid}/settings/media','/api/projects/{pid}/continuity/team/{member_id}/profile','/api/projects/{pid}/library/documents','/api/platform/projects'}.issubset(paths)
