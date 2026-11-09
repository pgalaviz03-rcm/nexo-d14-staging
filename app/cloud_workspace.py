"""Compose the validated workspace with the existing cloud identity gateway.
The core factory and protected main/knowledge sources remain unchanged.
"""
import os
from pathlib import Path
from fastapi import Depends,Header,Request,HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from .config import cloud
from .models import User,Project,Membership
from .pulse_models import PlatformGrant

def ensure_owner_memberships(session,user,commit=True):
 grant=session.get(PlatformGrant,user.id)
 if not grant or not grant.active:return
 projects=session.scalars(select(Project.id).where(Project.status=='active')).all()
 current=dict(session.execute(select(Membership.project_id,Membership.role).where(Membership.user_id==user.id)).all())
 missing=[pid for pid in projects if current.get(pid)!='admin']
 for pid in missing:
  stmt=insert(Membership).values(user_id=user.id,project_id=pid,role='admin')
  session.execute(stmt.on_conflict_do_update(index_elements=['project_id','user_id'],set_={'role':'admin'}))
 if missing and commit:session.commit()

def install(app):
 if not cloud() or app.state.engine.dialect.name!='postgresql':raise RuntimeError('Cloud entrypoint requires configured staging/production PostgreSQL.')
 route=next(r for r in app.routes if getattr(r,'path',None)=='/api/projects' and 'GET' in r.methods)
 deps={d.name:d.call for d in route.dependant.dependencies}
 if set(deps)!={'user','session'} or deps['user'].__name__!='current_user' or deps['session'].__name__!='db':
  raise RuntimeError('Core authentication dependency contract changed.')
 db=deps['session'];core_current_user=deps['user']
 def current_user(request:Request,authorization:str|None=Header(default=None),session:Session=Depends(db)):
  user=core_current_user(request=request,authorization=authorization,session=session)
  ensure_owner_memberships(session,user)
  return user
 def allow(pid,user,session,roles=None):
  member=session.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==user.id));project=session.get(Project,pid)
  if not project or project.status!='active' or not member:raise HTTPException(404,'Proyecto no disponible')
  if roles and member.role not in roles:raise HTTPException(403,'Permiso insuficiente')
  return project,member
 from .workspace_api import install_workspace_api
 from .review_api import install_review_api
 uploads=Path(os.getenv('NEXO_STORAGE_DIR','/app/storage/uploads')).resolve()
 install_workspace_api(app,db,current_user,allow,uploads)
 install_review_api(app,db,current_user,allow)
 return app
