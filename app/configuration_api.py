"""Owner-only project configuration, encrypted credentials, offline media ingress."""
from datetime import datetime,timezone
import hashlib,json
from fastapi import Depends,HTTPException
from sqlalchemy import select,func,update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from cryptography.fernet import InvalidToken
from .configuration import IntegrationSetting,IntegrationInput,CATALOG,secret_cipher,integration_record,MediaOutlet,MediaArticleLink,MediaInput,MediaBatch
from .models import AuditEvent,NewsArticle
from .client_access import is_owner
from .actors_api import lock_project
from .controls import take_quota
from .network_service import aware
from .config import cloud

def install_configuration_api(app,db,current_user,allow):
 from fastapi.exceptions import RequestValidationError
 from fastapi.exception_handlers import request_validation_exception_handler
 from starlette.responses import JSONResponse
 async def validation_error(request,exc):
  if '/settings/integrations/' in request.url.path:return JSONResponse({'detail':'Revisa los campos de la integración.'},status_code=422)
  if '/settings/media' in request.url.path:
   labels={'name':'nombre','site_url':'sitio web','channels':'cuentas','url':'enlace','published_at':'fecha de publicación','captured_at':'fecha de captura','items':'publicaciones'}
   fields=[]
   for error in exc.errors()[:3]:
    parts=[str(v+1) if isinstance(v,int) else labels.get(v,str(v)) for v in error.get('loc',[]) if v!='body']
    fields.append(' · '.join(parts) or 'archivo o ficha del medio')
   return JSONResponse({'detail':'Revisa: '+', '.join(fields)+'. Usa enlaces HTTPS y fechas con zona horaria.'},status_code=422)
  return await request_validation_exception_handler(request,exc)
 if hasattr(app,'add_exception_handler'):app.add_exception_handler(RequestValidationError,validation_error)
 engine=getattr(app.state,'engine',None)
 if engine is not None and engine.dialect.name=='sqlite':
  for model in [IntegrationSetting,MediaOutlet,MediaArticleLink]:model.__table__.create(bind=engine,checkfirst=True)
 def owner(pid,user,session):
  allow(pid,user,session)
  if not is_owner(session,user):raise HTTPException(403,'Configuración exclusiva del superadministrador.')
  if cloud() and session.bind.dialect.name!='postgresql':raise HTTPException(409,'La nube requiere PostgreSQL.')
 @app.get('/api/projects/{pid}/settings/integrations')
 def integrations(pid:int,user=Depends(current_user),session:Session=Depends(db)):
  owner(pid,user,session)
  rows={r.kind:r for r in session.scalars(select(IntegrationSetting).where(IntegrationSetting.project_id==pid)).all()}
  return dict(project_id=pid,items=[integration_record(rows.get(k),k) for k in CATALOG],external_calls=0)
 @app.put('/api/projects/{pid}/settings/integrations/{kind}')
 def save_integration(pid:int,kind:str,body:IntegrationInput,user=Depends(current_user),session:Session=Depends(db)):
  owner(pid,user,session)
  if kind not in CATALOG:raise HTTPException(404,'Integración no disponible.')
  if kind!='apify' and body.apify_processes is not None:raise HTTPException(422,'Estos procesos corresponden a Apify.')
  if set(body.secrets)-set(CATALOG[kind][1]):raise HTTPException(422,'Credencial no admitida para esta integración.')
  take_quota(session,pid,'settings.integration',100);lock_project(session,pid)
  previous=session.get(IntegrationSetting,(pid,kind))
  if (previous.version if previous else 0)!=body.expected_version:raise HTTPException(409,'La configuración cambió. Vuelve a cargarla.')
  encrypted=previous.secrets_ciphertext if previous else ''
  if body.clear_secrets:encrypted=''
  elif body.secrets:
   cipher=secret_cipher()
   try:saved=json.loads(cipher.decrypt(encrypted.encode())) if encrypted else {}
   except (InvalidToken,ValueError,UnicodeError):raise HTTPException(409,'Borra y vuelve a configurar las credenciales tras un cambio de clave.') from None
   saved.update({k:v.get_secret_value() for k,v in body.secrets.items()})
   encrypted=cipher.encrypt(json.dumps(saved).encode()).decode()
  config=body.model_dump(exclude={'secrets','clear_secrets','expected_version'})
  if body.apify_processes is None:
   config.pop('apify_processes',None)
   previous_config=json.loads(previous.config_json) if previous else {}
   if kind=='apify' and 'apify_processes' in previous_config:config['apify_processes']=previous_config['apify_processes']
  values=dict(config_json=json.dumps(config,ensure_ascii=False),secrets_ciphertext=encrypted,version=body.expected_version+1,updated_by=user.id,updated_at=datetime.now(timezone.utc))
  try:
   if previous:
    for k,v in values.items():setattr(previous,k,v)
   else:session.add(IntegrationSetting(project_id=pid,kind=kind,**values))
   session.add(AuditEvent(project_id=pid,user_id=user.id,action='settings.integration',target=kind+':v'+str(values['version'])))
   session.commit();return integration_record(session.get(IntegrationSetting,(pid,kind)),kind)
  except IntegrityError:session.rollback();raise HTTPException(409,'La configuración cambió. Vuelve a cargarla.') from None
 def media_record(row):return dict(id=row.id,name=row.name,site_url=row.site_url,channels=json.loads(row.channels_json),active=row.active,version=row.version)
 @app.get('/api/projects/{pid}/settings/media')
 def media(pid:int,user=Depends(current_user),session:Session=Depends(db)):
  owner(pid,user,session)
  rows=session.scalars(select(MediaOutlet).where(MediaOutlet.project_id==pid).order_by(MediaOutlet.name).limit(101)).all()
  return dict(project_id=pid,items=[media_record(r) for r in rows[:100]],bounded=len(rows)>100,external_calls=0)
 def store_media(pid,body,user,session,mid=None):
  owner(pid,user,session);take_quota(session,pid,'settings.media',100);lock_project(session,pid)
  row=session.scalar(select(MediaOutlet).where(MediaOutlet.id==mid,MediaOutlet.project_id==pid)) if mid else None
  if mid and not row:raise HTTPException(404,'Medio no disponible.')
  if (row.version if row else 0)!=body.expected_version:raise HTTPException(409,'La ficha cambió. Vuelve a cargarla.')
  if not row and session.scalar(select(func.count()).select_from(MediaOutlet).where(MediaOutlet.project_id==pid))>=100:raise HTTPException(422,'Máximo 100 medios por proyecto.')
  if body.active:
   chosen={(c.network,c.url) for c in body.channels if c.enabled}
   other=session.scalars(select(MediaOutlet).where(MediaOutlet.project_id==pid,MediaOutlet.active.is_(True),MediaOutlet.id!=(mid or 0))).all()
   if any(chosen & {(c['network'],c['url']) for c in json.loads(m.channels_json) if c.get('enabled',True)} for m in other):
    raise HTTPException(409,'Esa cuenta ya está registrada en otro medio del proyecto.')
  values=dict(name=body.name,name_key=body.name.casefold(),site_url=body.site_url,channels_json=json.dumps([c.model_dump() for c in body.channels]),active=body.active,version=body.expected_version+1,updated_by=user.id)
  try:
   if row:
    for k,v in values.items():setattr(row,k,v)
   else:row=MediaOutlet(project_id=pid,**values);session.add(row)
   session.flush();session.add(AuditEvent(project_id=pid,user_id=user.id,action='settings.media',target='media:'+str(row.id)+':v'+str(row.version)))
   session.commit();return media_record(row)
  except IntegrityError:session.rollback();raise HTTPException(409,'Ese nombre ya está registrado en este proyecto.') from None
 @app.post('/api/projects/{pid}/settings/media')
 def create_media(pid:int,body:MediaInput,user=Depends(current_user),session:Session=Depends(db)):return store_media(pid,body,user,session)
 @app.put('/api/projects/{pid}/settings/media/{media_id}')
 def edit_media(pid:int,media_id:int,body:MediaInput,user=Depends(current_user),session:Session=Depends(db)):return store_media(pid,body,user,session,media_id)
 @app.post('/api/projects/{pid}/settings/media/{media_id}/publications/import')
 def ingest_media(pid:int,media_id:int,body:MediaBatch,user=Depends(current_user),session:Session=Depends(db)):
  owner(pid,user,session)
  if len(body.model_dump_json().encode())>1_000_000:raise HTTPException(422,'Máximo 1 MB por lote normalizado.')
  row=session.scalar(select(MediaOutlet).where(MediaOutlet.id==media_id,MediaOutlet.project_id==pid,MediaOutlet.active.is_(True)))
  if not row:raise HTTPException(404,'Medio no disponible.')
  if not any(c['network']==body.network and c['url']==body.account_url and c.get('enabled',True) for c in json.loads(row.channels_json)):
   raise HTTPException(422,'Registra y activa esa cuenta del medio.')
  if body.captured_at>datetime.now(timezone.utc):raise HTTPException(422,'La captura no puede estar en el futuro.')
  take_quota(session,pid,'settings.media_import',30);lock_project(session,pid);inserted=duplicates=0
  try:
   for p in body.items:
    link=session.scalar(select(MediaArticleLink).where(MediaArticleLink.project_id==pid,MediaArticleLink.media_id==media_id,MediaArticleLink.network==body.network,MediaArticleLink.external_id==p.external_id))
    digest=hashlib.sha256(p.url.encode()).hexdigest()
    if link:
     article=session.get(NewsArticle,link.article_id)
     if article.url_hash!=digest:raise HTTPException(409,'Un identificador de origen ya corresponde a otra publicación.')
     duplicates+=1;continue
    article=session.scalar(select(NewsArticle).where(NewsArticle.project_id==pid,NewsArticle.url_hash==digest))
    if article:duplicates+=1
    else:
     article=NewsArticle(project_id=pid,title=p.title.strip(),url=p.url,url_hash=digest,publisher=row.name,abstract=p.text[:4000],origin='media_social',published_at=p.published_at)
     session.add(article);session.flush();inserted+=1
    session.add(MediaArticleLink(project_id=pid,media_id=media_id,article_id=article.id,network=body.network,account_url=body.account_url,external_id=p.external_id,captured_at=body.captured_at));session.flush()
   session.add(AuditEvent(project_id=pid,user_id=user.id,action='settings.media_import',target=f'media:{media_id}:new:{inserted}:same:{duplicates}'))
   session.commit();return dict(inserted=inserted,duplicates=duplicates,external_calls=0)
  except Exception:session.rollback();raise
