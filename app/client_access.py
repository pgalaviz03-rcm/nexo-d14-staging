"""Local transport policy: project accounts observe; platform owners administer.

The gate applies to legacy and newly registered routes, including routes
installed after this middleware. Membership still controls project visibility.
"""
import json,re
from contextvars import ContextVar
from types import SimpleNamespace
from fastapi import HTTPException,Request
from sqlalchemy import select
from starlette.responses import JSONResponse
from .models import Membership,Project
from .pulse_models import PlatformGrant

READ_POST=re.compile(r'^/api/projects/\d+/(?:knowledge/(?:context|critical-audit|answer)|explorer/selection|library/workbooks/\d+/preview)$')
PRIVATE_READ=re.compile(r'^/api/projects/\d+/briefing/(?:delivery(?:/.*)?|analysis|assessments)$')
READER_CONTEXT=ContextVar('nexo_reader_request',default=False)

def read_membership(allow):
    def access(pid,user,session,roles=None):
        result=allow(pid,user,session,roles=roles) if roles is not None else allow(pid,user,session)
        if READER_CONTEXT.get() and result is not None:
            if roles:raise HTTPException(403,'Solo el superadministrador puede modificar el proyecto.')
            project,member=result
            return project,SimpleNamespace(id=member.id,user_id=member.user_id,project_id=member.project_id,role='viewer')
        return result
    return access

def is_owner(session,user):
    grant=session.get(PlatformGrant,user.id)
    return bool(user.active and grant and grant.active)

def authorize(method,path,user,session):
    owner=is_owner(session,user)
    if owner:return True
    project_match=re.match(r'^/api/projects/(\d+)(?:/|$)',path)
    if project_match:
        pid=int(project_match[1]);project=session.get(Project,pid)
        member=session.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==user.id))
        if not project or project.status!='active' or not member:raise HTTPException(404,'Proyecto no disponible.')
    if PRIVATE_READ.fullmatch(path):raise HTTPException(403,'Esta configuración está reservada al superadministrador.')
    if method not in {'GET','HEAD','OPTIONS'} and not (method=='POST' and READ_POST.fullmatch(path)):
        raise HTTPException(403,'Tu cuenta permite consultar. Los cambios corresponden al superadministrador.')
    return False

def reader_payload(value):
    if isinstance(value,list):return [reader_payload(v) for v in value]
    if not isinstance(value,dict):return value
    result={k:reader_payload(v) for k,v in value.items()}
    for key in result:
        if key.startswith('can_') and key not in {'can_read','can_view','can_export','can_download'}:result[key]=False
    if 'role' in result and result['role'] in {'admin','editor','analyst','viewer'}:result['role']='viewer'
    return result

class ClientReadOnly:
    def __init__(self,app,sessions,current_user):self.app=app;self.sessions=sessions;self.current_user=current_user
    async def __call__(self,scope,receive,send):
        path=scope.get('path','');method=scope.get('method','GET')
        if scope['type']!='http' or not path.startswith('/api/') or path.startswith('/api/auth/') or path in {'/api/health','/api/ready','/api/branding'}:
            return await self.app(scope,receive,send)
        try:
            with self.sessions() as session:
                headers=dict(scope.get('headers',[]));authorization=headers.get(b'authorization',b'').decode('latin-1') or None
                user=self.current_user(request=Request(scope),authorization=authorization,session=session)
                owner=authorize(method,path,user,session)
        except HTTPException as exc:
            return await JSONResponse({'detail':exc.detail},status_code=exc.status_code)(scope,receive,send)
        if owner:
            token=READER_CONTEXT.set(False)
            try:return await self.app(scope,receive,send)
            finally:READER_CONTEXT.reset(token)
        start=None;parts=[];size=0;buffer=False;overflow=False
        async def guarded_send(message):
            nonlocal start,buffer,size,overflow
            if message['type']=='http.response.start':
                start=message;content=dict(message.get('headers',[])).get(b'content-type',b'')
                buffer=b'application/json' in content
                if not buffer:await send(message)
            elif message['type']=='http.response.body' and buffer:
                size+=len(message.get('body',b''))
                if size>8*1024*1024:overflow=True
                if not overflow:parts.append(message.get('body',b''))
                if message.get('more_body',False):return
                if overflow:
                    return await JSONResponse({'detail':'Acota la consulta para reducir los resultados.'},status_code=413)(scope,receive,send)
                try:
                    payload=reader_payload(json.loads(b''.join(parts)))
                    if path.endswith('/pulse/config') and isinstance(payload,dict):payload['connector']={}
                    raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
                except (ValueError,UnicodeError):
                    return await JSONResponse({'detail':'No se pudo preparar la consulta.'},status_code=500)(scope,receive,send)
                head=dict(start);head['headers']=[(k,v) for k,v in start.get('headers',[]) if k.lower() not in {b'content-length',b'etag'}]+[(b'content-length',str(len(raw)).encode())]
                await send(head);await send(dict(type='http.response.body',body=raw,more_body=False))
            else:await send(message)
        token=READER_CONTEXT.set(True)
        try:await self.app(scope,receive,guarded_send)
        finally:READER_CONTEXT.reset(token)

def install_client_access(app,current_user):
    app.add_middleware(ClientReadOnly,sessions=app.state.SessionLocal,current_user=current_user)
