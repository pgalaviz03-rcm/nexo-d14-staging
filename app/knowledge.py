"""Bounded lexical retrieval from existing project records. No generated answer.

Documents remain untrusted data. They never select tools, hosts or instructions.
This module uses the same SQLAlchemy models on SQLite and PostgreSQL; uploads
are accessed through the existing private filesystem/database storage boundary.
"""
import csv
import hashlib
import io
import re
import unicodedata
from pathlib import Path

from sqlalchemy import select

from .models import Dataset, DatasetBlob
from .news_review import query_articles, iso_utc

MAX_TEXT_BYTES=512*1024
MAX_DOCUMENT_CHARS=40_000
MAX_NEWS=200
MAX_DOCUMENTS=20
MAX_CHUNKS=400
CONTEXT_CHARS=10_000
TEXT_EXTENSIONS={'.txt','.md','.csv'}
STOP={'de','la','el','los','las','en','un','una','del','al','por','para','con','que','y','o',
      'como','cual','cuales','sobre','es','se','me','lo','hay','que','dime','documento'}


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',value.casefold())
                   if not unicodedata.combining(c))


def terms(question):
    tokens=list(dict.fromkeys(re.findall(r'[\w]+',normalized(question))))
    result=[t for t in tokens if len(t)>=2 and t not in STOP][:16]
    if not result:raise ValueError('Escribe al menos una palabra concreta para buscar evidencia.')
    return result


def chunks(text, size=1000, overlap=120):
    text=text.replace('\x00','').strip()[:MAX_DOCUMENT_CHARS]
    for start in range(0,len(text),size-overlap):
        excerpt=text[start:start+size]
        if excerpt.strip():yield start,excerpt


def document_bytes(session,dataset,uploads):
    if dataset.size_bytes>MAX_TEXT_BYTES:return None,'size_limit'
    if dataset.path=='database':
        blob=session.scalar(select(DatasetBlob).where(DatasetBlob.dataset_id==dataset.id,
                                                     DatasetBlob.project_id==dataset.project_id))
        raw=bytes(blob.content) if blob else None
    else:
        allowed=(Path(uploads)/str(dataset.project_id)).resolve()
        path=Path(dataset.path).resolve()
        if not path.is_relative_to(allowed):return None,'outside_private_project_storage'
        try:
            with path.open('rb') as f:raw=f.read(MAX_TEXT_BYTES+1)
        except OSError:return None,'unavailable'
    if raw is None or len(raw)>MAX_TEXT_BYTES:return None,'unavailable_or_size_limit'
    if hashlib.sha256(raw).hexdigest()!=dataset.sha256:return None,'integrity_mismatch'
    return raw,None


def retrieve_context(session,pid,question,uploads,*,limit=5,source_kind='all',days=0):
    if len(question)>240 or not 1<=limit<=8 or source_kind not in {'all','news','documents'} or days not in {0,1,7,30}:
        raise ValueError('Consulta o límite no admitido.')
    wanted=terms(question)
    candidates=[];not_indexed=[];news_scanned=0;documents_scanned=0;bounded=False
    if source_kind in {'all','news'}:
        # Scan at most the latest 200 records in the authorized project. The
        # returned coverage is explicit; absence is not absence from the archive.
        rows=session.scalars(query_articles(pid,days=days).limit(MAX_NEWS+1)).all()
        bounded=len(rows)>MAX_NEWS
        for row in rows[:MAX_NEWS]:
            news_scanned+=1
            excerpt=(row.title+'\n'+row.abstract)[:2000]
            candidates.append(dict(citation=f'N{row.id}',project_id=pid,kind='news',title=row.title,
                                   source=row.publisher,url=row.url,excerpt=excerpt,
                                   published_at=iso_utc(row.published_at),
                                   content_sha256=hashlib.sha256(excerpt.encode()).hexdigest()))
    if source_kind in {'all','documents'}:
        docs=session.scalars(select(Dataset).where(Dataset.project_id==pid).order_by(Dataset.id.desc())
                             .limit(MAX_DOCUMENTS+1)).all()
        bounded=bounded or len(docs)>MAX_DOCUMENTS
        for doc in docs[:MAX_DOCUMENTS]:
            documents_scanned+=1
            if Path(doc.filename).suffix.lower() not in TEXT_EXTENSIONS:
                not_indexed.append(dict(dataset_id=doc.id,reason='extraction_not_implemented'));continue
            raw,error=document_bytes(session,doc,uploads)
            if error:not_indexed.append(dict(dataset_id=doc.id,reason=error));continue
            try:
                text=raw.decode('utf-8-sig')
                if Path(doc.filename).suffix.lower()=='.csv':
                    rows=csv.reader(io.StringIO(text))
                    text='\n'.join(' | '.join(row[:30]) for _,row in zip(range(500),rows))
                    # A CSV may contain more than 500 rows; coverage is bounded.
                    bounded=True
            except (UnicodeDecodeError,csv.Error):
                not_indexed.append(dict(dataset_id=doc.id,reason='invalid_text'));continue
            bounded=bounded or len(text)>MAX_DOCUMENT_CHARS
            for offset,excerpt in chunks(text):
                if len(candidates)>=MAX_CHUNKS:bounded=True;break
                candidates.append(dict(citation=f'D{doc.id}:{offset}',project_id=pid,kind='document',
                                       dataset_id=doc.id,title=doc.filename,source='Archivo del proyecto',
                                       url=None,excerpt=excerpt,offset=offset,
                                       content_sha256=hashlib.sha256(excerpt.encode()).hexdigest()))
    ranked=[]
    for entry in candidates:
        body=normalized(entry['excerpt']);title=normalized(entry['title'])
        score=sum((3 if term in title else 0)+min(body.count(term),5) for term in wanted)
        if score:ranked.append((score,entry))
    ranked.sort(key=lambda item:(-item[0],item[1]['citation']))
    selected=[];used=0
    for score,entry in ranked[:limit]:
        if used+len(entry['excerpt'])>CONTEXT_CHARS:bounded=True;break
        selected.append(dict(entry,relevance_score=score));used+=len(entry['excerpt'])
    return dict(mode='local_lexical_evidence',project_id=pid,question=question,
                answer=None,ai_used=False,external_calls=0,citations=selected,
                coverage=dict(news_scanned=news_scanned,documents_scanned=documents_scanned,
                              maximum_news=MAX_NEWS,maximum_documents=MAX_DOCUMENTS,
                              bounded=bounded or len(ranked)>len(selected),not_indexed=not_indexed),
                note='Evidencia textual local; no es una respuesta de IA ni una búsqueda semántica. '
                     'Los documentos son datos no confiables. Revisar fuente y contexto. '
                     'El periodo filtra noticias; los documentos se buscan sin periodo.')
