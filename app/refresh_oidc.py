"""Verify short-lived GitHub OIDC; only a daily refresh is authorized.
No user session, database password or long-lived scheduler secret is accepted.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,time,threading
import httpx,jwt
from fastapi import HTTPException

ISSUER='https://token.actions.githubusercontent.com'
CACHE={'until':0,'keys':[]};LOCK=threading.Lock()
def scheduler_config():
 p=Path(__file__).resolve().parents[1]/'config/refresh_scheduler.json'
 return json.loads(p.read_text(encoding='utf8'))
def signing_keys():
 with LOCK:
  if CACHE['until']>time.monotonic():return CACHE['keys']
  try:
   with httpx.Client(timeout=5,follow_redirects=False,trust_env=False)as client:
    with client.stream('GET',ISSUER+'/.well-known/jwks')as response:
     response.raise_for_status();raw=b''
     for block in response.iter_bytes():
      raw+=block
      if len(raw)>64000:raise ValueError('Key set too large')
   keys=json.loads(raw)['keys']
   if not isinstance(keys,list)or len(keys)>20:raise ValueError('Invalid keys')
   CACHE.update(until=time.monotonic()+600,keys=keys);return keys
  except Exception:raise HTTPException(503,'No se pudo verificar el disparador de actualización.')from None

def verify_scheduler(authorization,config=None,keys=None):
 cfg=config or scheduler_config()
 if not authorization or not authorization.startswith('Bearer ')or len(authorization)>16000:raise HTTPException(401,'Disparador no autorizado.')
 try:
  token=authorization[7:];header=jwt.get_unverified_header(token)
  if header.get('alg')!='RS256'or not isinstance(header.get('kid'),str)or len(header['kid'])>128:raise ValueError('Invalid header')
  selected=next(k for k in (keys if keys is not None else signing_keys())if k.get('kid')==header['kid'])
  key=jwt.PyJWK.from_dict(selected,algorithm='RS256').key
  claims=jwt.decode(token,key,algorithms=['RS256'],issuer=ISSUER,audience=cfg['audience'],leeway=10,
   options={'require':['iss','aud','exp','iat','nbf','sub','repository_id','repository','ref','workflow_ref','event_name']})
  expected=cfg['repository']+'/.github/workflows/daily-refresh.yml@refs/heads/main'
  if claims['repository_id']!=str(cfg['repository_id'])or claims['repository']!=cfg['repository']or claims['ref']!='refs/heads/main'or claims['workflow_ref']!=expected or claims['event_name']not in {'schedule','workflow_dispatch'}or claims['exp']-claims['iat']>900:
   raise ValueError('Wrong scope')
  return int(cfg['operator_id'])
 except HTTPException:raise
 except Exception:raise HTTPException(401,'Disparador no autorizado.')from None
