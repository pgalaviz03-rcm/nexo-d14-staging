"""Allowlisted Facebook output mapping. Unclassified public content; no inferred beliefs."""
from datetime import datetime,timezone
from urllib.parse import urlsplit,urlunsplit
import hashlib,json
from sqlalchemy import select
from .actors_api import PublicChannel
from .pulse_models import PulseActor,PulseAccount,PulseDocument,PulseMention
from .pulse_api import import_posts
from .apify_port import PublicPost,ImportBatch
from .configuration import MediaOutlet,MediaArticleLink
from .models import NewsArticle
from .fidelity import FidelityCapture,AtalayaPublicationBatch,Publication,fingerprint
from .fidelity_team import TeamMember,TeamObservation,profile_key

def fburl(value):
 url=PublicChannel(network='facebook',url=str(value or '')).url
 p=urlsplit(url);host=p.hostname.lower()
 # Compare only Facebook aliases, never arbitrary same-path domains.
 if host not in ('facebook.com','www.facebook.com','m.facebook.com','web.facebook.com'):raise ValueError('Unsupported Facebook host')
 return urlunsplit(('https','facebook.com',p.path.rstrip('/'),p.query if p.path=='/profile.php' else '', ''))

def number(value):
 if isinstance(value,str) and value.isdigit():value=int(value)
 return value if type(value)is int and 0<=value<=9007199254740991 else None
def date(value):
 if type(value) in (int,float):return datetime.fromtimestamp(value,tz=timezone.utc)
 value=datetime.fromisoformat(str(value).replace('Z','+00:00'))
 if value.tzinfo is None:raise ValueError('Missing timezone')
 return value.astimezone(timezone.utc)
def match(raw,targets,fields):
 for key in fields:
  try:canonical=fburl(raw.get(key))
  except (ValueError,TypeError):continue
  found=[t for t in targets if fburl(t['url'])==canonical]
  if len(found)==1:return found[0]
 return None

def ingest(session,pid,uid,job,rows,at):
 key=job['key'];targets=job['targets'];stats=dict(inserted=0,duplicates=0,rejected=0,team_events=0,accounts=0)
 publications={};posts_for_next=[];items=[]
 for raw in rows:
  if raw.get('error'):stats['rejected']+=1;continue
  try:
   target=match(raw,targets,('inputUrl','facebookUrl','pageUrl','url') if key=='facebook.profile' else ('inputUrl','facebookUrl','postUrl'))
   if target is None:raise ValueError('Unmatched account/post')
   aid=target.get('actor_id');mid=target.get('media_id')
   if aid:
    actor=session.scalar(select(PulseActor).where(PulseActor.id==aid,PulseActor.project_id==pid,PulseActor.active.is_(True),PulseActor.is_demo.is_(False)))
    if not actor:raise ValueError('Actor no longer active')
   if key=='facebook.profile':
    followers=number(raw.get('followers'))
    if not aid or followers is None:raise ValueError('Missing followers')
    exists=session.scalar(select(PulseAccount.id).where(PulseAccount.project_id==pid,PulseAccount.actor_id==aid,PulseAccount.url==target['url'],PulseAccount.captured_at==at))
    if not exists:
     session.add(PulseAccount(project_id=pid,actor_id=aid,network='facebook',url=target['url'],captured_at=at,metrics=json.dumps(dict(followers=followers,provider='apify',source_run=job['run_id'])),is_demo=False,created_by=uid));stats['accounts']+=1
    continue
   if key=='facebook.posts':
    url=PublicChannel(network='facebook',url=raw.get('url','')).url;published=date(raw.get('time',raw.get('timestamp')))
    if published>at or published<date(job['since']):raise ValueError('Outside collection window')
    external=str(raw.get('postId') or '')
    if not external or len(external)>200:raise ValueError('Missing post id')
    text=str(raw.get('text') or '')[:4000];counts=[number(raw.get(k)) for k in ('likes','comments','shares')]
    interactions=sum(counts) if all(v is not None for v in counts) else None
    if aid:
     items.append(PublicPost(network='facebook',external_id=external,url=url,title=(text[:160] or 'Publicación de '+target['name']),text=text,published_at=published,collected_at=at,actor_ids=[aid],interactions=interactions))
     publications.setdefault((aid,target['url']),[]).append(Publication(url=url,published_at=published,text=text[:1000],reactions=counts[0],comments=counts[1],shares=counts[2]))
    elif mid:
     medium=session.scalar(select(MediaOutlet).where(MediaOutlet.id==mid,MediaOutlet.project_id==pid,MediaOutlet.active.is_(True)))
     if not medium:raise ValueError('Medium no longer active')
     digest=hashlib.sha256(url.encode()).hexdigest();article=session.scalar(select(NewsArticle).where(NewsArticle.project_id==pid,NewsArticle.url_hash==digest))
     if not article:
      article=NewsArticle(project_id=pid,title=(text[:650] or medium.name),url=url,url_hash=digest,publisher=medium.name,abstract=text,origin='media_social',published_at=published);session.add(article);session.flush();stats['inserted']+=1
     else:stats['duplicates']+=1
     existing=session.scalar(select(MediaArticleLink.id).where(MediaArticleLink.project_id==pid,MediaArticleLink.media_id==mid,MediaArticleLink.external_id==external,MediaArticleLink.network=='facebook'))
     if not existing:session.add(MediaArticleLink(project_id=pid,media_id=mid,article_id=article.id,network='facebook',account_url=target['url'],external_id=external,captured_at=at))
    posts_for_next.append(dict(url=url,actor_id=aid,media_id=mid,name=target['name'],account_url=target['url'],published_at=published.isoformat()))
   else:
    # Only an observed, exactly matched registered team profile becomes a team event.
    user_url=raw.get('profileUrl') if key=='facebook.comments' else raw.get('reactorProfileUrl')
    identity=profile_key('facebook',user_url) if user_url else ''
    event_id=str(raw.get('commentId') or raw.get('id') or '') if key=='facebook.comments' else ''
    if key=='facebook.comments':
     when=date(raw.get('date'));text=str(raw.get('text') or '')[:4000]
     if not event_id or len(event_id)>180 or not text or when>at or when<date(target['published_at']):raise ValueError('Invalid comment')
     if aid:items.append(PublicPost(network='facebook',external_id='comment:'+event_id,url=PublicChannel(network='facebook',url=raw.get('commentUrl','')).url,title=text[:160],text=text,published_at=when,collected_at=at,actor_ids=[aid]))
    if aid and identity:
     members=session.scalars(select(TeamMember).where(TeamMember.project_id==pid,TeamMember.active.is_(True))).all()
     matched=[m for m in members if json.loads(m.profiles_json).get('facebook')==identity]
     if len(matched)==1:
      kind='comment' if key=='facebook.comments' else 'reaction';source=hashlib.sha256(event_id.encode()).hexdigest() if event_id else ''
      exists=session.scalar(select(TeamObservation.id).where(TeamObservation.project_id==pid,TeamObservation.member_id==matched[0].id,TeamObservation.actor_id==aid,TeamObservation.network=='facebook',TeamObservation.post_url==target['url'],TeamObservation.kind==kind,TeamObservation.source_key==source))
      if not exists:session.add(TeamObservation(project_id=pid,member_id=matched[0].id,actor_id=aid,is_demo=False,network='facebook',post_url=target['url'],kind=kind,source_key=source,observed_at=at,source_kind='apify'));session.flush();stats['team_events']+=1
  except (ValueError,TypeError,KeyError,OverflowError):stats['rejected']+=1
 for (aid,url),pubs in publications.items():
  unique={p.url:p for p in pubs};body=AtalayaPublicationBatch(actor_id=aid,network='facebook',account_url=url,captured_at=at,publications=list(unique.values()));raw,digest=fingerprint(body)
  if not session.scalar(select(FidelityCapture.id).where(FidelityCapture.project_id==pid,FidelityCapture.actor_id==aid,FidelityCapture.account_url==url,FidelityCapture.captured_at==at)):
   session.add(FidelityCapture(project_id=pid,actor_id=aid,is_demo=False,network='facebook',account_url=url,captured_at=at,payload_json=raw,sha256=digest,source_kind='apify',created_by=uid))
 if items:
  # The established importer commits atomically, preserves reviewed labels and deduplicates IDs.
  result=import_posts(session,pid,ImportBatch(provider='apify_export',dataset_ref=job['dataset_id'],items=items),uid)
  stats['inserted']+=result['inserted'];stats['duplicates']+=result['duplicates']
 else:session.commit()
 return stats,posts_for_next
