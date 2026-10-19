"""Supabase Auth gateway. Provider access tokens stay in HttpOnly cookies.

No refresh tokens are persisted. Sessions expire at the IdP JWT expiration.
Memberships and active flags remain local, checked on every API request.
"""
import os
from uuid import UUID
import httpx
import jwt
from functools import lru_cache
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field
from .config import cloud

COOKIE = '__Host-nexo'  # Secure, no Domain, Path=/
PENDING = '__Host-nexo-mfa'


def base():
    return os.environ['NEXO_SUPABASE_URL'].rstrip('/') + '/auth/v1'


@lru_cache(maxsize=4)
def key_client(issuer):
    return jwt.PyJWKClient(issuer + '/.well-known/jwks.json', cache_jwk_set=True,
                          lifespan=300, timeout=5)


def decode_token(token, require_mfa=True):
    try:
        if len(token) > 8192:
            raise ValueError('Token demasiado largo')
        header = jwt.get_unverified_header(token)
        if header.get('alg') not in {'ES256', 'RS256'} or not header.get('kid'):
            raise ValueError('Algoritmo no permitido')
        key = key_client(base()).get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=['ES256', 'RS256'], audience='authenticated',
            issuer=base(), options={'require': ['exp', 'iat', 'sub', 'aud', 'iss']}, leeway=5)
        UUID(claims['sub'])
        if claims.get('role') != 'authenticated':
            raise ValueError('Rol inválido')
        if require_mfa and claims.get('aal') != 'aal2':
            raise ValueError('Se requiere segundo factor')
        return claims
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(401, 'Sesión inválida o expirada') from exc


def provider(method, path, token=None, body=None):
    headers = {'apikey': os.environ['NEXO_SUPABASE_PUBLISHABLE_KEY']}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
            result = client.request(method, base()+path, headers=headers, json=body)
        if result.status_code >= 400:
            raise HTTPException(401, 'No fue posible validar el acceso')
        return result.json() if result.content else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, 'Servicio de identidad temporalmente no disponible') from exc


def cookie(response, token):
    claims = decode_token(token)
    import time
    response.set_cookie(COOKIE, token, max_age=max(1, int(claims['exp']-time.time())),
                        secure=True, httponly=True, samesite='strict', path='/')
    response.delete_cookie(PENDING, secure=True, httponly=True, samesite='strict', path='/')


def login(email, password, response):
    data = provider('POST', '/token?grant_type=password', body={'email': email, 'password': password})
    token = data['access_token']
    decode_token(token, require_mfa=False)
    response.set_cookie(PENDING, token, max_age=300, secure=True, httponly=True, samesite='strict', path='/')
    return {'mfa_required': True}


class MfaCode(BaseModel):
    code: str = Field(pattern=r'^\d{6}$')
    factor_id: str


def install_auth(app):
    def pending(request):
        token = request.cookies.get(PENDING)
        if not token:
            raise HTTPException(401, 'Inicia sesión de nuevo')
        claims=decode_token(token, require_mfa=False)
        import time
        if time.time()-claims['iat']>300:raise HTTPException(401,'Inicia sesión de nuevo')
        return token

    @app.post('/api/auth/mfa/start')
    def start(request: Request):
        if not cloud():
            raise HTTPException(404)
        token = pending(request)
        user = provider('GET', '/user', token)
        factors = [f for f in user.get('factors', []) if f.get('factor_type') == 'totp' and f.get('status') == 'verified']
        if factors:
            return {'factor_id': factors[0]['id']}
        data = provider('POST', '/factors', token, {'factor_type': 'totp', 'friendly_name': 'NEXO'})
        return {'factor_id': data['id'], 'setup_secret': data['totp']['secret']}

    @app.post('/api/auth/mfa/verify')
    def verify_mfa(body: MfaCode, request: Request, response: Response):
        if not cloud():
            raise HTTPException(404)
        token = pending(request)
        try:factor = str(UUID(body.factor_id))
        except ValueError:raise HTTPException(422,'Identificador de factor inválido')
        challenge = provider('POST', f'/factors/{factor}/challenge', token, {})
        data = provider('POST', f'/factors/{factor}/verify', token,
                        {'challenge_id': challenge['id'], 'code': body.code})
        cookie(response, data['access_token'])
        return {'ok': True}

    @app.post('/api/auth/logout')
    def logout(request: Request, response: Response):
        token = request.cookies.get(COOKIE)
        if cloud() and token:
            try:
                provider('POST', '/logout', token)
            except HTTPException:
                pass
        response.delete_cookie(COOKIE, secure=True, httponly=True, samesite='strict', path='/')
        response.delete_cookie(PENDING, secure=True, httponly=True, samesite='strict', path='/')
        return {'ok': True}
