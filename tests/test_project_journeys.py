"""Cross-module project experiences in isolated, synthetic-only SQLite databases."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select,func
from app.models import Membership,AuditEvent
from app.pulse_models import PlatformGrant
from app.platform_api import ProjectInput
from app.platform_access import bind_projects
from test_manual_reviews import archive,endpoint
from test_pulse import platform

PAGES=['pulse','briefing','actors','summary','sections','networks','continuity','alerts','explorer','reports','account-audit']

def read(a,path,*,user=0,pid=None):
 return endpoint(a[0],'/api/projects/{pid}/'+path)(pid=pid or a[2].id,user=a[4][user],session=a[1])

def matrix(a,*,user=0,pid=None):return {path:read(a,path,user=user,pid=pid) for path in PAGES}

@pytest.mark.parametrize('role',['admin','editor','analyst','viewer'])
def test_every_project_role_can_read_all_screens_with_correct_capabilities(archive,role):
 member=archive[1].scalar(select(Membership).where(Membership.user_id==archive[4][0].id,Membership.project_id==archive[2].id))
 member.role=role;archive[1].commit();before=archive[1].scalar(select(func.count()).select_from(AuditEvent))
 pages=matrix(archive);write=role in {'admin','editor','analyst'};manage=role in {'admin','editor'}
 assert pages['actors']['can_manage']==manage
 assert pages['networks']['can_import']==write and pages['continuity']['can_import']==write
 assert pages['alerts']['can_review']==write and pages['alerts']['can_manage_rules']==manage
 assert pages['briefing']['can_save']==write and pages['explorer']['can_save_report']==write
 assert pages['reports']['can_write']==write and pages['reports']['can_publish']==manage
 assert pages['account-audit']['project_id']==archive[2].id
 assert pages['explorer']['counts']['news']==1
 assert not platform(archive,'session')['is_superadmin']
 assert archive[1].scalar(select(func.count()).select_from(AuditEvent))==before

@pytest.mark.parametrize('path',PAGES)
def test_project_id_in_url_never_gives_a_foreign_client_access(archive,path):
 with pytest.raises(HTTPException) as e:read(archive,path,user=3)
 assert e.value.status_code==404

@pytest.mark.parametrize('path',PAGES)
def test_membership_revocation_blocks_next_module_request(archive,path):
 member=archive[1].scalar(select(Membership).where(Membership.user_id==archive[4][1].id,Membership.project_id==archive[2].id))
 archive[1].delete(member);archive[1].commit()
 with pytest.raises(HTTPException) as e:read(archive,path,user=1)
 assert e.value.status_code==404

def test_new_project_is_empty_across_all_screens_and_does_not_inherit_d14(archive):
 s=archive[1];grant=PlatformGrant(user_id=archive[4][0].id);s.add(grant);s.flush();bind_projects(s,grant);s.commit()
 made=platform(archive,'projects','POST',body=ProjectInput(name='Otro cliente sintético',slug='nuevo-cliente',territory='Otro territorio',owner_user_id=archive[4][1].id))
 pages=matrix(archive,pid=made['id'])
 assert pages['pulse']['metrics']['mentions']==0 and pages['pulse']['actors']==[]
 assert pages['actors']['items']==[] and pages['sections']==[] and pages['summary']['sections']==0
 assert pages['summary']['official_votes'] is None
 assert pages['networks']['accounts']==[] and pages['continuity']['accounts']==[]
 assert pages['alerts']['incidents']==[] and pages['explorer']['items']==[] and pages['reports']['items']==[]
 assert pages['account-audit']['items']==[]
 assert read(archive,'workspace',pid=made['id'])['counts']==dict(news=0,documents=0,historical_sections=0)
 # New client owner sees the same empty space; no implicit membership to other clients.
 assert matrix(archive,user=1,pid=made['id'])['explorer']['items']==[]
 with pytest.raises(HTTPException) as e:read(archive,'actors',user=1,pid=archive[3].id)
 assert e.value.status_code==404
 assert read(archive,'explorer')['counts']['news']==1

def test_superadmin_sees_all_active_projects_but_project_admin_cannot_list_accounts(archive):
 s=archive[1];grant=PlatformGrant(user_id=archive[4][0].id);s.add(grant);s.flush();bind_projects(s,grant);s.commit()
 project_list=endpoint(archive[0],'/api/projects')
 rows=project_list(user=archive[4][0],session=s);assert {p['id'] for p in rows}=={archive[2].id,archive[3].id}
 assert all(p['role']=='admin' for p in rows)
 assert read(archive,'explorer',pid=archive[3].id)['counts']['news']==1
 for route in ['projects','users','projects/{pid}/members']:
  with pytest.raises(HTTPException) as e:platform(archive,route,actor=3,**({'pid':archive[3].id} if '{pid}' in route else {}))
  assert e.value.status_code==403

def test_project_selector_excludes_unassigned_and_inactive_projects(archive):
 s=archive[1];get=endpoint(archive[0],'/api/projects')
 assert [p['id'] for p in get(user=archive[4][1],session=s)]==[archive[2].id]
 archive[2].status='inactive';s.commit()
 assert get(user=archive[4][1],session=s)==[]
 for path in PAGES:
  with pytest.raises(HTTPException) as e:read(archive,path,user=1)
  assert e.value.status_code==404
