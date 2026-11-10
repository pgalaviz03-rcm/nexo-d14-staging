"""Independent social plans, strict provenance and zero execution."""
import json
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from app.configuration import IntegrationInput,IntegrationSetting
from app.apify_catalog import PROCESSES
from test_manual_reviews import archive
from test_fidelity import owner
from test_configuration import save,call,SECRET

def plan(key,**overrides):
    definition=next(p for p in PROCESSES if p['key']==key)
    return dict(actor_ref=definition['actor_ref'],selected=True,max_items=20,daily_limit=1,**overrides)

def test_all_five_networks_available_without_secret_or_execution(archive):
    owner(archive);row=call(archive,'integrations')['items'][0]
    c=row['apify_catalog'];assert set(c['networks'])=={'facebook','instagram','tiktok','x','youtube'}
    assert len(c['processes'])==16 and not c['runtime_enabled']
    assert not row['runtime_enabled'] and not row['connection_verified']
    assert c['schedule']==dict(time='08:00',timezone='America/Mexico_City')

def test_save_all_networks_preserves_independent_limits_and_encrypted_shared_token(archive):
    owner(archive);plans={p['key']:plan(p['key']) for p in PROCESSES}
    row=save(archive,secrets={'api_token':SECRET},apify_processes=plans)
    assert len(row['settings']['apify_processes'])==16
    assert row['credentials_saved'] and SECRET not in json.dumps(row)
    before=archive[1].get(IntegrationSetting,(archive[2].id,'apify')).secrets_ciphertext
    plans=row['settings']['apify_processes'];plans['instagram.comments']['max_items']=55
    row=save(archive,expected_version=1,apify_processes=plans)
    assert row['settings']['apify_processes']['facebook.comments']['max_items']==20
    assert row['settings']['apify_processes']['instagram.comments']['max_items']==55
    assert archive[1].get(IntegrationSetting,(archive[2].id,'apify')).secrets_ciphertext==before

def test_older_token_form_cannot_erase_saved_network_plans(archive):
    owner(archive);save(archive,apify_processes={'tiktok.posts':plan('tiktok.posts')},resource_ref='legacy-facebook-resource')
    row=save(archive,expected_version=1,secrets={'api_token':SECRET},resource_ref='legacy-facebook-resource')
    assert row['settings']['apify_processes']['tiktok.posts']['selected']
    assert row['settings']['resource_ref']=='legacy-facebook-resource'
    row=save(archive,expected_version=2,clear_secrets=True)
    assert not row['credentials_saved'] and row['settings']['apify_processes']['tiktok.posts']['selected']

def test_stale_editor_cannot_overwrite_another_network(archive):
    owner(archive);save(archive,apify_processes={'youtube.posts':plan('youtube.posts')})
    with pytest.raises(HTTPException) as exc:save(archive,expected_version=0,apify_processes={'x.posts':plan('x.posts')})
    assert exc.value.status_code==409
    assert 'youtube.posts' in call(archive,'integrations')['items'][0]['settings']['apify_processes']

@pytest.mark.parametrize('who',[1,2,3])
def test_nonowners_cannot_save_network_plans(archive,who):
    owner(archive)
    with pytest.raises(HTTPException):save(archive,who=who,apify_processes={'instagram.posts':plan('instagram.posts')})

def test_foreign_project_and_other_provider_rejected(archive):
    owner(archive)
    with pytest.raises(HTTPException):save(archive,pid=archive[3].id,apify_processes={'instagram.posts':plan('instagram.posts')})
    with pytest.raises(HTTPException):save(archive,kind='email',apify_processes={'instagram.posts':plan('instagram.posts')})

@pytest.mark.parametrize('plans',[
 {'instagram.posts':dict(actor_ref='apify/facebook-posts-scraper')},
 {'linkedin.posts':dict(actor_ref='community/unknown')},
 {'tiktok.posts':dict(actor_ref='clockworks/tiktok-scraper',max_items=501)},
 {'tiktok.posts':dict(actor_ref='clockworks/tiktok-scraper',daily_limit=3)},
 {'tiktok.posts':dict(actor_ref='clockworks/tiktok-scraper',max_items=True)},
 {'youtube.posts':dict(actor_ref='streamers/youtube-scraper',task_ref='https://example.org/?token=secret')},
 {'x.profile':dict(actor_ref='apidojo/x-api',task_ref='not-a-batch-task')},
 {'instagram.profile':dict(actor_ref='apify/instagram-scraper',enabled=True)},
])
def test_invalid_network_actor_transport_and_limits_rejected(plans):
    with pytest.raises(ValidationError):IntegrationInput(apify_processes=plans)

def test_saving_plan_never_calls_apify(archive,monkeypatch):
    import socket
    def blocked(*a,**kw):raise AssertionError('Provider execution not authorized')
    monkeypatch.setattr(socket,'getaddrinfo',blocked)
    monkeypatch.setattr(socket.socket,'connect',blocked)
    owner(archive);r=save(archive,apify_processes={'facebook.reactions':plan('facebook.reactions')})
    assert r['external_calls']==0 and not r['runtime_enabled'] and not r['connection_verified']
