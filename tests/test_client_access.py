import json
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.client_access import authorize,reader_payload,READER_CONTEXT,ClientReadOnly
from app.models import Membership
from app.pulse_models import PlatformGrant
from app.report_api import ReportInput,ReleaseInput
from test_manual_reviews import archive,endpoint

@pytest.mark.parametrize('role',['admin','editor','analyst','viewer'])
@pytest.mark.parametrize('method,path',[('POST','datasets'),('POST','reports'),('PUT','pulse/config'),
 ('POST','actors'),('POST','alerts/evaluate'),('PUT','briefing/delivery')])
def test_every_nonowner_role_is_read_only(archive,role,method,path):
    s=archive[1];m=s.scalar(select(Membership).where(Membership.user_id==archive[4][0].id,Membership.project_id==archive[2].id));m.role=role;s.commit()
    with pytest.raises(HTTPException) as e:authorize(method,f'/api/projects/{archive[2].id}/{path}',archive[4][0],s)
    assert e.value.status_code==403

@pytest.mark.parametrize('method,path',[('GET','pulse'),('GET','reports'),('GET','sections/export'),
 ('POST','knowledge/context'),('POST','knowledge/critical-audit'),('POST','explorer/selection')])
def test_client_can_observe_search_and_download(archive,method,path):
    assert authorize(method,f'/api/projects/{archive[2].id}/{path}',archive[4][0],archive[1]) is False

def test_platform_grant_controls_writes_and_revocation(archive):
    s=archive[1];u=archive[4][0];g=PlatformGrant(user_id=u.id,active=True,scope_bindings='{}');s.add(g);s.commit()
    assert authorize('POST',f'/api/projects/{archive[2].id}/datasets',u,s)
    g.active=False;s.commit()
    with pytest.raises(HTTPException):authorize('POST',f'/api/projects/{archive[2].id}/datasets',u,s)

def test_foreign_project_is_hidden_before_write_denial(archive):
    with pytest.raises(HTTPException) as e:authorize('POST',f'/api/projects/{archive[3].id}/reports',archive[4][0],archive[1])
    assert e.value.status_code==404

def test_private_delivery_configuration_is_not_a_client_read(archive):
    with pytest.raises(HTTPException) as e:authorize('GET',f'/api/projects/{archive[2].id}/briefing/delivery',archive[4][0],archive[1])
    assert e.value.status_code==403

def test_reader_capabilities_and_role_cannot_grant_editing():
    r=reader_payload(dict(role='admin',can_write=True,can_read=True,nested=[dict(can_manage=True,can_import=True)]))
    assert r==dict(role='viewer',can_write=False,can_read=True,nested=[dict(can_manage=False,can_import=False)])

def test_effective_viewer_cannot_read_drafts_and_membership_is_not_mutated(archive):
    a,s,p,_,users,_=archive
    make=endpoint(a,'/api/projects/{pid}/reports','POST')
    made=make(pid=p.id,body=ReportInput(title='Private draft',question='agua'),user=users[0],session=s)
    token=READER_CONTEXT.set(True)
    try:
        listing=endpoint(a,'/api/projects/{pid}/reports')(pid=p.id,user=users[0],session=s)
        assert not listing['can_write'] and listing['items']==[]
        with pytest.raises(HTTPException):endpoint(a,'/api/projects/{pid}/reports/{report_id}')(pid=p.id,report_id=made['id'],user=users[0],session=s)
        with pytest.raises(HTTPException):make(pid=p.id,body=ReportInput(title='Cannot save',question='agua'),user=users[0],session=s)
    finally:READER_CONTEXT.reset(token)
    assert s.scalar(select(Membership).where(Membership.user_id==users[0].id,Membership.project_id==p.id)).role=='admin'

def test_released_report_is_visible_with_read_only_capabilities(archive):
    a,s,p,_,users,_=archive
    made=endpoint(a,'/api/projects/{pid}/reports','POST')(pid=p.id,body=ReportInput(title='Visible report',question='agua'),user=users[0],session=s)
    endpoint(a,'/api/projects/{pid}/reports/{report_id}/release','POST')(pid=p.id,report_id=made['id'],body=ReleaseInput(expected_version=1),user=users[0],session=s)
    token=READER_CONTEXT.set(True)
    try:
        got=endpoint(a,'/api/projects/{pid}/reports/{report_id}')(pid=p.id,report_id=made['id'],user=users[0],session=s)
        assert got['snapshot']['title']=='Visible report'
    finally:READER_CONTEXT.reset(token)

def drive(task):
    with pytest.raises(StopIteration):task.send(None)

def test_transport_blocks_legacy_endpoint_before_it_runs(archive):
    a,s,p,_,users,_=archive;seen=[];messages=[]
    def identity(**kw):return kw['session'].get(type(users[0]),users[0].id)
    async def downstream(*args):seen.append('unsafe endpoint ran')
    async def send(m):messages.append(m)
    async def receive():return dict(type='http.request',body=b'')
    middleware=ClientReadOnly(downstream,a.state.SessionLocal,identity)
    drive(middleware(dict(type='http',method='POST',path=f'/api/projects/{p.id}/datasets',headers=[]),receive,send))
    assert not seen and messages[0]['status']==403

def test_transport_filters_json_and_sets_context_for_later_routes(archive):
    a,s,p,_,users,_=archive;messages=[];observed=[]
    def identity(**kw):return kw['session'].get(type(users[0]),users[0].id)
    async def downstream(scope,receive,send):
        observed.append(READER_CONTEXT.get());raw=json.dumps(dict(can_manage=True,role='analyst',connector=dict(actor_ref='private-reference'))).encode()
        await send(dict(type='http.response.start',status=200,headers=[(b'content-type',b'application/json'),(b'content-length',str(len(raw)).encode())]))
        await send(dict(type='http.response.body',body=raw[:10],more_body=True));await send(dict(type='http.response.body',body=raw[10:]))
    async def send(m):messages.append(m)
    async def receive():return dict(type='http.request',body=b'')
    drive(ClientReadOnly(downstream,a.state.SessionLocal,identity)(dict(type='http',method='GET',path=f'/api/projects/{p.id}/pulse/config',headers=[]),receive,send))
    packet=json.loads(messages[-1]['body']);assert packet==dict(can_manage=False,role='viewer',connector={})
    assert observed==[True] and not READER_CONTEXT.get()
    assert int(dict(messages[0]['headers'])[b'content-length'])==len(messages[-1]['body'])
