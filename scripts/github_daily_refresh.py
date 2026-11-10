"""GitHub runner: wake Render, obtain an ephemeral OIDC token, request one cut.
Standard library only. Never logs credentials or provider response bodies.
"""
import json,os,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def main():
 cfg=json.loads((Path(__file__).resolve().parents[1]/'config/refresh_scheduler.json').read_text(encoding='utf8'))
 origin=cfg['audience'].removesuffix('/internal/daily-refresh');parsed=urllib.parse.urlsplit(origin)
 if parsed.scheme!='https'or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Invalid origin')
 client=urllib.request.build_opener(NoRedirect)
 with client.open(origin+'/api/health',timeout=90)as r:
  if r.status!=200:raise RuntimeError('Wake failed')
 url=os.environ['ACTIONS_ID_TOKEN_REQUEST_URL'];p=urllib.parse.urlsplit(url)
 if p.scheme!='https'or not p.hostname or not p.hostname.endswith('.actions.githubusercontent.com'):raise ValueError('Invalid issuer request host')
 url+=('&'if p.query else'?')+urllib.parse.urlencode({'audience':cfg['audience']})
 req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
 with client.open(req,timeout=15)as response:token=json.loads(response.read(20000))['value']
 req=urllib.request.Request(cfg['audience'],method='POST',data=b'',headers={'Authorization':'Bearer '+token,'Origin':origin})
 with client.open(req,timeout=40)as response:
  if response.status!=202:raise RuntimeError('Admission failed')
  packet=json.loads(response.read(2000));print(json.dumps({'accepted_projects':packet['accepted'],'daily_time':'08:00','timezone':'America/Mexico_City'}))
 for tick in range(42):
  time.sleep(10)
  if tick and tick%12==0:
   req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
   with client.open(req,timeout=15) as response:token=json.loads(response.read(20000))['value']
  request=urllib.request.Request(origin+'/internal/refresh-tick',method='POST',data=b'',headers={'Authorization':'Bearer '+token,'Origin':origin})
  with client.open(request,timeout=25) as response:remaining=json.loads(response.read(2000))['running']
  if not remaining:break
 print(json.dumps({'running_after_observation':remaining}))
if __name__=='__main__':
 try:main()
 except Exception as exc:print(json.dumps({'status':'failed','error_type':type(exc).__name__}));raise SystemExit(1)
