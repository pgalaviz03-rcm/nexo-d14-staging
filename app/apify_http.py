"""Fixed-origin Apify transport. No redirects, query tokens, retries or response logging."""
import json,re
import httpx

class ProviderError(Exception):
 def __init__(self,code):self.code=code;super().__init__(code)

def ident(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value):raise ProviderError('invalid_provider_reference')
 return value

class ApifyHTTP:
 def __init__(self,token,transport=None):
  self.client=httpx.Client(base_url='https://api.apify.com/v2/',headers={'Authorization':'Bearer '+token},
   timeout=httpx.Timeout(15,connect=5),follow_redirects=False,trust_env=False,transport=transport)
 def close(self):self.client.close()
 def request(self,method,path,**kwargs):
  try:
   with self.client.stream(method,path,**kwargs) as response:
    if response.status_code not in (200,201):
     raise ProviderError({401:'invalid_token',403:'provider_permission',402:'provider_credit_required',429:'provider_rate_limit'}.get(response.status_code,'provider_http_'+str(response.status_code)))
    raw=bytearray()
    for part in response.iter_bytes():
     raw.extend(part)
     if len(raw)>2_000_000:raise ProviderError('provider_response_too_large')
    return json.loads(raw)
  except (httpx.HTTPError,ValueError,UnicodeError):raise ProviderError('provider_transport_or_json') from None
 def start(self,actor,body,cap,limit):
  if actor not in {'apify/facebook-posts-scraper','apify/facebook-comments-scraper','apify/facebook-pages-scraper','scraper_one/facebook-reactions-scraper'}:raise ProviderError('unsupported_actor')
  return self.request('POST','acts/'+actor.replace('/','~')+'/runs',json=body,
   params={'maxTotalChargeUsd':str(cap),'maxItems':limit,'timeout':180,'waitForFinish':0,'restartOnError':'false'})['data']
 def run(self,run_id):return self.request('GET','actor-runs/'+ident(run_id))['data']
 def items(self,dataset,limit):
  data=self.request('GET','datasets/'+ident(dataset)+'/items',params={'clean':'true','format':'json','limit':min(limit,500)})
  if not isinstance(data,list) or len(data)>500 or any(not isinstance(i,dict) for i in data):raise ProviderError('invalid_dataset')
  return data
