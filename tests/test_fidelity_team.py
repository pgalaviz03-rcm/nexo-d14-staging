"""Explicit staff roster, exact accounts, observed counts, project/read-only isolation."""
from datetime import timedelta
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from app.fidelity_team import TeamMember,TeamObservation,TeamEvents,TeamEvent,parse_roster,profile_key,team_dashboard
from app.fidelity_team_api import TeamState
from app.controls import request_body_limit
from test_fidelity import NOW,START,batch,load,owner
from test_networks import setup,URL
from test_manual_reviews import archive,endpoint
from test_workbook_evidence import book

CSV='Código,Nombre,Facebook,Instagram,Teléfono\nE01,Colaborador Uno,equipo.uno,,IGNORED\nE02,Colaborador Dos,equipo.dos,,IGNORED\n'
def drive(coro):
    it=coro.__await__()
    try:it.send(None)
    except StopIteration as done:return done.value
    raise AssertionError('Unexpected asynchronous dependency')
class Upload:
    filename='equipo.csv'
    def __init__(self,raw):self.raw=raw;self.closed=False
    async def read(self,n):return self.raw[:n]
    async def close(self):self.closed=True

def call(a,suffix='',method='GET',who=0,pid=None,**kw):
    return endpoint(a[0],'/api/projects/{pid}/continuity/team'+suffix,method)(pid=pid or a[2].id,user=a[4][who],session=a[1],**kw)
def roster(a,raw=CSV,**kw):
    upload=Upload(raw.encode() if isinstance(raw,str) else raw)
    result=drive(call(a,'/roster/import','POST',file=upload,sheet='',**kw));assert upload.closed;return result

def ready(a):
    actor=setup(a);owner(a);load(a,batch(actor));roster(a)
    return actor,a[1].scalars(select(TeamMember).order_by(TeamMember.id)).all()
def event(member,**kw):
    d=dict(member_id=member,network='facebook',post_url='https://facebook.com/fixture/posts/1',kind='reaction',observed_at=NOW)
    d.update(kw);return d
def events(a,actor,items,**kw):return call(a,'/events','POST',body=TeamEvents(actor_id=actor,events=items),**kw)
def view(a,**kw):
    d=dict(actor_id=0,network='all',account_url='',start=START,end=NOW);d.update(kw)
    return call(a,**d)
def count(a,model):return a[1].scalar(select(func.count()).select_from(model))

@pytest.mark.parametrize('network,value,key',[
 ('facebook','https://www.facebook.com/Equipo.Uno/','equipo.uno'),('facebook','https://facebook.com/profile.php?id=123','id:123'),
 ('facebook','id:123','id:123'),('instagram','@Equipo.Uno','equipo.uno'),('tiktok','https://tiktok.com/@equipo.uno','equipo.uno'),('x','equipo_uno','equipo_uno')])
def test_profile_exact_keys(network,value,key):assert profile_key(network,value)==key
@pytest.mark.parametrize('value',['Nombre Completo','http://facebook.com/user','https://instagram.com/user','https://facebook.com/user?token=secret','https://user:pw@facebook.com/user','https://localhost/user'])
def test_invalid_profile_rejected(value):
    with pytest.raises(ValueError):profile_key('facebook',value)
def test_csv_whitelist_and_stable_codes():
    rows=parse_roster(CSV.encode(),'equipo.csv');assert len(rows)==2 and rows[0]['external_key']=='code:E01'
    assert rows[0]['profiles']=={'facebook':'equipo.uno'} and 'IGNORED' not in json.dumps(rows)
@pytest.mark.parametrize('raw',[
 'Nombre,Facebook\nPersona,\n', 'Nombre,Facebook\nPersona,invalid handle\n',
 'Código,Nombre,Facebook\n1,Uno,uno\n2,Dos,uno\n',
 'Código,Nombre,Facebook\n1,Uno,uno\n1,Dos,dos\n',
 'Nombre,Facebook\nPersona,uno,extra\n', 'Nombre,Facebook\nPersona,"unclosed\n'])
def test_invalid_roster_rejected(raw):
    with pytest.raises(ValueError):parse_roster(raw.encode(),'x.csv')
def xlsx(formula=False):
    return book(rows='<row r="1"><c r="A1" t="inlineStr"><is><t>Nombre</t></is></c><c r="B1" t="inlineStr"><is><t>Facebook</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>Colaborador</t></is></c><c r="B2" t="inlineStr">'+('<f>WEBSERVICE("https://never.test")</f>' if formula else '')+'<is><t>equipo.uno</t></is></c></row>')
def test_xlsx_values_and_sheet():
    assert parse_roster(xlsx(),'equipo.xlsx','Datos')[0]['profiles']=={'facebook':'equipo.uno'}
    with pytest.raises(ValueError):parse_roster(xlsx(),'equipo.xlsx','Otro')
def test_xlsx_formula_not_executed_or_accepted():
    with pytest.raises(ValueError):parse_roster(xlsx(True),'equipo.xlsx')
@pytest.mark.parametrize('who',[0,1,2,3])
def test_roster_write_denied_without_owner(archive,who):
    setup(archive)
    with pytest.raises(HTTPException):roster(archive,who=who)
    assert count(archive,TeamMember)==0
def test_roster_owner_upsert_not_replace_and_repeat(archive):
    ready(archive);assert roster(archive)==dict(inserted=0,updated=0,unchanged=2,external_calls=0)
    p=roster(archive,'Código,Nombre,Facebook\nE01,Nombre actualizado,equipo.uno\n');assert p['updated']==1
    assert count(archive,TeamMember)==2
    assert call(archive,'/roster')['items'][0]['name']=='Nombre actualizado'
def test_roster_same_account_conflict_atomic(archive):
    ready(archive)
    with pytest.raises(HTTPException) as exc:roster(archive,'Código,Nombre,Facebook\nE03,Tercero,nuevo\nE04,Cuarto,equipo.uno\n')
    assert exc.value.status_code==409 and count(archive,TeamMember)==2
@pytest.mark.parametrize('suffix',['/roster','/template'])
def test_private_roster_and_template_owner_only(archive,suffix):
    ready(archive)
    for who in [1,2,3]:
        with pytest.raises(HTTPException):call(archive,suffix,who=who)
    assert call(archive,suffix)
def test_member_state_keeps_history_and_reactivation(archive):
    actor,m=ready(archive);events(archive,actor,[event(m[0].id)])
    call(archive,'/{member_id}','PATCH',member_id=m[0].id,body=TeamState(active=False))
    assert len(view(archive)['rows'])==1 and count(archive,TeamObservation)==1
    call(archive,'/{member_id}','PATCH',member_id=m[0].id,body=TeamState(active=True))
    assert view(archive)['rows'][0]['reaction_posts']==1

def test_reactions_presence_and_comment_events_not_confused(archive):
    actor,m=ready(archive);items=[event(m[0].id),event(m[0].id,kind='comment_presence')]
    assert events(archive,actor,items)['inserted']==2
    p=view(archive,who=1);r=p['rows'][0]
    assert r['reaction_posts']==r['comment_posts']==r['participated_posts']==1 and r['comment_events'] is None
    assert r['participation_percent']==100 and not p['can_manage'] and p['external_calls']==0
    assert 'equipo.uno' not in json.dumps(p) and 'profiles' not in r
    assert events(archive,actor,items)['duplicates']==2 and count(archive,TeamObservation)==2
    events(archive,actor,[event(m[0].id,kind='comment',event_id='c1'),event(m[0].id,kind='comment',event_id='c2')])
    assert view(archive)['rows'][0]['comment_events']==2 and view(archive)['rows'][0]['comment_posts']==1
    assert events(archive,actor,[event(m[0].id,kind='comment',event_id='c1')])['duplicates']==1

def test_observed_update_does_not_double_count(archive):
    actor,m=ready(archive);events(archive,actor,[event(m[0].id,observed_at=NOW-timedelta(minutes=1))])
    events(archive,actor,[event(m[0].id)]);assert count(archive,TeamObservation)==1
    assert view(archive)['rows'][0]['last_observed'].startswith(NOW.isoformat()[:19])
@pytest.mark.parametrize('override',[{'member_id':99999},{'network':'instagram','post_url':'https://instagram.com/p/one'},
 {'post_url':'https://facebook.com/other/posts/1'},{'observed_at':NOW+timedelta(days=1)}, {'observed_at':NOW-timedelta(days=2)}])
def test_invalid_event_rejected_atomically(archive,override):
    actor,m=ready(archive)
    with pytest.raises(HTTPException):events(archive,actor,[event(m[0].id),event(m[0].id,**override)])
    assert count(archive,TeamObservation)==0
@pytest.mark.parametrize('override',[{'kind':'loyalty'},{'opinion':'positive'},{'kind':'comment'}, {'observed_at':NOW.replace(tzinfo=None)}, {'member_id':True}])
def test_contract_rejects_opinion_and_incomplete_events(override):
    with pytest.raises(ValidationError):TeamEvent(**event(1,**override))
@pytest.mark.parametrize('who',[1,2,3])
def test_event_write_owner_only(archive,who):
    actor,m=ready(archive)
    with pytest.raises(HTTPException):events(archive,actor,[event(m[0].id)],who=who)
    assert count(archive,TeamObservation)==0

def test_project_and_period_filters_no_crossing(archive):
    actor,m=ready(archive);events(archive,actor,[event(m[0].id)])
    with pytest.raises(HTTPException):view(archive,who=3)
    with pytest.raises(HTTPException):view(archive,actor_id=actor,pid=archive[3].id)
    from app.models import Membership
    archive[1].add(Membership(project_id=archive[3].id,user_id=archive[4][0].id,role='admin'));archive[1].commit()
    own_other=view(archive,pid=archive[3].id);assert own_other['rows']==[]
    assert view(archive,start=NOW-timedelta(hours=1))['rows'][0]['participated_posts']==0

def test_no_data_stays_unknown_community(archive):
    setup(archive);p=view(archive);assert p['rows']==[] and p['community']['comments'] is None

def test_registered_network_denominator(archive):
    actor,m=ready(archive);events(archive,actor,[event(m[0].id)])
    p=view(archive,network='instagram');r=p['rows'][0]
    assert r['eligible_posts']==0 and r['participation_percent'] is None and r['networks']==[]

def test_upload_limits_are_narrow_and_realistic():
    assert request_body_limit('/api/projects/1/continuity/team/roster/import')==2*1024*1024+16384
    assert request_body_limit('/api/projects/1/continuity/team/events')==1_000_000
    assert request_body_limit('/api/projects/1/continuity/atalaya/import')==1_000_000
    assert request_body_limit('/api/projects/1/continuity/team/wrong')==32000
    assert request_body_limit('/api/projects/1/actors')==32000

@pytest.mark.parametrize('path,size,header,expected',[
 ('/api/projects/1/continuity/team/events',40000,True,204),
 ('/api/projects/1/continuity/team/roster/import',40000,False,204),
 ('/api/projects/1/continuity/team/events',1000001,True,413),
 ('/api/projects/1/continuity/team/events',1000001,False,413),
 ('/api/projects/1/actors',40000,True,413),
 ('/api/projects/1/actors',40000,False,413)])
def test_guard_real_body_stream_limits(monkeypatch,path,size,header,expected):
    import app.controls as controls
    async def immediate(coro,timeout):return await coro
    monkeypatch.setattr(controls.asyncio,'wait_for',immediate)
    sent=[];received=[]
    async def receive():return dict(type='http.request',body=b'x'*size,more_body=False)
    async def send(message):sent.append(message)
    async def target(scope,receive,send):
        message=await receive();received.append(len(message['body']))
        await send(dict(type='http.response.start',status=204,headers=[]));await send(dict(type='http.response.body',body=b''))
    scope=dict(type='http',method='POST',path=path,headers=[(b'content-length',str(size).encode())] if header else [])
    drive(controls.Guard(target,'sha256-fixture')(scope,receive,send))
    assert sent[0]['status']==expected and bool(received)==(expected==204)
    assert b'content-security-policy' in dict(sent[0]['headers'])

# Single-member entry uses the same roster validation, matching and transaction rules.
def manual(a,**kw):
    from app.fidelity_team_api import TeamMemberInput
    who=kw.pop('who',0);pid=kw.pop('pid',None)
    values=dict(code='E03',name='Colaborador Tres',facebook='equipo.tres');values.update(kw)
    return call(a,'/roster/member','POST',who=who,pid=pid,body=TeamMemberInput(**values))

def test_manual_create_repeat_and_update_shared_with_excel(archive):
    ready(archive);assert manual(archive)['inserted']==1
    assert manual(archive)['unchanged']==1 and count(archive,TeamMember)==3
    assert manual(archive,name='Nombre actualizado',instagram='equipo.tres')['updated']==1
    assert roster(archive,'Código,Nombre,Facebook,Instagram\nE03,Nombre actualizado,equipo.tres,equipo.tres\n')['unchanged']==1
    assert count(archive,TeamMember)==3

@pytest.mark.parametrize('who',[1,2,3])
def test_manual_entry_owner_only(archive,who):
    ready(archive)
    with pytest.raises(HTTPException):manual(archive,who=who)
    assert count(archive,TeamMember)==2

@pytest.mark.parametrize('changes',[{'facebook':''},{'facebook':'not an account'},{'facebook':'https://instagram.com/other'}, {'name':'A\nB'}])
def test_manual_invalid_entry_not_saved(archive,changes):
    ready(archive)
    with pytest.raises(HTTPException) as exc:manual(archive,**changes)
    assert exc.value.status_code==422 and count(archive,TeamMember)==2

def test_manual_duplicate_account_cannot_reassign_person(archive):
    ready(archive)
    with pytest.raises(HTTPException) as exc:manual(archive,facebook='equipo.uno')
    assert exc.value.status_code==409 and count(archive,TeamMember)==2

def test_manual_names_are_literal_and_account_urls_normalized(archive):
    ready(archive);manual(archive,name='Equipo, "Álvarez"',facebook='https://www.facebook.com/Equipo.Tres/')
    m=archive[1].scalar(select(TeamMember).where(TeamMember.external_key=='code:E03'))
    assert m.display_name=='Equipo, "Álvarez"' and json.loads(m.profiles_json)=={'facebook':'equipo.tres'}

def test_manual_foreign_project_rejected(archive):
    ready(archive)
    with pytest.raises(HTTPException):manual(archive,pid=archive[3].id)
    assert count(archive,TeamMember)==2

def test_manual_no_code_reuses_same_explicit_record(archive):
    ready(archive);assert manual(archive,code='')['inserted']==1
    assert manual(archive,code='')['unchanged']==1 and count(archive,TeamMember)==3
