"""Local canonical configuration, secret redaction and social-media news ingress."""
from datetime import datetime,timedelta,timezone
import json,socket
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from app.configuration import IntegrationInput,IntegrationSetting,MediaInput,MediaBatch,MediaOutlet,MediaArticleLink,secret_cipher
from app.models import AuditEvent,NewsArticle
from app.fidelity_team import TeamMember
from app.client_access import authorize
from test_manual_reviews import archive,endpoint
from test_fidelity import owner,START,NOW
from test_fidelity_team import ready,event,events,view

SECRET='fixture-key-never-live'
def call(a,suffix,method='GET',who=0,pid=None,**kwargs):
 return endpoint(a[0],'/api/projects/{pid}/settings/'+suffix,method)(pid=pid or a[2].id,user=a[4][who],session=a[1],**kwargs)
def save(a,kind='apify',who=0,pid=None,**kwargs):return call(a,'integrations/{kind}','PUT',who=who,pid=pid,kind=kind,body=IntegrationInput(**kwargs))
def media(a,**kwargs):
 fields=dict(name='Medio de prueba',site_url='https://example.org',channels=[dict(network='facebook',url='https://facebook.com/fixture.medium')]);fields.update(kwargs)
 return call(a,'media','POST',body=MediaInput(**fields))
def body(**kwargs):
 d=dict(network='facebook',account_url='https://facebook.com/fixture.medium',captured_at=NOW,
 items=[dict(external_id='post-1',url='https://facebook.com/fixture.medium/posts/1',title='Titular de servicios públicos',text='Documento de mantenimiento público.',published_at=NOW-timedelta(hours=1))]);d.update(kwargs);return MediaBatch(**d)
def ingest(a,m,b=None,**kwargs):return call(a,'media/{media_id}/publications/import','POST',media_id=m,body=b or body(),**kwargs)

def test_catalogue_has_all_channels_and_no_runtime_or_calls(archive):
 owner(archive);p=call(archive,'integrations');assert len(p['items'])==8
 assert all(not r['runtime_enabled'] and not r['connection_verified'] and not r['credentials_saved'] for r in p['items'])
 assert p['external_calls']==0
@pytest.mark.parametrize('who',[0,1,2,3])
def test_settings_private_without_platform_grant(archive,who):
 for suffix in ['integrations','media']:
  with pytest.raises(HTTPException):call(archive,suffix,who=who)
 with pytest.raises(HTTPException):save(archive,who=who,secrets={'api_token':SECRET})

def test_secret_encrypted_never_in_response_or_audit(archive):
 owner(archive);p=save(archive,provider='Apify',secrets={'api_token':SECRET})
 assert p['credentials_saved'] and not p['connection_verified'] and p['version']==1
 row=archive[1].get(IntegrationSetting,(archive[2].id,'apify'))
 assert SECRET not in row.secrets_ciphertext and json.loads(secret_cipher().decrypt(row.secrets_ciphertext.encode()))=={'api_token':SECRET}
 assert SECRET not in json.dumps(p) and SECRET not in json.dumps(call(archive,'integrations'))
 assert SECRET not in '\n'.join(r.target for r in archive[1].scalars(select(AuditEvent)).all())

def test_secret_preserve_clear_and_optimistic_update(archive):
 owner(archive);save(archive,secrets={'api_token':SECRET});p=save(archive,provider='Nuevo nombre',expected_version=1)
 assert p['credentials_saved'] and p['version']==2
 with pytest.raises(HTTPException) as e:save(archive,expected_version=1)
 assert e.value.status_code==409
 p=save(archive,expected_version=2,clear_secrets=True);assert not p['credentials_saved'] and p['version']==3
 assert archive[1].get(IntegrationSetting,(archive[2].id,'apify')).secrets_ciphertext==''

def test_integration_does_not_follow_foreign_project_or_unknown_key(archive):
 owner(archive)
 with pytest.raises(HTTPException):save(archive,pid=archive[3].id,secrets={'api_token':SECRET})
 with pytest.raises(HTTPException):save(archive,kind='unknown')
 with pytest.raises(HTTPException):save(archive,secrets={'bot_token':SECRET})
 assert archive[1].scalar(select(func.count()).select_from(IntegrationSetting))==0
@pytest.mark.parametrize('values',[{'monthly_budget_usd':10},{'enabled':True},{'base_url':'http://example.org'},{'base_url':'https://127.0.0.1'},
 {'base_url':'https://example.org?token=private'},{'max_items':501},{'clear_secrets':True,'secrets':{'api_token':SECRET}}])
def test_invalid_or_spending_configuration_rejected(values):
 with pytest.raises(ValidationError):IntegrationInput(**values)

def test_media_accounts_persist_with_versions_and_disable(archive):
 owner(archive);m=media(archive);assert m['channels'][0]['url']=='https://facebook.com/fixture.medium'
 assert len(call(archive,'media')['items'])==1
 p=call(archive,'media/{media_id}','PUT',media_id=m['id'],body=MediaInput(name=m['name'],site_url=m['site_url'],channels=m['channels'],active=False,expected_version=1));assert p['version']==2 and not p['active']
 with pytest.raises(HTTPException):ingest(archive,m['id'])
 assert archive[1].scalar(select(func.count()).select_from(NewsArticle))==2

def test_media_rejects_duplicate_names_and_stale_version(archive):
 owner(archive);m=media(archive)
 with pytest.raises(HTTPException) as e:media(archive,name='MEDIO DE PRUEBA')
 assert e.value.status_code==409
 with pytest.raises(HTTPException):call(archive,'media/{media_id}','PUT',media_id=m['id'],body=MediaInput(name='Otro',site_url='https://example.org',expected_version=0))
 assert call(archive,'media')['items'][0]['name']==m['name']
@pytest.mark.parametrize('values',[{'channels':[dict(network='facebook',url='https://instagram.com/medium')]},{'site_url':'https://localhost'}, {'channels':[],'site_url':''}])
def test_media_reference_validation(values):
 d=dict(name='Medio',site_url='https://example.org');d.update(values)
 with pytest.raises(ValidationError):MediaInput(**d)

def test_social_media_import_searchable_without_rss_and_idempotent(archive):
 owner(archive);m=media(archive);result=ingest(archive,m['id']);assert result==dict(inserted=1,duplicates=0,external_calls=0)
 assert ingest(archive,m['id'])['duplicates']==1
 row=archive[1].scalar(select(NewsArticle).where(NewsArticle.origin=='media_social'));assert row.feed_id is None and row.publisher==m['name']
 from app.evidence_search import retrieve_context
 packet=retrieve_context(archive[1],archive[2].id,'mantenimiento',archive[0].state if False else '.',source_kind='news')
 assert any(c['title']=='Titular de servicios públicos' for c in packet['citations'])
 assert archive[1].scalar(select(func.count()).select_from(MediaArticleLink))==1

def test_media_import_account_and_project_boundaries(archive):
 owner(archive);m=media(archive)
 for b,kw in [(body(account_url='https://facebook.com/not.registered'),{}),(body(),{'pid':archive[3].id}),(body(captured_at=datetime.now(timezone.utc)+timedelta(days=1)),{})]:
  with pytest.raises(HTTPException):ingest(archive,m['id'],b,**kw)
 assert archive[1].scalar(select(func.count()).select_from(MediaArticleLink))==0
@pytest.mark.parametrize('who',[1,2,3])
def test_media_ingress_never_writable_by_client(archive,who):
 owner(archive);m=media(archive)
 with pytest.raises(HTTPException):ingest(archive,m['id'],who=who)
 with pytest.raises(HTTPException):authorize('POST',f'/api/projects/{archive[2].id}/settings/media',archive[4][who],archive[1])

def profile(a,mid,who=0,pid=None,**kwargs):
 d=dict(actor_id=0,network='all',account_url='',start=START,end=NOW,page=1);d.update(kwargs)
 return endpoint(a[0],'/api/projects/{pid}/continuity/team/{member_id}/profile')(pid=pid or a[2].id,member_id=mid,user=a[4][who],session=a[1],**d)

def test_team_profile_reader_counts_and_exact_registered_accounts(archive):
 actor,m=ready(archive);events(archive,actor,[event(m[0].id),event(m[0].id,kind='comment_presence')])
 p=profile(archive,m[0].id,who=1);assert p['name']==m[0].display_name and p['accounts']==[dict(network='facebook',url='https://facebook.com/equipo.uno')]
 assert p['summary']['reaction_posts']==1 and p['items'][0]['reaction_recorded'] and p['items'][0]['comment_recorded']
 assert p['items'][0]['identified_comments']==0 and p['summary']['comment_events'] is None and p['external_calls']==0
 assert p['total_publications']==1 and p['items'][0]['url'].endswith('/posts/1')

def test_team_profile_foreign_and_unregistered_people_have_no_endpoint(archive):
 actor,m=ready(archive)
 with pytest.raises(HTTPException):profile(archive,m[0].id,who=3)
 with pytest.raises(HTTPException):profile(archive,m[0].id,pid=archive[3].id)
 with pytest.raises(HTTPException):profile(archive,999999)
 assert profile(archive,m[0].id)['items']==[]

def test_team_profile_period_and_pagination(archive):
 actor,m=ready(archive);events(archive,actor,[event(m[0].id,kind='comment',event_id='source-c1')])
 p=profile(archive,m[0].id);assert p['items'][0]['identified_comments']==1
 assert profile(archive,m[0].id,start=NOW-timedelta(minutes=1))['items']==[]
 assert profile(archive,m[0].id,page=2)['items']==[]
 with pytest.raises(HTTPException):profile(archive,m[0].id,page=0)

def test_preparation_and_import_do_not_make_network_calls(archive,monkeypatch):
 def blocked(*a,**kw):raise AssertionError('No provider calls authorized')
 monkeypatch.setattr(socket,'getaddrinfo',blocked);owner(archive);save(archive,secrets={'api_token':SECRET});m=media(archive);ingest(archive,m['id'])
 assert call(archive,'integrations')['external_calls']==0

def test_validation_errors_never_echo_incoming_secret(archive):
 from fastapi.exceptions import RequestValidationError
 from starlette.requests import Request
 from test_fidelity_team import drive
 handler=archive[0].exception_handlers[RequestValidationError]
 request=Request(dict(type='http',path='/api/projects/1/settings/integrations/apify',headers=[],method='PUT',scheme='http',server=('localhost',8002),query_string=b''))
 response=drive(handler(request,RequestValidationError([dict(type='value_error',loc=['body'],input={'secrets':{'api_token':SECRET}},msg='Bad')])))
 assert response.status_code==422 and SECRET.encode() not in response.body and b'input' not in response.body

def test_same_social_account_cannot_be_configured_twice(archive):
 owner(archive);media(archive)
 with pytest.raises(HTTPException) as e:media(archive,name='Otro nombre para la misma cuenta')
 assert e.value.status_code==409
 assert len(call(archive,'media')['items'])==1

def test_media_import_conflict_rolls_back_entire_batch(archive):
 owner(archive);m=media(archive);ingest(archive,m['id']);items=body().model_dump()['items']
 second={**items[0],'external_id':'post-2','url':'https://facebook.com/fixture.medium/posts/2'}
 conflict={**items[0],'url':'https://facebook.com/fixture.medium/posts/DIFFERENT'}
 with pytest.raises(HTTPException) as e:ingest(archive,m['id'],body(items=[second,conflict]))
 assert e.value.status_code==409
 assert archive[1].scalar(select(func.count()).select_from(MediaArticleLink))==1
 assert archive[1].scalar(select(func.count()).select_from(NewsArticle).where(NewsArticle.origin=='media_social'))==1

def test_duplicate_article_keeps_existing_editorial_record(archive):
 import hashlib
 owner(archive);m=media(archive);p=body().items[0]
 existing=NewsArticle(project_id=archive[2].id,title='Titular conservado',url=p.url,url_hash=hashlib.sha256(p.url.encode()).hexdigest(),publisher='Archivo previo',abstract='Texto revisado',origin='rss')
 archive[1].add(existing);archive[1].commit();assert ingest(archive,m['id'])['inserted']==0
 archive[1].refresh(existing);assert existing.title=='Titular conservado' and existing.origin=='rss' and existing.abstract=='Texto revisado'

def test_configuration_is_local_only(archive,monkeypatch):
 owner(archive);monkeypatch.setenv('NEXO_ENV','staging')
 with pytest.raises(HTTPException) as e:save(archive,secrets={'api_token':SECRET})
 assert e.value.status_code==409 and archive[1].scalar(select(func.count()).select_from(IntegrationSetting))==0

def test_config_forms_exist_once_inside_owner_configuration_page():
 from html.parser import HTMLParser
 from pathlib import Path
 class Position(HTMLParser):
  def __init__(self):super().__init__();self.section='';self.forms={}
  def handle_starttag(self,t,a):
   d=dict(a)
   if t=='section':self.section=d.get('id','')
   if t=='form' and 'id' in d:
    assert d['id'] not in self.forms
    self.forms[d['id']]=self.section
 html=(Path(__file__).resolve().parents[1]/'static/index.html').read_text(encoding='utf-8');p=Position();p.feed(html)
 expected=['actorForm','pulseConfigForm','teamMemberForm','teamRosterForm','teamSourceForm','addRssFeed','alertsRuleForm','platformProjectForm','platformUserForm','platformMemberForm','deliveryForm','topicCreate','settingsIntegrationForm','settingsMediaForm','pulseImportForm','fidelityImportForm','networksImportForm','continuityImportForm','settingsMediaImportForm','uploadDataset']
 assert all(p.forms[k]=='platform' for k in expected)
 assert not any(k in p.forms for k in ['pulseActorForm','pulseRuleForm','pulseAccountForm','platformBrandForm'])
 assert 'data-settings-tab="integrations"' in html and 'data-settings-tab="media"' in html

def test_editing_one_secret_preserves_other_blank_fields(archive):
 owner(archive);save(archive,kind='storage',secrets={'access_key':'fixture-access','secret_key':'fixture-secret'})
 save(archive,kind='storage',expected_version=1,secrets={'access_key':'fixture-access-replaced'})
 row=archive[1].get(IntegrationSetting,(archive[2].id,'storage'))
 assert json.loads(secret_cipher().decrypt(row.secrets_ciphertext.encode()))=={'access_key':'fixture-access-replaced','secret_key':'fixture-secret'}

def test_encryption_key_rotation_requires_explicit_clear_before_replacement(archive,monkeypatch):
 owner(archive);save(archive,secrets={'api_token':SECRET});monkeypatch.setenv('NEXO_SECRET_KEY','different-fixture-key-'+('z'*40))
 with pytest.raises(HTTPException) as e:save(archive,expected_version=1,secrets={'api_token':'fixture-replaced'})
 assert e.value.status_code==409
 assert save(archive,expected_version=1,clear_secrets=True)['version']==2
 assert save(archive,expected_version=2,secrets={'api_token':'fixture-replaced'})['credentials_saved']

def test_whatsapp_credentials_prepare_only_the_connection_not_delivery(archive):
 owner(archive);p=save(archive,kind='whatsapp',provider='WhatsApp',account_ref='fixture-business-account',secrets={'access_token':SECRET})
 assert p['credentials_saved'] and not p['runtime_enabled'] and not p['connection_verified']
 row=archive[1].get(IntegrationSetting,(archive[2].id,'whatsapp'))
 assert SECRET not in row.secrets_ciphertext
 assert json.loads(secret_cipher().decrypt(row.secrets_ciphertext.encode()))=={'access_token':SECRET}

def test_media_validation_error_is_actionable_without_echoing_payload(archive):
 from fastapi.exceptions import RequestValidationError
 from starlette.requests import Request
 from test_fidelity_team import drive
 request=Request(dict(type='http',path='/api/projects/1/settings/media/1/publications/import',headers=[],method='POST',scheme='http',server=('localhost',8002),query_string=b''))
 response=drive(archive[0].exception_handlers[RequestValidationError](request,RequestValidationError([dict(type='datetime_type',loc=['body','items',0,'published_at'],input='do-not-echo-fixture',msg='Invalid')])))
 assert response.status_code==422 and b'do-not-echo-fixture' not in response.body
 assert 'fecha de publicación' in json.loads(response.body)['detail']

def test_uncompleted_example_template_cannot_add_fictional_news():
 with pytest.raises(ValidationError):body(items=[dict(external_id='REEMPLAZAR_ID',url='https://facebook.com/fixture/posts/REEMPLAZAR_ID',title='Ejemplo',published_at=NOW)])
