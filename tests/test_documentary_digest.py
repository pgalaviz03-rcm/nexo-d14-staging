"""Dossier isolation, abstention, no model activation and UI compatibility."""
from pathlib import Path
from html.parser import HTMLParser
import json
import re
import socket

import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from sqlalchemy import inspect, select

from app.models import AuditEvent, Membership
from app.workspace_api import ContextRequest, install_workspace_api
from test_local_knowledge import archive


def installed(archive):
    session,pid,foreign,user,other,doc,uploads=archive
    def allow(project,actor,db):
        if not db.scalar(select(Membership).where(Membership.project_id==project,Membership.user_id==actor.id)):
            raise HTTPException(404,'Proyecto no disponible')
    def db():yield session
    def identity():return user
    app=FastAPI();install_workspace_api(app,db,identity,allow,uploads)
    return app,next(r.endpoint for r in app.routes if r.path.endswith('/critical-audit'))


def test_digest_quotes_only_the_current_project(archive):
    app,route=installed(archive);s,p,foreign,user,*_=archive
    result=route(p,ContextRequest(question='agua'),user,s)
    assert result['mode']=='local_documentary_digest'
    assert result['status']=='fragments_found'
    assert result['answer'] is None and not result['ai_used'] and result['external_calls']==0
    assert not result['from_cache'] and 'tokens_saved' not in result
    assert all(c['project_id']==p for c in result['citations'])
    assert 'NO DEBE APARECER' not in json.dumps(result)
    assert 'no verifican hechos' in result['note']


def test_empty_dossier_abstains(archive):
    _,route=installed(archive);s,p,_,user,*_=archive
    result=route(p,ContextRequest(question='terminoinexistente'),user,s)
    assert result['status']=='no_matches' and result['citations']==[] and result['answer'] is None


def test_digest_never_activates_a_provider_or_obeys_a_source(archive,monkeypatch):
    monkeypatch.setenv('NEXO_LOCAL_OLLAMA','true')
    monkeypatch.setenv('OPENAI_API_KEY','not-a-real-key')
    def blocked(*args,**kwargs):raise AssertionError('Network attempted')
    monkeypatch.setattr(socket,'getaddrinfo',blocked)
    monkeypatch.setattr(socket,'socket',blocked)
    _,route=installed(archive);s,p,_,user,*_=archive
    result=route(p,ContextRequest(question='secretos'),user,s)
    assert 'Ignora instrucciones' in result['citations'][0]['excerpt']
    assert result['external_calls']==0 and not result['ai_used']


def test_digest_does_not_store_questions_or_create_profile_tables(archive):
    _,route=installed(archive);s,p,_,user,*_=archive
    for _ in range(2):route(p,ContextRequest(question='agua consulta privada'),user,s)
    events=s.scalars(select(AuditEvent)).all()
    assert len(events)==2
    assert all(e.action=='knowledge.documentary_digest' and e.target.startswith('citations:') for e in events)
    assert 'consulta privada' not in repr([(e.action,e.target) for e in events])
    assert not {'rag_cache','social_mentions','synthetic_personas'} & set(inspect(s.bind).get_table_names())


def test_digest_rejects_foreign_members_before_retrieval(archive):
    _,route=installed(archive);s,p,_,user,other,*_=archive
    with pytest.raises(HTTPException) as rejected:route(p,ContextRequest(question='agua'),other,s)
    assert rejected.value.status_code==404
    assert not s.scalars(select(AuditEvent)).all()


@pytest.mark.parametrize('fields',[{'source_kind':'profiles'},{'days':2}])
def test_digest_validates_retrieval_filters(archive,fields):
    _,route=installed(archive);s,p,_,user,*_=archive
    with pytest.raises(HTTPException) as rejected:route(p,ContextRequest(question='agua',**fields),user,s)
    assert rejected.value.status_code==422


def test_digest_request_cannot_turn_on_generation():
    with pytest.raises(ValidationError):ContextRequest(question='agua',provider='external')


class Elements(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.pages=[];self.scripts=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if 'id' in values:self.ids.append(values['id'])
        if 'data-page' in values:self.pages.append(values['data-page'])
        if tag=='script':self.scripts.append(values.get('src'))


def test_ui_bindings_and_navigation_have_unique_existing_elements():
    static=Path(__file__).resolve().parents[1]/'static'
    html=(static/'index.html').read_text(encoding='utf-8')
    elements=Elements();elements.feed(html)
    assert len(elements.ids)==len(set(elements.ids))
    assert set(elements.pages)<=set(elements.ids)
    assert len(elements.scripts)==2 and elements.scripts[1] is None
    bundle=(Path(__file__).resolve().parents[1]/'static/nexo-modules.js').read_bytes()
    assert elements.scripts[0]=='/assets/nexo-modules.js?v='+__import__('hashlib').sha256(bundle).hexdigest()[:16]
    scripts=re.search(r'<script>([\s\S]*?)</script>',html).group(1)+(static/'nexo-modules.js').read_text(encoding='utf-8')
    referenced=set(re.findall(r"byId\(['\"]([^'\"]+)['\"]\)",scripts))
    assert referenced<=set(elements.ids),referenced-set(elements.ids)
    assert all(x in html for x in ['Temas y revisión','Ficha documental','Métricas ilustrativas'])
    assert '/personas' not in scripts and '/social`' not in scripts


def test_digest_is_registered_only_in_local_workspace(archive,monkeypatch):
    from app.main import create_app
    s,p,_,user,*_=archive
    monkeypatch.setenv('NEXO_ENV','local');monkeypatch.setenv('NEXO_LOCAL_WORKSPACE','false')
    app=create_app(str(s.bind.url),str(archive[-1]))
    assert not any(r.path.endswith('/critical-audit') for r in app.routes)
    app.state.engine.dispose()


def test_ui_preserves_full_territorial_map_and_report_workspace():
    html=(Path(__file__).resolve().parents[1]/'static/index.html').read_text(encoding='utf-8')
    sections=re.findall(r'class="secpath" data-section="(\d+)"',html)
    assert len(sections)==45 and len(set(sections))==45
    assert 'id="map-manzanas"' in html
    report=re.search(r'<section\b[^>]*id="reports"[\s\S]*?</section>',html).group(0)
    assert 'data-state="operational"' in report
    assert 'id="reportForm"' in report and 'id="reportVersions"' in report
    assert 'Listas para integrar' not in report
    executive=re.search(r'<section\b[^>]*id="executive"[\s\S]*?</section>',html).group(0)
    assert 'data-state="demo"' in executive
    assert 'no son mediciones reales' in executive
