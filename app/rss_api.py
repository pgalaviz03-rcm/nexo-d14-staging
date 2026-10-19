"""FastAPI router installer for authorized feeds and manual records, bound to project isolation."""
import csv,io,os,re,ssl,logging,json
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends, UploadFile, File
from pydantic import BaseModel,Field
from .models import FeedSource, NewsArticle, AuditEvent
from .listening import validate_feed_url, fetch_rss, parse_feed, normalize_url, digest_url, safe_text
from .controls import take_quota

class FeedInput(BaseModel):
    title:str=Field(min_length=3,max_length=180)
    url:str=Field(min_length=12,max_length=1500)


def safe_feed_failure(exc):
    """Whitelisted diagnostics only: never persist raw exceptions or feed content."""
    message = str(exc) if isinstance(exc, ValueError) else ''
    status = re.fullmatch(r'La fuente devolvió HTTP ([1-5][0-9]{2})', message)
    if status:
        return 'http_' + status[1], 'El medio respondió HTTP ' + status[1] + '; revisa su fuente original.'
    if isinstance(exc, ssl.SSLError):
        return 'tls', 'No se pudo validar la conexión segura del medio.'
    if isinstance(exc, TimeoutError) or message == 'Tiempo RSS agotado':
        return 'timeout', 'El medio tardó demasiado en responder; inténtalo más tarde.'
    if 'DNS' in message:
        return 'dns', 'No se pudo validar una dirección pública del medio.'
    if message == 'Compresión de RSS no permitida':
        return 'compression', 'El medio entregó una compresión que este piloto no admite.'
    if message in {'RSS excede 2 MB', 'RSS sobrepasa 2 MB'}:
        return 'size_limit', 'La fuente supera el límite de 2 MB del piloto.'
    if message == 'Tipo de contenido no permitido':
        return 'content_type', 'La dirección no entregó un tipo de contenido RSS admitido.'
    if message in {'XML de fuente RSS/Atom inválido', 'No es un documento RSS o Atom'}:
        return 'invalid_feed', 'La dirección no entregó un RSS o Atom válido.'
    if message == 'RSS válido sin elementos importables':
        return 'empty_feed', 'La fuente no contiene publicaciones importables.'
    return 'unavailable', 'Fuente temporalmente no disponible; revisar configuración y conectividad.'


def install_rss_api(app,db,current_user,allow):
    @app.get('/api/projects/{pid}/feeds')
    def feeds(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        data=session.scalars(select(FeedSource).where(FeedSource.project_id==pid).order_by(FeedSource.id)).all()
        return [dict(id=x.id,title=x.title,url=x.url,status=x.status,last_error=x.last_error,
          last_checked_at=x.last_checked_at.isoformat() if x.last_checked_at else None) for x in data]

    @app.post('/api/projects/{pid}/feeds')
    def add_feed(pid:int,body:FeedInput,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor'})
        try:url=validate_feed_url(body.url)
        except ValueError as exc:raise HTTPException(422,str(exc))
        count=session.scalar(select(func.count(FeedSource.id)).where(FeedSource.project_id==pid))
        if count>=5:raise HTTPException(429,'Máximo 5 fuentes por proyecto en el piloto')
        if session.scalar(select(FeedSource).where(FeedSource.project_id==pid,FeedSource.url==url)):
            raise HTTPException(409,'Fuente ya registrada')
        source=FeedSource(project_id=pid,created_by=user.id,title=body.title.strip(),url=url)
        session.add(source);session.flush()
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='feed.create',target=str(source.id)))
        session.commit()
        return {'id':source.id,'status':'pending','detail':'Fuente registrada; requiere sincronización explícita'}

    @app.post('/api/projects/{pid}/feeds/{fid}/sync')
    def refresh_feed(pid:int,fid:int,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'})
        take_quota(session,pid,'rss.sync',96)
        source=session.scalar(select(FeedSource).where(FeedSource.id==fid,FeedSource.project_id==pid).with_for_update())
        if not source:raise HTTPException(404,'Fuente no disponible')
        now=datetime.now(timezone.utc)
        if source.last_checked_at:
            last=source.last_checked_at.replace(tzinfo=timezone.utc) if source.last_checked_at.tzinfo is None else source.last_checked_at
            if now-last<timedelta(seconds=60):raise HTTPException(429,'Espera al menos 60 segundos entre actualizaciones')
        # Record attempt before network I/O (also throttles failed requests).
        source.last_checked_at=now;source.status='updating';session.commit()
        try:
            items=parse_feed(fetch_rss(source.url))
            if not items:raise ValueError('RSS válido sin elementos importables')
            inserted=0
            for item in items:
                digest=digest_url(item['url'])
                existing=session.scalar(select(NewsArticle.id).where(NewsArticle.project_id==pid,NewsArticle.url_hash==digest))
                if existing:continue
                session.add(NewsArticle(project_id=pid,feed_id=source.id,publisher=source.title,
                    url=item['url'],url_hash=digest,title=item['title'],abstract=item['abstract'],
                    published_at=item['published_at'],origin='rss'))
                inserted+=1
            source.status='active';source.last_error=None
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='feed.sync',target=f'{fid}:{inserted}'))
            session.commit()
            return {'source':source.title,'inserted':inserted,'read':len(items),'status':'active'}
        except Exception as exc:
            session.rollback()
            source=session.get(FeedSource, fid)
            if source is None:raise HTTPException(404,'Fuente no disponible')
            code, explanation = safe_feed_failure(exc)
            source.status='error';source.last_error=explanation
            logging.getLogger('nexo').warning(json.dumps({'event':'rss.error','source':fid,'reason':code}))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='feed.error',target=f'{fid}:{code}'))
            session.commit()
            raise HTTPException(502,'La fuente no pudo sincronizarse; los registros históricos se conservan')

    @app.get('/api/projects/{pid}/articles')
    def articles(pid:int,q:str='',limit:int=60,user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        if len(q)>100:raise HTTPException(422,'Búsqueda demasiado extensa')
        limit=max(1,min(limit,100))
        stmt=select(NewsArticle).where(NewsArticle.project_id==pid)
        if q.strip():
            token='%'+q.strip().replace('%','\\%').replace('_','\\_')+'%'
            stmt=stmt.where(NewsArticle.title.ilike(token,escape='\\') | NewsArticle.abstract.ilike(token,escape='\\'))
        rows=session.scalars(stmt.order_by(NewsArticle.id.desc()).limit(limit)).all()
        return [dict(id=x.id,title=x.title,url=x.url,publisher=x.publisher,
           abstract=x.abstract,origin=x.origin,published_at=x.published_at.isoformat() if x.published_at else None,
           ingested_at=x.ingested_at.isoformat()) for x in rows]

    @app.post('/api/projects/{pid}/articles/import')
    async def import_articles_csv(pid:int,file:UploadFile=File(...),user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'})
        take_quota(session,pid,'articles.import',20)
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(422,'Se requiere archivo CSV')
        raw=await file.read(500_001)
        if not raw or len(raw)>500_000:raise HTTPException(413,'CSV máximo 500 KB')
        try:
            rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        except (UnicodeDecodeError,csv.Error):raise HTTPException(422,'CSV inválido')
        required={'title','url','source'}
        if not rows or not required.issubset(rows[0]):raise HTTPException(422,'Columnas requeridas: title,url,source')
        if len(rows)>500:raise HTTPException(413,'Máximo 500 registros por carga')
        validated=[];errors=[]
        for n,row in enumerate(rows,2):
            try:
                url=normalize_url(row['url'])
                title=safe_text(row['title'],650);publisher=safe_text(row['source'],180)
                if not title or not publisher:raise ValueError('Título/fuente vacíos')
                validated.append((url,title,publisher,safe_text(row.get('description',''),1300)))
            except (ValueError,TypeError) as exc:errors.append({'line':n,'error':str(exc)[:110]})
        if errors:raise HTTPException(422,{'message':'Corrige filas antes de importar','errors':errors[:12]})
        inserted=0
        candidate_hashes=[digest_url(x[0]) for x in validated]
        existing_hashes=set(session.scalars(select(NewsArticle.url_hash).where(NewsArticle.project_id==pid,NewsArticle.url_hash.in_(candidate_hashes))).all())
        for url,title,publisher,abstract in validated:
            digest=digest_url(url)
            if digest in existing_hashes:continue
            session.add(NewsArticle(project_id=pid,url=url,url_hash=digest,title=title,publisher=publisher,
               abstract=abstract,origin='csv'))
            existing_hashes.add(digest);inserted+=1
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='articles.import',target=f'{inserted}'))
        session.commit()
        return {'inserted':inserted,'received':len(validated),'origin':'csv','note':'Carga manual; no representa una medición de opinión'}
