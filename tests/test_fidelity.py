"""Atalaya publications, project isolation, missing values and immutable imports."""
from datetime import datetime,timedelta,timezone
import json,socket
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from app.fidelity import AtalayaPublicationBatch,Publication,FidelityCapture,activity
from app.pulse_models import PlatformGrant
from app.actor_models import ActorProfile
from test_manual_reviews import archive,endpoint
from test_networks import setup,URL

NOW=datetime.now(timezone.utc)-timedelta(minutes=10)
START=NOW-timedelta(days=7)
def batch(actor,**kw):
    values=dict(actor_id=actor,network='facebook',account_url=URL,captured_at=NOW,
        publications=[dict(url='https://facebook.com/fixture/posts/1',published_at=NOW-timedelta(days=1),text='Publicación pública',reactions=10,comments=5,shares=2,followers=100)])
    values.update(kw);return AtalayaPublicationBatch(**values)
def owner(a):
    a[1].add(PlatformGrant(user_id=a[4][0].id,active=True));a[1].commit()
def load(a,b,who=0,pid=None):
    return endpoint(a[0],'/api/projects/{pid}/continuity/atalaya/import','POST')(pid=pid or a[2].id,body=b,user=a[4][who],session=a[1])
def view(a,**kw):
    args=dict(start=START,end=NOW,now=NOW+timedelta(minutes=1));args.update(kw)
    return activity(a[1],a[2].id,**args)
def count(a):return a[1].scalar(select(func.count()).select_from(FidelityCapture))

def test_empty_keeps_missing_unknown(archive):
    setup(archive);p=view(archive)
    assert p['summary']['publications'] is None and p['summary']['interactions'] is None
    assert p['source_kind']=='empty' and not p['publications'] and p['external_calls']==0

def test_source_publications_and_rate(archive):
    actor=setup(archive);owner(archive);load(archive,batch(actor));p=view(archive)
    assert p['summary']['publications']==1 and p['summary']['interactions']==17 and p['summary']['followers']==100
    assert p['summary']['engagement_rate']==17 and p['publications'][0]['engagement_rate']==17
    assert p['source_kind']=='atalaya_import' and p['provider_enabled'] is False

@pytest.mark.parametrize('who',[0,1,2])
def test_every_project_role_without_platform_grant_is_read_only(archive,who):
    actor=setup(archive)
    with pytest.raises(HTTPException) as e:load(archive,batch(actor),who=who)
    assert e.value.status_code==403 and count(archive)==0

def test_owner_revocation_effective(archive):
    actor=setup(archive);owner(archive);g=archive[1].get(PlatformGrant,archive[4][0].id);g.active=False;archive[1].commit()
    with pytest.raises(HTTPException) as e:load(archive,batch(actor))
    assert e.value.status_code==403

def test_duplicate_export_does_not_sum_again(archive):
    actor=setup(archive);owner(archive);b=batch(actor);load(archive,b)
    assert load(archive,b)['duplicates']==1 and count(archive)==1 and view(archive)['summary']['publications']==1

def test_conflicting_same_capture_preserves_history(archive):
    actor=setup(archive);owner(archive);load(archive,batch(actor))
    b=batch(actor);b.publications[0].reactions=99
    with pytest.raises(HTTPException) as e:load(archive,b)
    assert e.value.status_code==409 and view(archive)['summary']['interactions']==17

def test_latest_snapshot_not_sum_of_observations(archive):
    actor=setup(archive);owner(archive);load(archive,batch(actor,captured_at=NOW-timedelta(hours=1)))
    b=batch(actor);b.publications[0].reactions=20;load(archive,b)
    assert count(archive)==2 and view(archive)['summary']['interactions']==27

def test_latest_snapshot_replaces_omitted_publications(archive):
    actor=setup(archive);owner(archive);load(archive,batch(actor,captured_at=NOW-timedelta(hours=1)))
    b=batch(actor);b.publications[0].url='https://facebook.com/fixture/posts/2';load(archive,b)
    assert len(view(archive)['publications'])==1 and view(archive)['publications'][0]['url'].endswith('/2')

def test_negative_sentinel_is_missing_and_partial_not_zero(archive):
    actor=setup(archive);owner(archive);b=batch(actor)
    b=AtalayaPublicationBatch(**{**b.model_dump(), 'publications':[{**b.publications[0].model_dump(),'reactions':-1,'shares':None}]})
    load(archive,b);p=view(archive)
    assert p['summary']['interactions']==5 and p['partial_counters'] and p['publications'][0]['reactions'] is None

def test_all_unknown_counts_and_zero_denominator(archive):
    actor=setup(archive);owner(archive);b=batch(actor);p=b.publications[0]
    p.reactions=p.comments=p.shares=None;p.followers=0;load(archive,b);r=view(archive)
    assert r['summary']['interactions'] is None and r['summary']['engagement_rate'] is None

def test_actual_zero_counters_remain_zero(archive):
    actor=setup(archive);owner(archive);b=batch(actor);p=b.publications[0];p.reactions=p.comments=p.shares=0
    load(archive,b);assert view(archive)['summary']['interactions']==0 and view(archive)['summary']['engagement_rate']==0

def test_missing_selected_account_suppresses_denominator(archive):
    actor=setup(archive);owner(archive);profile=archive[1].get(ActorProfile,actor)
    refs=json.loads(profile.channels_json);refs.append(dict(network='instagram',url='https://instagram.com/fixture',enabled=True));profile.channels_json=json.dumps(refs);archive[1].commit()
    load(archive,batch(actor));r=view(archive)
    assert r['summary']['followers'] is None and r['summary']['engagement_rate'] is None
    assert view(archive,network='facebook')['summary']['followers']==100

def test_foreign_project_actor_and_account_rejected(archive):
    actor=setup(archive);owner(archive)
    with pytest.raises(HTTPException):load(archive,batch(actor),pid=archive[3].id)
    assert count(archive)==0
    with pytest.raises(HTTPException):view(archive,actor_id=99999)
    with pytest.raises(HTTPException):view(archive,account_url='https://facebook.com/unregistered')

def test_unregistered_account_cannot_be_imported(archive):
    actor=setup(archive);owner(archive)
    with pytest.raises(HTTPException):load(archive,batch(actor,account_url='https://facebook.com/unregistered'))
    assert count(archive)==0

def test_disabled_reference_not_visible(archive):
    actor=setup(archive);owner(archive);load(archive,batch(actor));p=archive[1].get(ActorProfile,actor)
    refs=json.loads(p.channels_json);refs[0]['enabled']=False;p.channels_json=json.dumps(refs);archive[1].commit()
    assert not view(archive)['publications']

def test_period_half_open_and_network_filter(archive):
    actor=setup(archive);owner(archive);b=batch(actor)
    b.publications[0].published_at=START;load(archive,b)
    assert view(archive)['summary']['publications']==1 and not view(archive,network='instagram')['publications']
    assert activity(archive[1],archive[2].id,start=START-timedelta(days=1),end=START,now=NOW)['summary']['publications']==0

def test_account_filter_does_not_misattribute_mentions(archive):
    actor=setup(archive);owner(archive);load(archive,batch(actor))
    p=view(archive,account_url=URL);assert p['summary']['mentions'] is None and p['mentions_scope']=='not_attributed_to_account'

@pytest.mark.parametrize('extra',[{'org':[]},{'team':{}},{'token':'not-a-real-key'},{'posture':'positive'},{'project_id':9}])
def test_unknown_batch_fields_rejected(extra):
    with pytest.raises(ValidationError):AtalayaPublicationBatch(**{**batch(1).model_dump(),**extra})

@pytest.mark.parametrize('extra',[{'autores':[]},{'handle':'fixture'},{'postura':'positive'},{'participant_id':4}])
def test_participant_fields_never_enter_ledger(extra):
    row=batch(1).publications[0].model_dump()
    with pytest.raises(ValidationError):Publication(**{**row,**extra})

@pytest.mark.parametrize('field,value',[('reactions',-2),('comments',True),('followers','100'),('shares',1.5)])
def test_invalid_counters_rejected(field,value):
    with pytest.raises(ValidationError):Publication(**{**batch(1).publications[0].model_dump(),field:value})

@pytest.mark.parametrize('url',['http://facebook.com/post','https://localhost/post','https://facebook.com/post?token=abc','https://user:pw@facebook.com/post'])
def test_untrusted_urls_rejected(url):
    with pytest.raises(ValidationError):Publication(**{**batch(1).publications[0].model_dump(),'url':url})

def test_cross_network_post_rejected():
    b=batch(1).model_dump();b['publications'][0]['url']='https://instagram.com/p/example'
    with pytest.raises(ValidationError):AtalayaPublicationBatch(**b)

def test_duplicate_post_dates_and_future_constraints(archive):
    b=batch(1).model_dump();b['publications']*=2
    with pytest.raises(ValidationError):AtalayaPublicationBatch(**b)
    b=batch(1).model_dump();b['publications'][0]['published_at']=NOW.replace(tzinfo=None)
    with pytest.raises(ValidationError):AtalayaPublicationBatch(**b)
    actor=setup(archive);owner(archive)
    with pytest.raises(HTTPException):load(archive,batch(actor,captured_at=NOW+timedelta(days=1)))
    with pytest.raises(HTTPException):view(archive, end=NOW+timedelta(days=1))

def test_import_and_dashboard_do_not_touch_socket(archive,monkeypatch):
    def blocked(*a,**kw):raise AssertionError('No external calls permitted')
    monkeypatch.setattr(socket,'getaddrinfo',blocked)
    actor=setup(archive);owner(archive);load(archive,batch(actor));assert view(archive)['external_calls']==0
