"""Bounded lexical archive and revalidated selections; no network or model calls."""
from datetime import datetime,timezone
from pathlib import Path
import json,hashlib
from fastapi import HTTPException
from sqlalchemy import select,func,and_,exists
from .models import NewsArticle,Dataset
from .pulse_models import PulseActor,PulseDocument,PulseMention
from .knowledge import document_bytes,normalized,TEXT_EXTENSIONS,MAX_DOCUMENT_CHARS
from .news_review import iso_utc
from .network_service import aware

MAX_NEWS=500;MAX_SOCIAL=500;MAX_DOCUMENTS=100;MAX_TEXT_DOCUMENTS=20;PAGE_SIZE=20
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def document_text(session,row,uploads):
    if Path(row.filename).suffix.lower() not in TEXT_EXTENSIONS:return '', 'metadata_only'
    raw,error=document_bytes(session,row,uploads)
    if error:return '',error
    try:return raw.decode('utf-8-sig').replace('\x00','')[:MAX_DOCUMENT_CHARS],'text_verified'
    except UnicodeError:return '', 'invalid_text'
def entry(session,row,kind,uploads,*,read_text=True):
    if kind=='news':
        title,body,url,source,network=row.title,row.abstract,row.url,row.publisher,'press'
        at=row.published_at or row.ingested_at;basis='published' if row.published_at else 'ingested';status='stored_excerpt'
    elif kind=='social':
        title,body,url,source,network=row.title,row.text,row.url,row.network,row.network
        at=row.published_at;basis='published';status='stored_excerpt'
    else:
        title,url,source,network=row.filename,None,'Archivos del proyecto','file';at=row.created_at;basis='uploaded'
        body,status=document_text(session,row,uploads) if read_text else ('','metadata_only')
    base=dict(reference=f'{kind}:{row.id}',kind=kind,title=title,source=source,network=network,url=url,at=iso_utc(at),date_basis=basis,
        body=body,preview_status=status,file_sha256=row.sha256 if kind=='document' else None)
    base['content_sha256']=digest(base);return base
def public_entry(e,*,query='',limit=600):
    body=e['body'];pos=normalized(body).find(normalized(query)) if query else 0;start=max(0,pos-100)
    excerpt=body[start:start+limit]
    return {**{k:v for k,v in e.items() if k!='body'},'excerpt':excerpt,'excerpt_bounded':start>0 or len(body)>len(excerpt)}
def resolve(session,pid,reference,uploads):
    kind,rawid=reference.split(':');model={'news':NewsArticle,'social':PulseDocument,'document':Dataset}.get(kind)
    if model is None or not rawid.isdigit():raise HTTPException(404,'Fuente no disponible.')
    q=select(model).where(model.project_id==pid,model.id==int(rawid))
    if kind=='social':q=q.where(PulseDocument.is_demo.is_(False))
    row=session.scalar(q)
    if row is None:raise HTTPException(404,'Fuente no disponible.')
    return entry(session,row,kind,uploads)
def search(session,pid,query,uploads):
    actors=session.scalars(select(PulseActor).where(PulseActor.project_id==pid,PulseActor.is_demo.is_(False)).order_by(PulseActor.active.desc(),PulseActor.id).limit(100)).all()
    if query.actor_id and query.actor_id not in {a.id for a in actors}:raise HTTPException(404,'Actor no disponible en este proyecto.')
    now=datetime.now(timezone.utc);entries=[];bounded=False;scanned={};text_read=0;metadata_only=0
    for kind,model,cap,stamp in [('news',NewsArticle,MAX_NEWS,func.coalesce(NewsArticle.published_at,NewsArticle.ingested_at)),
            ('social',PulseDocument,MAX_SOCIAL,PulseDocument.published_at),('document',Dataset,MAX_DOCUMENTS,Dataset.created_at)]:
        if query.kind not in {'all',kind}:continue
        if query.actor_id and kind!='social':continue
        if query.network!='all' and ((kind=='news' and query.network!='press') or kind=='document'):continue
        q=select(model).where(model.project_id==pid,stamp<=now)
        if query.start:q=q.where(stamp>=query.start,stamp<query.end)
        if kind=='social':
            q=q.where(PulseDocument.is_demo.is_(False))
            if query.network!='all':q=q.where(PulseDocument.network==query.network)
            if query.actor_id:q=q.where(exists(select(PulseMention.document_id).where(PulseMention.project_id==pid,PulseMention.document_id==PulseDocument.id,PulseMention.actor_id==query.actor_id,PulseMention.is_demo.is_(False))))
        rows=session.scalars(q.order_by(stamp.desc(),model.id.desc()).limit(cap+1)).all();bounded=bounded or len(rows)>cap;scanned[kind]=min(len(rows),cap)
        for row in rows[:cap]:
            read_text=kind=='document' and text_read<MAX_TEXT_DOCUMENTS
            if read_text and Path(row.filename).suffix.lower() in TEXT_EXTENSIONS:text_read+=1
            e=entry(session,row,kind,uploads,read_text=read_text)
            if kind=='document' and ((not read_text and Path(row.filename).suffix.lower() in TEXT_EXTENSIONS) or len(e['body'])>=MAX_DOCUMENT_CHARS):bounded=True
            if kind=='document' and e['preview_status']!='text_verified':metadata_only+=1
            entries.append(e)
    sources=sorted({(e['kind']+':'+e['source'],e['source']) for e in entries})
    words=list(dict.fromkeys(normalized(query.q).split()))
    matches=[]
    for e in entries:
        if query.source and query.source!=e['kind']+':'+e['source']:continue
        text=normalized(e['title']+' '+e['body']) if words else ''
        if all(w in text for w in words):matches.append(e)
    matches.sort(key=lambda e:(e['at'],e['reference']),reverse=True);page=matches[query.offset:query.offset+PAGE_SIZE]
    return dict(project_id=pid,items=[public_entry(e,query=query.q) for e in page],matched_in_scan=len(matches),
        counts={k:sum(e['kind']==k for e in matches) for k in ('news','social','document')},
        sources=[dict(value=v,label=l) for v,l in sources],actors=[dict(id=a.id,name=a.name,active=a.active) for a in actors],
        offset=query.offset,page_size=PAGE_SIZE,has_more=query.offset+PAGE_SIZE<len(matches),filters=query.model_dump(mode='json'),
        coverage=dict(bounded=bounded,scanned=scanned,document_texts_attempted=text_read,documents_metadata_only=metadata_only,
            maximum_news=MAX_NEWS,maximum_social=MAX_SOCIAL,maximum_documents=MAX_DOCUMENTS,maximum_document_texts=MAX_TEXT_DOCUMENTS),
        mode='local_archive_lexical_v1',ai_used=False,external_calls=0)
def selection(session,pid,references,uploads):
    sources=[resolve(session,pid,r,uploads) for r in references]
    if any(e['kind']=='document' and e['preview_status']!='text_verified' for e in sources):raise HTTPException(422,'Elige documentos con texto verificable para preparar una selección con citas.')
    cites=[dict(citation=e['reference'],project_id=pid,kind=e['kind'],title=e['title'],source=e['source'],url=e['url'],published_at=e['at'],
        date_basis=e['date_basis'],excerpt=e['body'][:1500] or e['title'],content_sha256=e['content_sha256']) for e in sources]
    frozen=dict(project_id=pid,citations=cites,mode='explorer_selection_v1')
    return dict(**frozen,preview_sha256=digest(frozen),ai_used=False,external_calls=0)
