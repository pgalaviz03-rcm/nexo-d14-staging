"""Read-only external health probe; schedule only after authorization."""
import sys,time,os,json
import httpx
def main():
    origin=os.environ['NEXO_PUBLIC_ORIGIN'].rstrip('/')
    if not origin.startswith('https://'):raise SystemExit('HTTPS obligatorio')
    started=time.monotonic()
    try:
        with httpx.Client(timeout=8,follow_redirects=False,trust_env=False) as c:
            r=c.get(origin+'/api/ready')
        ok=r.status_code==200 and r.json().get('status')=='ready'
    except (httpx.HTTPError,ValueError):ok=False
    print(json.dumps({'event':'readiness','ok':ok,'ms':round((time.monotonic()-started)*1000)}))
    return 0 if ok else 1
if __name__=='__main__':sys.exit(main())
