"""Measured corpus metrics, strict offline imports and multi-client boundaries."""
from datetime import datetime,timedelta,timezone
import json
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from app.apify_port import ImportBatch,PublicPost,DisabledApifyReader,ApifyUnavailable,ConnectorPlan,normalize_export
from app.pulse_api import ActorInput,ActorUpdate,Classification,ConfigInput,RuleInput,AccountInput
from app.platform_api import ProjectInput,MemberInput,UserInput,UserState,BrandInput
from app.pulse_models import PulseActor,PulseMention,PulseDocument,PulseBatch,PlatformGrant,PulseAccount
from app.models import Membership,User
from test_manual_reviews import archive,endpoint

NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)

def call(a,suffix='',method='GET',actor=0,pid=None,**kwargs):
    return endpoint(a[0],'/api/projects/{pid}/pulse'+suffix,method)(pid=pid or a[2].id,user=a[4][actor],session=a[1],**kwargs)

def platform(a,suffix,method='GET',actor=0,**kwargs):
    return endpoint(a[0],'/api/platform/'+suffix,method)(user=a[4][actor],session=a[1],**kwargs)

def add_actor(a,name='Actor público A',kind='primary',pid=None,actor=0):
    return call(a,'/actors','POST',pid=pid,actor=actor,body=ActorInput(name=name,kind=kind))

def post(actor,external='one',at=None,**fields):
    return PublicPost(network='facebook',external_id=external,url='https://example.org/p/'+external,
        title='Contenido público '+external,published_at=at or NOW-timedelta(hours=1),collected_at=NOW,
        actor_ids=[actor],**fields)

def ingest(a,posts):return call(a,'/import','POST',body=ImportBatch(items=posts))

def dashboard(a,actor_id=0,demo=False,**fields):
    params=dict(actor_id=actor_id,start=NOW-timedelta(days=1),end=NOW,network='all',demo=demo);params.update(fields)
    return call(a,**params)

def classify_all(a,label='positive',where=None):
    rows=a[1].scalars(select(PulseMention).where(PulseMention.project_id==a[2].id)).all()
    for row in rows:
        if where and not where(row):continue
        call(a,'/documents/{document_id}/actors/{actor_id}/classification','PUT',
             document_id=row.document_id,actor_id=row.actor_id,body=Classification(sentiment=label,emotion='joy',expected_version=row.version))


def test_empty_observatory_does_not_invent_mood_reach_or_alerts(archive):
    packet=dashboard(archive)
    assert packet['metrics']['mentions']==0 and packet['metrics']['score'] is None
    assert packet['metrics']['share'] is None and packet['active_alerts'] is None
    assert not packet['accounts'] and not packet['actors'] and packet['external_calls']==0
    assert all(h['views'] is None for h in packet['headlines'])


def test_dedup_and_actor_share_have_explicit_denominator(archive):
    a=add_actor(archive)['id'];b=add_actor(archive,'Actor B','comparator')['id']
    ingest(archive,[post(a,'1'),post(a,'2'),post(a,'3')])
    other=post(a,'4').model_copy(update={'actor_ids':[a,b]});ingest(archive,[other])
    assert ingest(archive,[other])['duplicates']==1
    packet=dashboard(archive,actor_id=a)
    assert packet['metrics']['mentions']==4 and packet['universe_mentions']==5
    assert packet['metrics']['share']==80 and packet['metrics']['score'] is None


def test_score_coverage_and_ninety_day_baseline(archive):
    actor=add_actor(archive)['id']
    call(archive,'/config','PUT',body=ConfigInput(min_classified=3))
    ingest(archive,[post(actor,str(i)) for i in range(3)]+[post(actor,'old'+str(i),NOW-timedelta(days=5)) for i in range(3)])
    classify_all(archive,'positive')
    old_ids=set(archive[1].scalars(select(PulseDocument.id).where(PulseDocument.published_at<NOW-timedelta(days=1))))
    classify_all(archive,'negative',where=lambda row:row.document_id in old_ids)
    packet=dashboard(archive,actor_id=actor)
    assert packet['metrics']['score']==100 and packet['metrics']['baseline_score']==0
    assert packet['metrics']['score_delta']==100 and packet['metrics']['classification_coverage']==100
    assert packet['emotions_classified']==3 and packet['emotions'][0]['percentage']==100


def test_window_is_half_open_and_network_filter_matches_comparators(archive):
    actor=add_actor(archive)['id']
    ingest(archive,[post(actor,'start',NOW-timedelta(days=1)),post(actor,'end',NOW)])
    assert dashboard(archive)['metrics']['mentions']==1
    assert dashboard(archive,network='press')['metrics']['mentions']==0


def test_missing_baseline_and_small_samples_stay_unknown(archive):
    actor=add_actor(archive)['id'];ingest(archive,[post(actor)])
    classify_all(archive)
    packet=dashboard(archive,actor_id=actor)
    assert packet['metrics']['classified']==1 and packet['metrics']['score'] is None
    assert packet['metrics']['score_delta'] is None and packet['emotions']==[]


def test_config_and_actor_updates_reject_stale_writes(archive):
    actor=add_actor(archive)
    call(archive,'/actors/{actor_id}','PUT',actor_id=actor['id'],body=ActorUpdate(name='Actor renombrado',kind='primary',expected_version=1))
    with pytest.raises(HTTPException) as error:
        call(archive,'/actors/{actor_id}','PUT',actor_id=actor['id'],body=ActorUpdate(name='Viejo',kind='primary',expected_version=1))
    assert error.value.status_code==409
    call(archive,'/config','PUT',body=ConfigInput(territory='Otro territorio'))
    with pytest.raises(HTTPException) as error:call(archive,'/config','PUT',body=ConfigInput())
    assert error.value.status_code==409


def test_only_one_active_primary_actor_per_project(archive):
    add_actor(archive)
    with pytest.raises(HTTPException) as error:add_actor(archive,'Segunda persona','primary')
    assert error.value.status_code==409


def test_source_metrics_update_without_rewriting_original_text_or_double_counting(archive):
    actor=add_actor(archive)['id'];ingest(archive,[post(actor,views=10)])
    item=post(actor,views=40).model_copy(update={'collected_at':NOW+timedelta(hours=1),'title':'Título editado'})
    ingest(archive,[item]);packet=dashboard(archive)
    assert packet['metrics']['mentions']==1 and packet['headlines'][0]['views'] is None
    assert archive[1].scalar(select(PulseDocument.views))==40
    assert packet['headlines'][0]['title']=='Contenido público one'


def test_rules_count_triggered_findings_not_configured_rules(archive):
    actor=add_actor(archive)['id'];ingest(archive,[post(actor,str(i)) for i in range(3)])
    for metric,threshold in [('mentions',3),('mention_spike',50)]:
        call(archive,'/rules','POST',body=RuleInput(actor_id=actor,name='Regla '+metric,metric=metric,threshold=threshold,min_mentions=1))
    result=dashboard(archive)
    assert result['rules_configured']==2 and result['alerts_evaluated']==1 and result['active_alerts']==1


def test_account_snapshots_do_not_sum_audiences_and_preserve_missing_metrics(archive):
    actor=add_actor(archive)['id']
    for days,followers in [(2,100),(0,115)]:
        call(archive,'/accounts','POST',body=AccountInput(actor_id=actor,network='facebook',url='https://example.org/account',
            captured_at=NOW-timedelta(days=days,hours=1),followers=followers))
    result=dashboard(archive)['accounts'][0]
    assert result['followers_delta']==15
    assert set(result['metrics'])=={'followers','posts','interactions','metrics_from','metrics_to'}
    assert result['metrics']['posts'] is None and result['metrics']['interactions'] is None


def test_pulse_headlines_are_recent_not_ranked_by_unavailable_audiences(archive):
    actor=add_actor(archive)['id']
    ingest(archive,[post(actor,'old-high-views',NOW-timedelta(hours=3),views=900000),
                    post(actor,'new',NOW-timedelta(minutes=10))])
    result=dashboard(archive)
    assert result['headlines'][0]['title']=='Contenido público new'
    assert result['headlines'][0]['source']=='example.org'
    assert all(row['views'] is None and row['rank_basis']=='date_only' for row in result['headlines'])


def test_pulse_supported_account_counters_do_not_expose_reach_or_impressions(archive):
    actor=add_actor(archive)['id']
    call(archive,'/accounts','POST',body=AccountInput(actor_id=actor,network='facebook',url='https://example.org/account',
        captured_at=NOW-timedelta(hours=1),followers=100,posts=12,interactions=55,views=90000,reach=80000,impressions=100000))
    result=dashboard(archive)['accounts'][0]['metrics']
    assert result['followers']==100 and result['posts']==12 and result['interactions']==55
    assert not {'views','reach','impressions'} & result.keys()


def test_pulse_historical_comparison_includes_dates_without_inventing_delta(archive):
    result=dashboard(archive)
    assert result['metrics']['score_delta'] is None
    assert datetime.fromisoformat(result['comparison_window']['end'])==NOW-timedelta(days=1)
    assert datetime.fromisoformat(result['comparison_window']['start'])==NOW-timedelta(days=91)


def test_pulse_rss_fallback_orders_publication_date_not_insertion_id(archive):
    from app.models import NewsArticle
    first=archive[5][0];first.title='Nota reciente';first.published_at=NOW-timedelta(hours=1)
    archive[1].add(NewsArticle(project_id=archive[2].id,title='Nota antigua insertada después',url='https://example.org/older',
        url_hash='older',publisher='Otro medio',origin='rss',published_at=NOW-timedelta(hours=3)))
    archive[1].commit();result=dashboard(archive)
    assert result['headlines'][0]['title']=='Nota reciente'
    assert result['headlines'][0]['source']=='Fixture'
    assert all(row['rank_basis']=='archive_date_only' and row['views'] is None for row in result['headlines'])


def test_import_cannot_assign_another_project_actor_and_is_atomic(archive):
    foreign=add_actor(archive,pid=archive[3].id,actor=3)['id']
    with pytest.raises(HTTPException) as error:ingest(archive,[post(foreign)])
    assert error.value.status_code==422
    assert archive[1].scalar(select(func.count(PulseDocument.id)))==0
    assert archive[1].scalar(select(func.count(PulseBatch.id)))==0


def test_foreign_project_dashboard_is_inaccessible_even_for_its_public_actor_id(archive):
    actor=add_actor(archive,pid=archive[3].id,actor=3)['id']
    with pytest.raises(HTTPException) as error:dashboard(archive,actor_id=actor)
    assert error.value.status_code==404
    with pytest.raises(HTTPException) as error:call(archive,actor=3,start=NOW-timedelta(days=1),end=NOW)
    assert error.value.status_code==404


@pytest.mark.parametrize('path,method,body',[
 ('/actors','POST',ActorInput(name='Nuevo actor')),('/config','PUT',ConfigInput()),
 ('/import','POST',ImportBatch(items=[post(1)])),('/rules','POST',RuleInput(actor_id=1,name='Regla',metric='mentions',threshold=20)),
 ('/apify/sync','POST',None),('/demo','POST',None)])
def test_viewer_cannot_write_or_activate_providers(archive,path,method,body):
    with pytest.raises(HTTPException) as error:call(archive,path,method,actor=2,**({'body':body} if body else {}))
    assert error.value.status_code==403


def test_analyst_can_review_but_cannot_manage_actors(archive):
    actor=add_actor(archive)['id'];ingest(archive,[post(actor)])
    with pytest.raises(HTTPException) as error:add_actor(archive,'Analyst actor',actor=1)
    assert error.value.status_code==403
    row=archive[1].scalar(select(PulseMention))
    call(archive,'/documents/{document_id}/actors/{actor_id}/classification','PUT',actor=1,
        document_id=row.document_id,actor_id=actor,body=Classification(sentiment='neutral',expected_version=0))
    assert archive[1].get(PulseMention,(row.document_id,actor)).method=='human_review:v1'


def test_demo_is_explicit_and_does_not_pollute_real_counts(archive):
    call(archive,'/demo','POST');call(archive,'/demo','POST')
    real=dashboard(archive)
    assert real['metrics']['mentions']==0 and not real['actors']
    demo=call(archive,demo=True,start=datetime.now(timezone.utc)-timedelta(days=1),end=datetime.now(timezone.utc)+timedelta(seconds=1))
    assert demo['is_demo'] and demo['metrics']['mentions']>0 and demo['external_calls']==0
    actor=demo['actors'][0]['id']
    with pytest.raises(HTTPException) as error:ingest(archive,[post(actor)])
    assert error.value.status_code==422


def test_composite_demo_fk_rejects_mix_even_below_the_api(archive):
    real=add_actor(archive)['id'];call(archive,'/demo','POST')
    doc=archive[1].scalar(select(PulseDocument).where(PulseDocument.is_demo.is_(True)))
    archive[1].add(PulseMention(project_id=archive[2].id,document_id=doc.id,actor_id=real,is_demo=True))
    with pytest.raises(IntegrityError):archive[1].commit()
    archive[1].rollback()


def test_apify_is_disabled_even_when_an_environment_key_exists(archive,monkeypatch):
    monkeypatch.setenv('APIFY_TOKEN','SYNTHETIC_NOT_REAL')
    with pytest.raises(ApifyUnavailable):DisabledApifyReader().read('fixture',limit=1)
    with pytest.raises(HTTPException) as error:call(archive,'/apify/sync','POST')
    assert error.value.status_code==409
    with pytest.raises(ValidationError):ConnectorPlan(enabled=True)
    with pytest.raises(ValidationError):ConnectorPlan(monthly_budget_usd=1)


@pytest.mark.parametrize('url',['http://example.org','https://127.0.0.1/a','https://[fd00::1]/a','https://localhost/a','https://user:pass@example.org/a','https://a.internal/a','https://example.org/a?access_token=private'])
def test_import_rejects_private_or_credential_bearing_urls(url):
    with pytest.raises(ValidationError):post(1).model_copy().model_validate({**post(1).model_dump(),'url':url})


def test_apify_mapping_is_explicit_and_drops_author_identity():
    rows=normalize_export([dict(postId='a',link='https://example.org/a',headline='A title',date=NOW.isoformat(),authorId='NOT_STORED')],
        {'external_id':'postId','url':'link','title':'headline','published_at':'date'},network='facebook',actor_ids=[1],collected_at=NOW)
    assert rows[0].external_id=='a' and 'author' not in rows[0].model_dump_json()
    with pytest.raises(ValueError):normalize_export([],{},network='facebook',actor_ids=[1],collected_at=NOW)


def test_project_admin_does_not_implicitly_become_platform_admin(archive):
    assert not platform(archive,'session')['is_superadmin']
    with pytest.raises(HTTPException) as error:platform(archive,'projects')
    assert error.value.status_code==403


def test_platform_creates_generic_project_and_owner_can_access_all_modules(archive):
    s=archive[1];s.add(PlatformGrant(user_id=archive[4][0].id));s.commit()
    made=platform(archive,'projects','POST',body=ProjectInput(name='Cliente en otro territorio',slug='cliente-otro',territory='Territorio distinto',owner_user_id=archive[4][1].id))
    assert made['slug']!='d14'
    assert call(archive,pid=made['id'],start=NOW-timedelta(days=1),end=NOW)['metrics']['mentions']==0
    assert call(archive,'/config',pid=made['id'])['territory']=='Territorio distinto'
    with pytest.raises(HTTPException) as error:call(archive,pid=made['id'],actor=2,start=NOW-timedelta(days=1),end=NOW)
    assert error.value.status_code==404
    with pytest.raises(HTTPException) as error:platform(archive,'projects/{pid}/members','PUT',pid=made['id'],body=MemberInput(user_id=archive[4][0].id,role='viewer'))
    assert error.value.status_code==409
    assert s.scalar(select(Membership).where(Membership.project_id==made['id'],Membership.user_id==archive[4][0].id)).role=='admin'


def test_platform_user_creation_hashes_password_and_does_not_grant_superadmin(archive):
    archive[1].add(PlatformGrant(user_id=archive[4][0].id));archive[1].commit()
    result=platform(archive,'users','POST',body=UserInput(email='new@test.invalid',password='synthetic-password-123'))
    user=archive[1].get(User,result['id'])
    assert user.password_hash!='synthetic-password-123' and archive[1].get(PlatformGrant,user.id) is None
    assert all('password' not in str(row) for row in platform(archive,'users'))


@pytest.mark.parametrize('fields',[dict(network='unknown'),dict(views=-1),dict(views=True),dict(collected_at=NOW.replace(tzinfo=None))])
def test_import_contract_rejects_invalid_values(fields):
    raw=post(1).model_dump();raw.update(fields)
    with pytest.raises(ValidationError):PublicPost.model_validate(raw)


def test_account_metrics_period_requires_complete_valid_window():
    fields=dict(actor_id=1,network='facebook',url='https://example.org/a',captured_at=NOW)
    with pytest.raises(ValidationError):AccountInput(**fields,metrics_from=NOW)
    with pytest.raises(ValidationError):AccountInput(**fields,metrics_from=NOW,metrics_to=NOW-timedelta(days=1))


def test_brand_is_editable_only_by_explicit_platform_owner(archive):
    read=endpoint(archive[0],'/api/branding')
    assert read(session=archive[1])['name']=='NEXO'
    with pytest.raises(HTTPException) as error:platform(archive,'branding','PUT',body=BrandInput(name='Marca propia'))
    assert error.value.status_code==403
    archive[1].add(PlatformGrant(user_id=archive[4][0].id));archive[1].commit()
    platform(archive,'branding','PUT',body=BrandInput(name='Marca propia',tagline='Contexto claro'))
    assert read(session=archive[1])==dict(name='Marca propia',tagline='Contexto claro')
    assert archive[2].name=='Own' and archive[2].slug=='own'


def test_platform_provision_binds_every_project_and_revoke_restores_roles(archive):
    from app.platform_access import bind_projects,unbind_projects
    s=archive[1];user=archive[4][1]
    grant=PlatformGrant(user_id=user.id);s.add(grant);s.flush();bind_projects(s,grant);s.commit()
    members=s.scalars(select(Membership).where(Membership.user_id==user.id)).all()
    assert len(members)==2 and all(x.role=='admin' for x in members)
    assert call(archive,pid=archive[3].id,actor=1,start=NOW-timedelta(days=1),end=NOW)['metrics']['mentions']==0
    bind_projects(s,grant);s.commit();unbind_projects(s,grant);grant.active=False;s.commit()
    members=s.scalars(select(Membership).where(Membership.user_id==user.id)).all()
    assert len(members)==1 and members[0].role=='analyst'
    with pytest.raises(HTTPException) as error:call(archive,pid=archive[3].id,actor=1,start=NOW-timedelta(days=1),end=NOW)
    assert error.value.status_code==404


def test_platform_owner_existing_admin_survives_revoke(archive):
    from app.platform_access import bind_projects,unbind_projects
    s=archive[1];grant=PlatformGrant(user_id=archive[4][0].id);s.add(grant);s.flush()
    bind_projects(s,grant);s.commit();unbind_projects(s,grant);s.commit()
    rows=s.scalars(select(Membership).where(Membership.user_id==grant.user_id)).all()
    assert len(rows)==1 and rows[0].project_id==archive[2].id and rows[0].role=='admin'


def test_stale_account_snapshot_does_not_claim_growth_in_current_window(archive):
    actor=add_actor(archive)['id']
    call(archive,'/accounts','POST',body=AccountInput(actor_id=actor,network='facebook',url='https://example.org/account',captured_at=NOW-timedelta(days=5),followers=100))
    result=dashboard(archive)['accounts'][0]
    assert result['stale'] and result['followers_delta'] is None


def test_archived_actor_does_not_leave_headlines_in_active_universe(archive):
    actor=add_actor(archive);ingest(archive,[post(actor['id'])])
    call(archive,'/actors/{actor_id}','PUT',actor_id=actor['id'],body=ActorUpdate(name=actor['name'],kind='primary',active=False,expected_version=1))
    packet=dashboard(archive)
    assert not packet['actors'] and packet['metrics']['mentions']==0
    assert not any(x['rank_basis']=='observed_views' for x in packet['headlines'])


def test_pulse_backup_and_restore_keep_scope_labels_and_brand(archive,monkeypatch):
    from pathlib import Path
    import sqlite3
    from scripts import backup_local as backup
    actor=add_actor(archive)['id'];ingest(archive,[post(actor)]);classify_all(archive)
    call(archive,'/demo','POST')
    archive[1].add(PlatformGrant(user_id=archive[4][0].id));archive[1].commit()
    platform(archive,'branding','PUT',body=BrandInput(name='Marca ficticia'))
    private=Path(archive[0].state.engine.url.database).parent
    uploads=private/'uploads';uploads.mkdir(exist_ok=True);secret=private/'fixture-session.key';secret.write_text('test-only')
    raw,manifest=backup.make_archive(private,db_file=Path(archive[0].state.engine.url.database),uploads_directory=uploads,secret_file=secret)
    monkeypatch.setattr(backup,'dpapi',lambda value,decrypt=False:value)
    file=private/'synthetic-pulse.nexobak';file.write_bytes(backup.MAGIC+raw)
    recovered=backup.restore_backup(file,private/'isolated-pulse-restore');assert recovered['counts']==manifest['counts']
    with sqlite3.connect(private/'isolated-pulse-restore/storage/nexo.db') as db:
        assert db.execute('select name from platform_brand').fetchone()[0]=='Marca ficticia'
        assert db.execute('select sentiment,method from pulse_mentions where is_demo=0').fetchone()==('positive','human_review:v1')
        assert db.execute('select count(*) from pulse_mentions where is_demo=1').fetchone()[0]>0
