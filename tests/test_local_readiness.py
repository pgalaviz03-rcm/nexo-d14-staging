from pathlib import Path
import json,sqlite3,sys
import pytest
from sqlalchemy import text
from test_manual_reviews import archive
from test_retrieval_evaluation import add_text
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_local_readiness import check
import evaluate_retrieval

def paths(a):
    root=Path(a[0].state.engine.url.database).parent
    source=add_text(a,'Inventario de muestra: 100.','Fuente.txt')
    cases=[dict(id='actual',project_id=a[2].id,question='inventario',document_id=source.id,
                evidence=[dict(source_id=source.id,text=['100'])])]
    path=root/'cases.json';path.write_text(json.dumps(cases),encoding='utf-8')
    return root/'reviews.sqlite',root/'uploads',path,cases

def test_health_and_evaluation_are_read_only(archive):
    database,uploads,cases,_=paths(archive)
    before=database.read_bytes();r=check(database,uploads,cases)
    assert r['ready_for_human_local_test'] and r['retrieval']['cases_passed']==1
    assert database.read_bytes()==before and not r['production_ready'] and r['external_calls']==0
    assert not r['running_server_verified'] and not r['provider_connections_verified']

def test_evaluation_database_connection_rejects_writes(archive,monkeypatch):
    database,uploads,_,cases=paths(archive)
    def write(session,*args,**kw):session.execute(text("UPDATE projects SET name='changed'"))
    monkeypatch.setattr(evaluate_retrieval,'retrieve_context',write)
    r=evaluate_retrieval.run(database,uploads,cases)
    assert not r['passed'] and r['results'][0]['checks_failed']==['retrieval_error']
    with sqlite3.connect(database) as conn:assert conn.execute('select name from projects where id=?',(archive[2].id,)).fetchone()[0]=='Own'

def test_failed_retrieval_blocks_general_test_readiness(archive):
    database,uploads,path,cases=paths(archive);cases[0]['evidence'][0]['text']=['missing expected fact']
    path.write_text(json.dumps(cases),encoding='utf-8');r=check(database,uploads,path)
    assert not r['ready_for_human_local_test']

def test_missing_dependency_blocks_readiness(archive,monkeypatch):
    import check_local_readiness
    database,uploads,cases,_=paths(archive);original=check_local_readiness.importlib.util.find_spec
    monkeypatch.setattr(check_local_readiness.importlib.util,'find_spec',lambda name:None if name=='pypdf' else original(name))
    assert not check(database,uploads,cases)['ready_for_human_local_test']

def test_offline_mode_blocks_rss_before_dns_or_connection(monkeypatch):
    from app import listening
    monkeypatch.setenv('NEXO_OFFLINE','true')
    def blocked(*args,**kwargs):raise AssertionError('DNS or network attempted')
    monkeypatch.setattr(listening,'resolve_public',blocked)
    with pytest.raises(ValueError,match='desactivadas'):listening.fetch_rss('https://example.invalid/feed')
