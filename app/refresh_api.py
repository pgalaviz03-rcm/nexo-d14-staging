"""Owner manual refresh and signed daily scheduler, with project read-only status."""
from fastapi import Depends,BackgroundTasks,Header,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import User,Project
from .client_access import is_owner
from .refresh_service import status,admit,execute_run,available
from .refresh_oidc import verify_scheduler

def install_refresh_api(app,db,current_user,allow):
 sessions=app.state.SessionLocal
 feed=next(r.endpoint for r in app.routes if getattr(r,'path',None)=='/api/projects/{pid}/feeds/{fid}/sync'and'POST'in r.methods)
 @app.get('/api/projects/{pid}/refresh')
 def refresh_status(pid:int,user=Depends(current_user),session:Session=Depends(db)):
  allow(pid,user,session);return status(session,pid,can_refresh=is_owner(session,user))
 @app.post('/api/projects/{pid}/refresh',status_code=202)
 def refresh_now(pid:int,background:BackgroundTasks,user=Depends(current_user),session:Session=Depends(db)):
  allow(pid,user,session)
  if not is_owner(session,user):raise HTTPException(403,'Actualización exclusiva del superadministrador.')
  row,new=admit(session,pid,user)
  if row and row.status=='queued':background.add_task(execute_run,sessions,row.id,row.requested_by,feed)
  return dict(accepted=bool(row),run_id=row.id if row else None,status=row.status if row else None,created=new)
 @app.post('/internal/daily-refresh',status_code=202)
 def daily_refresh(background:BackgroundTasks,authorization:str|None=Header(default=None)):
  uid=verify_scheduler(authorization)
  with sessions()as s:
   s.info['nexo.actor_id']=str(uid);user=s.get(User,uid)
   if not user or not is_owner(s,user):raise HTTPException(403,'Operador de actualización no autorizado.')
   if not available(s):raise HTTPException(409,'Actualización temporalmente no disponible.')
   if s.bind.dialect.name=='postgresql':
    from .cloud_workspace import ensure_owner_memberships
    ensure_owner_memberships(s,user)
   projects=s.scalars(select(Project.id).where(Project.status=='active').order_by(Project.id).limit(101)).all()
   if len(projects)>100:raise HTTPException(409,'El programador requiere dividir los proyectos en lotes.')
   accepted=0
   for pid in projects:
    row,new=admit(s,pid,user,trigger='daily')
    if row and row.status=='queued':background.add_task(execute_run,sessions,row.id,row.requested_by,feed);accepted+=1
  return dict(accepted=accepted,daily_time='08:00',timezone='America/Mexico_City')
