from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import select
import pytest
from app.main import create_app
from app.models import User, Project, Membership,NewsArticle,FeedSource
from app.security import make_hash
from app.listening import parse_feed,normalize_url,validate_feed_url

RSS=b'''<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0"><channel><title>Noticias ficticias para prueba</title>
<item><title>Reporte sobre abastecimiento de agua</title><link>https://ejemplo.org/noticia/uno</link><description>Nota <b>de prueba</b></description><pubDate>Wed, 14 Oct 2026 15:00:00 GMT</pubDate></item>
<item><title>Actualizan las rutas urbanas</title><link>https://ejemplo.org/noticia/dos</link><description>Movilidad</description></item>
</channel></rss>'''

@pytest.fixture
def setup(monkeypatch,tmp_path):
    monkeypatch.setenv('NEXO_SECRET_KEY','unique-test-secret-'+ 'A'*48)
    monkeypatch.setenv('NEXO_RSS_ALLOWED_HOSTS','fuente.gob.mx')
    app=create_app('sqlite:///'+str(tmp_path/'rss.sqlite'),storage_dir=str(tmp_path/'files'))
    with app.state.SessionLocal() as s:
        alice=User(email='rss@test.local',password_hash=make_hash('safe12345678901234'))
        bob=User(email='other@test.local',password_hash=make_hash('safe12345678901234'))
        s.add_all([alice,bob]);s.flush()
        a=Project(slug='d14',name='Distrito 14');b=Project(slug='other',name='Otro')
        s.add_all([a,b]);s.flush()
        s.add_all([Membership(user_id=alice.id,project_id=a.id,role='admin'),Membership(user_id=bob.id,project_id=b.id,role='viewer')]);s.commit()
        aid=a.id;bid=b.id
    with TestClient(app) as c:
        def auth(email):
            r=c.post('/api/auth/login',json={'email':email,'password':'safe12345678901234'})
            assert r.status_code==200
            return {'Authorization':'Bearer '+r.json()['token']}
        yield c,aid,bid,auth,app


def test_parse_and_url_rules(monkeypatch):
    rows=parse_feed(RSS)
    assert len(rows)==2
    assert rows[0]['published_at'].year==2026
    assert rows[0]['abstract']=='Nota de prueba'
    assert normalize_url('https://ejemplo.org/?utm_source=test&a=1')=='https://ejemplo.org/?a=1'
    for bad in ['http://fuente.gob.mx/feed','https://127.0.0.1/rss','https://localhost/rss','https://foo:444/feed','https://x:y@fuente.gob.mx/rss']:
        with pytest.raises(ValueError):normalize_url(bad)
    monkeypatch.setenv('NEXO_RSS_ALLOWED_HOSTS','fuente.gob.mx')
    assert validate_feed_url('https://fuente.gob.mx/feed')=='https://fuente.gob.mx/feed'
    with pytest.raises(ValueError):validate_feed_url('https://example.com/feed')


def test_feed_register_sync_and_boundaries(setup,monkeypatch):
    c,a,b,auth,app=setup
    alice=auth('rss@test.local');bob=auth('other@test.local')
    monkeypatch.setattr('app.rss_api.fetch_rss',lambda url:RSS)
    assert c.post(f'/api/projects/{a}/feeds',headers=alice,json={'title':'Fuente no autorizada','url':'https://example.com/rss'}).status_code==422
    assert c.post(f'/api/projects/{b}/feeds',headers=alice,json={'title':'Fuente','url':'https://fuente.gob.mx/rss'}).status_code==404
    r=c.post(f'/api/projects/{a}/feeds',headers=alice,json={'title':'Prueba RSS','url':'https://fuente.gob.mx/rss'})
    assert r.status_code==200,r.text
    fid=r.json()['id']
    assert c.post(f'/api/projects/{a}/feeds/{fid}/sync',headers=bob).status_code==404
    result=c.post(f'/api/projects/{a}/feeds/{fid}/sync',headers=alice)
    assert result.status_code==200,result.text
    assert result.json()['inserted']==2
    assert c.post(f'/api/projects/{a}/feeds/{fid}/sync',headers=alice).status_code==429
    rows=c.get(f'/api/projects/{a}/articles?q=agua',headers=alice).json()
    assert len(rows)==1
    assert rows[0]['origin']=='rss'
    assert c.get(f'/api/projects/{a}/articles',headers=bob).status_code==404
    assert c.get(f'/api/projects/{b}/articles',headers=bob).json()==[]


def test_csv_import_dedup_and_error(setup):
    c,a,b,auth,app=setup
    ah=auth('rss@test.local');bh=auth('other@test.local')
    csv=b'title,url,source,description\nNoticia uno,https://ejemplo.org/a,Medio publico,Nota de archivo\nNoticia dos,https://ejemplo.org/b,Medio publico,Otra nota\n'
    res=c.post(f'/api/projects/{a}/articles/import',headers=ah,files={'file':('notas.csv',csv,'text/csv')})
    assert res.status_code==200,res.text
    assert res.json()['inserted']==2
    assert c.post(f'/api/projects/{a}/articles/import',headers=ah,files={'file':('notas.csv',csv,'text/csv')}).json()['inserted']==0
    assert len(c.get(f'/api/projects/{a}/articles',headers=ah).json())==2
    assert c.get(f'/api/projects/{b}/articles',headers=ah).status_code==404
    assert c.post(f'/api/projects/{b}/articles/import',headers=bh,files={'file':('notas.csv',csv,'text/csv')}).status_code==403
    invalid=b'title,url,source\nA,http://localhost/internal,Medio\n'
    assert c.post(f'/api/projects/{a}/articles/import',headers=ah,files={'file':('bad.csv',invalid,'text/csv')}).status_code==422


def test_failed_feed_keeps_existing_articles(setup,monkeypatch):
    c,a,b,auth,app=setup;h=auth('rss@test.local')
    r=c.post(f'/api/projects/{a}/articles/import',headers=h,files={'file':('news.csv',b'title,url,source\nEjemplo,https://ejemplo.org/uno,Archivo\n','text/csv')})
    assert r.status_code==200
    monkeypatch.setattr('app.rss_api.fetch_rss',lambda u: (_ for _ in ()).throw(ValueError('Proveedor no disponible')))
    f=c.post(f'/api/projects/{a}/feeds',headers=h,json={'title':'Fuente','url':'https://fuente.gob.mx/feed'}).json()
    assert c.post(f'/api/projects/{a}/feeds/{f["id"]}/sync',headers=h).status_code==502
    assert len(c.get(f'/api/projects/{a}/articles',headers=h).json())==1
    assert c.get(f'/api/projects/{a}/feeds',headers=h).json()[0]['status']=='error'
