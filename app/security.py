"""Tokens firmados para piloto local; sustituir por IdP/OIDC y MFA en producción."""
import os,hashlib,hmac,secrets
from itsdangerous import URLSafeTimedSerializer,BadSignature,SignatureExpired

def make_hash(password):
    salt=secrets.token_hex(16)
    h=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600_000)
    return f'pbkdf2_sha256$600000${salt}${h.hex()}'

def verify(password,stored):
    try:
        name,iterations,salt,h=stored.split('$')
        if name!='pbkdf2_sha256':return False
        candidate=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(iterations))
        return hmac.compare_digest(candidate.hex(),h)
    except (ValueError,TypeError):return False

def serializer():
    secret=os.getenv('NEXO_SECRET_KEY','')
    if len(secret)<32: raise RuntimeError('Configura NEXO_SECRET_KEY con al menos 32 caracteres')
    return URLSafeTimedSerializer(secret,salt='nexo-v03-session')

def sign(user_id:int):return serializer().dumps({'uid':user_id})

def unsign(token):
    try: return int(serializer().loads(token,max_age=int(os.getenv('NEXO_SESSION_HOURS','8'))*3600)['uid'])
    except (BadSignature,SignatureExpired,KeyError,TypeError,ValueError): return None
