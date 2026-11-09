"""Whole-project owner capability, empty-project setup, client isolation."""
from datetime import datetime,timedelta,timezone
import json
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.models import Membership,NewsArticle
from app.pulse_models import PlatformGrant,PulseActor
from app.platform_access import bind_projects
from app.platform_api import ProjectInput
from app.client_access import authorize,reader_payload,READER_CONTEXT
from app.fidelity_team import TeamMember
from app.fidelity_team_api import TeamMemberInput
from app.actors_api import ActorCreate
from app.pulse_api import ConfigInput,RuleInput
from test_manual_reviews import archive,endpoint
from test_pulse import platform

CAPABILITIES={'pulse/config':['can_manage','can_import'],'actors':['can_manage'],'networks':['can_import'],
 'continuity':['can_import'],'continuity/activity':['can_import'],'continuity/team':['can_manage'],
 'alerts':['can_review','can_manage_rules'],'briefing':['can_save'],'explorer':['can_save_report'],
 'reports':['can_write','can_publish'],'library/documents':['can_prepare'],'topics':['can_manage','can_review']}
READS=['summary','sections','account-audit','workspace','library/workbooks','pulse','feeds','articles']
WRITES=[('PUT','pulse/config'),('POST','actors'),('POST','continuity/team/roster/member'),('POST','continuity/team/roster/import'),
 ('POST','continuity/atalaya/import'),('POST','networks/captures'),('POST','continuity/captures'),('POST','alerts/evaluate'),
 ('POST','pulse/rules'),('POST','briefing/reports'),('PUT','briefing/delivery'),('POST','reports'),('POST','library/upload'),
 ('POST','datasets'),('POST','feeds'),('POST','articles/import'),('POST','topics')]

def prepare(a):
 s=a[1];grant=PlatformGrant(user_id=a[4][0].id);s.add(grant);s.flush();bind_projects(s,grant);s.commit()
 new=platform(a,'projects','POST',body=ProjectInput(name='Cliente nuevo genérico',slug='empty-client',territory='Territorio propio',owner_user_id=a[4][1].id))
 return new['id']
def read(a,pid,path,who=0):return endpoint(a[0],'/api/projects/{pid}/'+path)(pid=pid,user=a[4][who],session=a[1])

def test_owner_manages_old_and_future_projects_even_with_no_actors(archive):
 pid=prepare(archive);s=archive[1];owner=archive[4][0]
 for project in [archive[2].id,archive[3].id,pid]:
  m=s.scalar(select(Membership).where(Membership.user_id==owner.id,Membership.project_id==project));assert m.role=='admin'
  for path,flags in CAPABILITIES.items():
   payload=read(archive,project,path)
   assert all(payload[flag] is True for flag in flags),(path,project,payload)
  for path in READS:read(archive,project,path)
  for method,path in WRITES:assert authorize(method,f'/api/projects/{project}/{path}',owner,s)
 assert read(archive,pid,'actors')['items']==[]
 assert read(archive,pid,'continuity/team')['can_manage'] and read(archive,pid,'continuity/team')['rows']==[]
 assert read(archive,pid,'continuity/activity')['actor_id'] is None
 assert read(archive,pid,'summary')['sections']==0
 assert read(archive,pid,'library/documents')['items']==[]
 assert read(archive,pid,'reports')['items']==[]

@pytest.mark.parametrize('role',['admin','editor','analyst','viewer'])
def test_client_remains_read_only_in_its_new_project_for_every_screen(archive,role):
 pid=prepare(archive);s=archive[1];user=archive[4][1]
 m=s.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==user.id));m.role=role;s.commit()
 token=READER_CONTEXT.set(True)
 try:
  for path,flags in CAPABILITIES.items():
   payload=reader_payload(read(archive,pid,path,1));assert all(payload[flag] is False for flag in flags),(path,payload)
  for method,path in WRITES:
   with pytest.raises(HTTPException) as exc:authorize(method,f'/api/projects/{pid}/{path}',user,s)
   assert exc.value.status_code==403
 finally:READER_CONTEXT.reset(token)
 for path in CAPABILITIES:
  with pytest.raises(HTTPException) as exc:read(archive,archive[3].id,path,1)
  assert exc.value.status_code==404

def test_owner_can_register_team_before_creating_first_actor(archive):
 pid=prepare(archive);s=archive[1];u=archive[4][0]
 save=endpoint(archive[0],'/api/projects/{pid}/continuity/team/roster/member','POST')
 assert save(pid=pid,body=TeamMemberInput(code='NEW01',name='Colaborador del cliente nuevo',facebook='new.team.account'),user=u,session=s)['inserted']==1
 before=read(archive,pid,'continuity/team');assert before['summary']['members']==1 and before['rows'][0]['participation_percent'] is None
 assert read(archive,archive[2].id,'continuity/team')['rows']==[]
 assert read(archive,pid,'actors')['items']==[]
 actor=endpoint(archive[0],'/api/projects/{pid}/actors','POST')(pid=pid,body=ActorCreate(name='Actor del cliente nuevo',kind='primary',channels=[dict(network='facebook',url='https://facebook.com/new.principal.account')]),user=u,session=s)
 after=read(archive,pid,'continuity/team');assert after['actor_id']==actor['id'] and after['summary']['members']==1 and after['can_manage']
 assert read(archive,archive[2].id,'actors')['items']==[]

def test_configuration_writes_stay_scoped_to_selected_project(archive):
 pid=prepare(archive);s=archive[1];u=archive[4][0]
 endpoint(archive[0],'/api/projects/{pid}/pulse/config','PUT')(pid=pid,body=ConfigInput(territory='Solo el nuevo cliente',expected_version=read(archive,pid,'pulse/config')['version']),user=u,session=s)
 assert read(archive,pid,'pulse/config')['territory']=='Solo el nuevo cliente'
 assert read(archive,archive[2].id,'pulse/config')['territory']!='Solo el nuevo cliente'
 assert read(archive,archive[2].id,'continuity/team')['rows']==[]

def test_revoking_global_owner_keeps_new_project_clients_read_only(archive):
 pid=prepare(archive);s=archive[1];u=archive[4][0];g=s.get(PlatformGrant,u.id);g.active=False;s.commit()
 assert not platform(archive,'session')['is_superadmin']
 for method,path in WRITES:
  with pytest.raises(HTTPException) as exc:authorize(method,f'/api/projects/{pid}/{path}',u,s)
  assert exc.value.status_code==403
 assert not read(archive,pid,'continuity/team')['can_manage']
