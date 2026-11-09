import os, json, base64, hashlib, re, time
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import cloud_auth, listening
from app.config import validate_config
from app.controls import WindowLimiter, take_quota
from app.main import create_app
from app.models import DatasetBlob, AuditEvent, User, Project, Membership
from app.security import make_hash


@pytest.fixture
def client(monkeypatch,tmp_path):
    monkeypatch.setenv('NEXO_SECRET_KEY','test-only-'+('A'*48))
    app=create_app('sqlite:///'+str(tmp_path/'v05.sqlite'),storage_dir=str(tmp_path/'files'))
    with app.state.SessionLocal() as s:
        u=User(email='test@example.invalid',password_hash=make_hash('test-password-only'))
        p=Project(slug='d14',name='D14');s.add_all([u,p]);s.flush()
        s.add(Membership(user_id=u.id,project_id=p.id,role='admin'));s.commit();pid=p.id
    with TestClient(app) as c:
        token=c.post('/api/auth/login',json={'email':'test@example.invalid','password':'test-password-only'}).json()['token']
        yield c,app,pid,{'Authorization':'Bearer '+token}


def test_durable_upload_and_no_path_leak(client,monkeypatch):
    c,app,pid,h=client
    monkeypatch.setenv('NEXO_STORAGE_MODE','database')
    r=c.post(f'/api/projects/{pid}/datasets',headers=h,files={'file':('x.csv',b'a,b\n1,2')})
    assert r.status_code==200,r.text
    with app.state.SessionLocal() as s:
        assert s.scalar(select(DatasetBlob.content))==b'a,b\n1,2'
    assert 'path' not in c.get(f'/api/projects/{pid}/datasets',headers=h).text


def test_export_audited_and_scoped(client):
    c,app,pid,h=client
    assert c.get(f'/api/projects/{pid+99}/sections/export',headers=h).status_code==404
    r=c.get(f'/api/projects/{pid}/sections/export',headers=h)
    assert r.status_code==200 and 'attachment' in r.headers['content-disposition']
    with app.state.SessionLocal() as s:
        assert s.scalar(select(AuditEvent).where(AuditEvent.action=='sections.export'))


def test_oversized_chunked_body_before_parser(client):
    c,app,pid,h=client
    r=c.post('/api/auth/login',content=iter([b'x'*20000,b'x'*20000]))
    assert r.status_code==413


def test_security_headers_and_script_hash(client):
    c,*_=client
    r=c.get('/')
    content=re.search(r'<script>([\s\S]*?)</script>',r.text).group(1)
    digest=base64.b64encode(hashlib.sha256(content.encode()).digest()).decode()
    assert 'sha256-'+digest in r.headers['content-security-policy']
    assert "script-src 'self' 'sha256-" in r.headers['content-security-policy']
    assert r.headers['cache-control']=='no-store'
    assert c.get('/openapi.json').status_code==404
    assert 'id="logoutNexo"' in r.text


def test_cloud_origin_and_host_rejected(client,monkeypatch):
    c,*_=client
    monkeypatch.setenv('NEXO_PUBLIC_ORIGIN','https://nexo.test')
    monkeypatch.setattr('app.controls.cloud',lambda:True)
    assert c.post('/api/auth/login',headers={'Host':'nexo.test','Origin':'https://evil.test'},json={}).status_code==403
    assert c.get('/api/health',headers={'Host':'evil.test'}).status_code==400
    assert 'max-age' in c.get('/api/health',headers={'Host':'nexo.test'}).headers['strict-transport-security']


def test_project_quota_commits_attempt(client):
    c,app,pid,h=client
    with app.state.SessionLocal() as s:
        take_quota(s,pid,'test.attempt',1)
        with pytest.raises(HTTPException) as error:take_quota(s,pid,'test.attempt',1)
        assert error.value.status_code==429


def test_bounded_memory_limiter():
    limiter=WindowLimiter()
    assert limiter.accept('a',1)
    assert not limiter.accept('a',1)
    for i in range(5000):limiter.accept(str(i),1)
    assert len(limiter.buckets)==4096


def test_cloud_fails_closed(monkeypatch):
    monkeypatch.setenv('NEXO_ENV','staging')
    with pytest.raises(RuntimeError):validate_config('sqlite:///local.db')
    monkeypatch.setenv('NEXO_PUBLIC_ORIGIN','https://nexo.test')
    monkeypatch.setenv('NEXO_SUPABASE_URL','https://project.supabase.co')
    monkeypatch.setenv('NEXO_SUPABASE_PUBLISHABLE_KEY','sb_publishable_placeholder')
    monkeypatch.setenv('NEXO_STORAGE_MODE','database')
    with pytest.raises(RuntimeError):validate_config('postgresql+psycopg://user:pass@host/db?sslmode=require')
    monkeypatch.setenv('NEXO_ENV','production')
    with pytest.raises(RuntimeError):validate_config('postgresql+psycopg://user:pass@host/db?sslmode=verify-full')


@pytest.fixture
def signed(monkeypatch):
    monkeypatch.setenv('NEXO_SUPABASE_URL','https://project.supabase.co')
    key=ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(cloud_auth,'key_client',lambda issuer:SimpleNamespace(get_signing_key_from_jwt=lambda t:SimpleNamespace(key=key.public_key())))
    claims={'sub':'11111111-1111-4111-8111-111111111111','iss':cloud_auth.base(),'aud':'authenticated',
            'role':'authenticated','aal':'aal2','iat':int(time.time()),'exp':int(time.time())+300}
    def sign(**changes):return jwt.encode({**claims,**changes},key,algorithm='ES256',headers={'kid':'local-test'})
    return sign


def test_jwt_valid(signed):
    assert cloud_auth.decode_token(signed())['aal']=='aal2'


@pytest.mark.parametrize('change',[{'aud':'other'},{'iss':'https://evil.test'},{'role':'service_role'},
    {'aal':'aal1'},{'exp':1},{'sub':'not-a-uuid'}])
def test_jwt_wrong_claims(signed,change):
    with pytest.raises(HTTPException):cloud_auth.decode_token(signed(**change))


def test_jwt_signature_and_alg_rejected(signed):
    token=signed();bits=token.split('.')
    bits[2]=base64.urlsafe_b64encode(b'\0'*64).decode().rstrip('=')
    with pytest.raises(HTTPException):cloud_auth.decode_token('.'.join(bits))
    with pytest.raises(HTTPException):cloud_auth.decode_token(jwt.encode({'sub':'x'},'x'*48,algorithm='HS256',headers={'kid':'x'}))


@pytest.mark.parametrize('bad',['https://127.0.0.1/feed','https://[::1]/rss','https://169.254.169.254/latest',
    'file:///etc/passwd','http://feed.example/rss','https://feed.example:22/rss','https://x:y@feed.example/rss',
    'https://feed.example/rss\r\nX:evil','https://feed.example\\@evil.test/rss','https://feed.example./rss'])
def test_ssrf_urls_blocked(bad):
    with pytest.raises(ValueError):listening.normalize_url(bad)


def test_dns_mixed_private_addresses_rejected(monkeypatch):
    fake=SimpleNamespace(timeout=1,lifetime=2,resolve=lambda host,kind,lifetime:['8.8.8.8'] if kind=='A' else ['::1'])
    monkeypatch.setattr(listening.dns.resolver,'Resolver',lambda:fake)
    with pytest.raises(ValueError):listening.resolve_public('feed.example')


def test_fetch_connects_to_pinned_address_and_no_redirects(monkeypatch):
    # The connection and DNS are fully replaced below; no live request is made.
    monkeypatch.setenv('NEXO_OFFLINE','false')
    monkeypatch.setenv('NEXO_RSS_ALLOWED_HOSTS','feed.example')
    looked=[];connected=[]
    monkeypatch.setattr(listening,'resolve_public',lambda host:looked.append(host) or ['8.8.8.8'])
    class Conn:
        status=200
        def __init__(self,host,address):connected.append((host,address));self.parts=[b'<rss/>',b'']
        def request(self,*a,**k):pass
        def getresponse(self):return self
        def getheader(self,key,default=''):return {'Content-Type':'application/rss+xml'}.get(key,default)
        def read1(self,n):return self.parts.pop(0)
        def close(self):pass
    monkeypatch.setattr(listening,'PinnedHTTPS',Conn)
    assert listening.fetch_rss('https://feed.example/rss')==b'<rss/>'
    assert looked==['feed.example'] and connected==[('feed.example','8.8.8.8')]
    Conn.status=302
    with pytest.raises(ValueError):listening.fetch_rss('https://feed.example/rss')


def test_xml_entities_and_bombs_rejected():
    with pytest.raises(ValueError):listening.parse_feed(b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss>&x;</rss>')
    with pytest.raises(ValueError):listening.parse_feed(b'x'*(listening.MAX_FEED_BYTES+1))


def test_historical_totals_preserved():
    data=json.loads((Path(__file__).resolve().parents[1]/'data/secciones_2024.json').read_text(encoding='utf-8'))
    assert len(data)==45
    assert sum(v['ln'] for v in data.values())==65378
    assert sum(v['votes'] for v in data.values())==41984


def test_cloud_login_mfa_flow_and_cookie(client,signed,monkeypatch):
    c,app,pid,h=client
    with app.state.SessionLocal() as s:
        s.scalar(select(User)).auth_subject='11111111-1111-4111-8111-111111111111';s.commit()
    monkeypatch.setenv('NEXO_ENV','staging')
    monkeypatch.setenv('NEXO_PUBLIC_ORIGIN','https://testserver')
    c.base_url='https://testserver'
    origin={'Origin':'https://testserver'}
    factor='44444444-4444-4444-8444-444444444444'
    def provider(method,path,token=None,body=None):
        if path.startswith('/token'):return {'access_token':signed(aal='aal1')}
        if path=='/user':return {'factors':[]}
        if path=='/factors':return {'id':factor,'totp':{'secret':'TEST-ENROLLMENT-ONLY'}}
        if path.endswith('/challenge'):return {'id':'challenge'}
        if path.endswith('/verify'):return {'access_token':signed()}
        return {}
    monkeypatch.setattr(cloud_auth,'provider',provider)
    r=c.post('/api/auth/login',json={'email':'test@example.invalid','password':'test-password-only'},headers=origin)
    assert r.json()=={'mfa_required':True}
    assert 'HttpOnly' in r.headers['set-cookie'] and 'Secure' in r.headers['set-cookie']
    assert c.get('/api/projects').status_code==401
    r=c.post('/api/auth/mfa/start',headers=origin)
    assert r.json()['setup_secret']=='TEST-ENROLLMENT-ONLY'
    r=c.post('/api/auth/mfa/verify',json={'factor_id':factor,'code':'123456'},headers=origin)
    assert r.status_code==200 and 'access_token' not in r.text
    assert c.get('/api/projects').status_code==200
    assert c.post('/api/auth/logout',headers=origin).status_code==200
    assert c.get('/api/projects').status_code==401


def test_pinned_socket_uses_numeric_ip_and_original_tls_host(monkeypatch):
    import ssl
    conn=listening.PinnedHTTPS('feed.example','8.8.8.8')
    assert conn._context.check_hostname and conn._context.verify_mode==ssl.CERT_REQUIRED
    calls=[]
    sock=SimpleNamespace(close=lambda:None)
    monkeypatch.setattr(listening.socket,'create_connection',lambda address,timeout:calls.append(address) or sock)
    conn._context=SimpleNamespace(wrap_socket=lambda socket,server_hostname:calls.append(server_hostname) or sock)
    conn.connect()
    assert calls==[('8.8.8.8',443),'feed.example']
