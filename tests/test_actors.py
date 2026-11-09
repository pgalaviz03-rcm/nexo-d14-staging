"""Project-specific public dossiers, safe references and atomic actor lifecycle."""
import json
from datetime import datetime,timezone
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from app.models import AuditEvent
from app.pulse_models import PulseActor,PulseMention,PulseDocument
from app.actor_models import ActorProfile
from app.actors_api import ActorCreate,ProfileUpdate,ActorState,MakePrimary,PublicChannel
from test_manual_reviews import archive,endpoint
from test_pulse import add_actor,post,ingest,call as pulse

def call(a,suffix='',method='GET',actor=0,pid=None,**kwargs):
    return endpoint(a[0],'/api/projects/{pid}/actors'+suffix,method)(pid=pid or a[2].id,user=a[4][actor],session=a[1],**kwargs)
def create(a,name='Actor público A',kind='primary',**values):return call(a,method='POST',body=ActorCreate(name=name,kind=kind,**values))
def item(a,i=None):return next(r for r in call(a)['items'] if i is None or r['id']==i)
def update_profile(a,row,**values):
    fields={k:row[k] for k in ['name','public_role','organization','territory','description','aliases','channels']};fields.update(values)
    return call(a,'/{actor_id}','PUT',actor_id=row['id'],body=ProfileUpdate(**fields,expected_actor_version=row['version'],expected_profile_version=row['profile_version']))
def state(a,row,active):return call(a,'/{actor_id}/state','PATCH',actor_id=row['id'],body=ActorState(active=active,expected_version=row['version']))

def test_empty_directory_is_generic_without_d14_or_demo_seed(archive):
    r=call(archive);assert r['items']==[] and r['project']['name']=='Own' and r['external_calls']==0 and r['can_manage']

def test_create_profile_uses_same_actor_as_pulse_and_survives_reopening(archive):
    made=create(archive,public_role='Función pública',territory='Territorio de ejemplo',organization='Institución',aliases=['Nombre alternativo'],
        channels=[PublicChannel(network='facebook',url='https://www.facebook.com/example.public')])
    p=item(archive);assert p['id']==made['id'] and p['profile_version']==1 and p['channels'][0]['review']=='unreviewed'
    config=pulse(archive,'/config');assert config['actors'][0]['id']==made['id']
    with archive[0].state.SessionLocal() as session:
        row=session.get(ActorProfile,made['id']);assert row.territory=='Territorio de ejemplo' and json.loads(row.aliases_json)==['Nombre alternativo']

def test_legacy_pulse_actor_gets_dossier_without_duplicate(archive):
    made=add_actor(archive);p=item(archive);assert p['profile_version']==0
    update_profile(archive,p,public_role='Representante público')
    assert item(archive)['profile_version']==1 and archive[1].scalar(select(func.count()).select_from(PulseActor))==1

def test_actor_names_are_normalized_and_duplicate_check_shared_with_pulse(archive):
    create(archive,name='  Actor   Público A  ')
    with pytest.raises(HTTPException) as e:create(archive,name='actor público a',kind='comparator')
    assert e.value.status_code==409
    with pytest.raises(HTTPException) as e:add_actor(archive,name='ACTOR PÚBLICO A',kind='comparator')
    assert e.value.status_code==409 and item(archive)['name']=='Actor Público A'

def test_same_public_name_is_allowed_in_separate_projects(archive):
    a=create(archive)
    b=call(archive,method='POST',actor=3,pid=archive[3].id,body=ActorCreate(name='Actor público A',kind='primary'))
    assert a['id']!=b['id'] and len(call(archive)['items'])==1
    assert call(archive,actor=3,pid=archive[3].id)['items'][0]['id']==b['id']

@pytest.mark.parametrize('actor',[1,2])
def test_consultor_and_reader_can_read_but_not_change_configuration(archive,actor):
    create(archive);assert len(call(archive,actor=actor)['items'])==1 and not call(archive,actor=actor)['can_manage']
    with pytest.raises(HTTPException) as e:call(archive,method='POST',actor=actor,body=ActorCreate(name='No autorizado'))
    assert e.value.status_code==403

def test_foreign_membership_never_reveals_directory_or_edits(archive):
    made=create(archive)
    with pytest.raises(HTTPException) as e:call(archive,actor=3)
    assert e.value.status_code==404
    fields=dict(name='Otra ficha',expected_actor_version=1,expected_profile_version=1)
    with pytest.raises(HTTPException) as e:call(archive,'/{actor_id}','PUT',actor_id=made['id'],pid=archive[3].id,actor=3,body=ProfileUpdate(**fields))
    assert e.value.status_code==404

def test_stale_profile_edit_rolls_back_actor_rename(archive):
    create(archive);old=item(archive);update_profile(archive,old,description='Primera revisión')
    with pytest.raises(HTTPException) as e:update_profile(archive,old,name='Nombre obsoleto')
    assert e.value.status_code==409 and item(archive)['name']=='Actor público A' and item(archive)['description']=='Primera revisión'

def test_stale_profile_version_rolls_back_both_records(archive):
    create(archive);p=item(archive);p['profile_version']=99
    with pytest.raises(HTTPException):update_profile(archive,p,name='No debe guardarse')
    p=item(archive);assert p['version']==1 and p['name']=='Actor público A'

def test_archiving_preserves_observations_and_profile(archive):
    made=create(archive);ingest(archive,[post(made['id'],text='Registro ficticio')]);p=item(archive)
    assert p['mentions_in_archive']==1;state(archive,p,False)
    assert not item(archive)['active'] and item(archive)['mentions_in_archive']==1
    assert archive[1].scalar(select(func.count()).select_from(PulseDocument))==1 and archive[1].get(ActorProfile,made['id'])

def test_primary_replacement_is_atomic_and_keeps_observations(archive):
    a=create(archive);b=create(archive,name='Actor público B',kind='comparator');rows=call(archive)['items']
    principal=next(x for x in rows if x['id']==a['id']);target=next(x for x in rows if x['id']==b['id'])
    call(archive,'/{actor_id}/primary','POST',actor_id=b['id'],body=MakePrimary(expected_version=target['version'],previous_primary_id=principal['id'],previous_primary_version=principal['version']))
    assert item(archive,b['id'])['kind']=='primary' and item(archive,a['id'])['kind']=='comparator'
    assert pulse(archive,'/config')['actors'][1]['kind']=='primary'

def test_stale_primary_selection_cannot_demote_current_principal(archive):
    a=create(archive);b=create(archive,name='Actor público B',kind='comparator')
    with pytest.raises(HTTPException) as e:call(archive,'/{actor_id}/primary','POST',actor_id=b['id'],body=MakePrimary(expected_version=1))
    assert e.value.status_code==409 and item(archive,a['id'])['kind']=='primary' and item(archive,b['id'])['kind']=='comparator'

def test_reactivated_former_principal_becomes_comparator_if_another_is_active(archive):
    a=create(archive);state(archive,item(archive),False);b=create(archive,name='Principal nuevo')
    state(archive,item(archive,a['id']),True)
    assert item(archive,a['id'])['kind']=='comparator' and item(archive,b['id'])['kind']=='primary'

@pytest.mark.parametrize('url',[ 'http://facebook.com/example','https://127.0.0.1/example','https://localhost/example',
    'https://facebook.com.evil.invalid/example','https://www.facebook.com/example?access_token=synthetic','https://user:pass@facebook.com/example','https://facebook.com/'])
def test_unsafe_or_mismatched_profile_urls_rejected(url):
    with pytest.raises((ValidationError,ValueError)):PublicChannel(network='facebook',url=url)

def test_reference_review_is_human_status_and_no_fetch_is_needed(archive,monkeypatch):
    import socket
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Network forbidden')))
    create(archive,channels=[PublicChannel(network='x',url='https://x.com/public_example',review='reviewed',enabled=False)])
    c=item(archive)['channels'][0];assert c['review']=='reviewed' and not c['enabled']

def test_duplicate_aliases_channels_and_unknown_fields_rejected():
    with pytest.raises(ValidationError):ActorCreate(name='Actor',aliases=['Alias',' alias '])
    channel=dict(network='x',url='https://x.com/example')
    with pytest.raises(ValidationError):ActorCreate(name='Actor',channels=[channel,channel])
    with pytest.raises(ValidationError):ActorCreate(name='Actor',project_id=999)
    with pytest.raises(ValidationError):PublicChannel(**channel,api_key='synthetic')

def test_profile_cannot_reference_other_project_or_demo_actor(archive):
    made=add_actor(archive)
    archive[1].add(ActorProfile(actor_id=made['id'],project_id=archive[3].id,is_demo=False,updated_by=archive[4][0].id))
    with pytest.raises(IntegrityError):archive[1].commit()
    archive[1].rollback()

def test_no_source_text_or_reference_url_is_logged_in_audit(archive):
    create(archive,description='SYNTHETIC_PUBLIC_DESCRIPTION',channels=[PublicChannel(network='x',url='https://x.com/public_example')])
    targets=' '.join(r.target for r in archive[1].scalars(select(AuditEvent)))
    assert 'SYNTHETIC_PUBLIC_DESCRIPTION' not in targets and 'https://' not in targets
