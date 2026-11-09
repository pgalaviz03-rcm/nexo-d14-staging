"""Explicit local owner control plane with audited all-project memberships."""
from fastapi import Depends,HTTPException
from pydantic import Field,SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Literal
from uuid import UUID
from .apify_port import Strict
from .models import User,Project,Membership,AuditEvent
from .pulse_models import PlatformGrant,PulseConfig,PlatformBrand
from .platform_access import bind_projects
from .config import cloud


class ProjectInput(Strict):
    name:str=Field(min_length=2,max_length=160)
    slug:str=Field(min_length=2,max_length=100,pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    territory:str=Field(default='',max_length=160)
    owner_user_id:int|None=Field(default=None,ge=1)


class MemberInput(Strict):
    user_id:int=Field(ge=1)
    role:Literal['admin','editor','analyst','viewer']


class UserInput(Strict):
    email:str=Field(max_length=255,pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    password:SecretStr|None=Field(default=None,min_length=12,max_length=128)
    auth_subject:str|None=Field(default=None,max_length=36)


class UserState(Strict):active:bool


class BrandInput(Strict):
    name:str=Field(min_length=2,max_length=60)
    tagline:str=Field(default='',max_length=160)


def install_platform_api(app,db,current_user):
    def guard(user,session):
        grant=session.get(PlatformGrant,user.id)
        if not grant or not grant.active:raise HTTPException(403,'Se requiere acceso de administración de plataforma.')
        if cloud() and session.bind.dialect.name!='postgresql':raise HTTPException(409,'La nube requiere PostgreSQL.')

    @app.get('/api/platform/session')
    def platform_session(user=Depends(current_user),session:Session=Depends(db)):
        grant=session.get(PlatformGrant,user.id)
        import os
        return dict(is_superadmin=bool(grant and grant.active),client_read_only=not bool(grant and grant.active),
                    visual_review=os.getenv('NEXO_VISUAL_REVIEW')=='true',environment=os.getenv('NEXO_ENV','local'),auth_mode='supabase' if cloud() else 'local',scope='Administración y consulta por proyecto.')

    @app.get('/api/branding')
    def branding(session:Session=Depends(db)):
        row=session.get(PlatformBrand,1)
        return dict(name=row.name if row else 'NEXO',tagline=row.tagline if row else 'Contexto para entender')

    @app.put('/api/platform/branding')
    def set_brand(body:BrandInput,user=Depends(current_user),session:Session=Depends(db)):
        guard(user,session)
        if cloud():raise HTTPException(405,'La identidad de la plataforma se publica con su diseño.')
        name=' '.join(body.name.split())
        if len(name)<2 or any(ord(c)<32 for c in name+body.tagline):raise HTTPException(422,'Revisa el nombre o lema de la marca.')
        row=session.get(PlatformBrand,1)
        if not row:row=PlatformBrand(id=1,name=name,tagline=body.tagline);session.add(row)
        else:row.name=name;row.tagline=body.tagline
        session.add(AuditEvent(project_id=None,user_id=user.id,action='platform.brand',target='identity'))
        session.commit();return dict(name=name,tagline=body.tagline)

    @app.get('/api/platform/projects')
    def projects(user=Depends(current_user),session:Session=Depends(db)):
        guard(user,session)
        rows=session.scalars(select(Project).order_by(Project.id).limit(100)).all()
        return [dict(id=p.id,name=p.name,slug=p.slug,status=p.status) for p in rows]

    @app.get('/api/platform/users')
    def users(user=Depends(current_user),session:Session=Depends(db)):
        guard(user,session)
        return [dict(id=u.id,email=u.email,active=u.active) for u in session.scalars(select(User).order_by(User.id).limit(100)).all()]

    @app.post('/api/platform/users')
    def create_user(body:UserInput,user=Depends(current_user),session:Session=Depends(db)):
        guard(user,session)
        from .security import make_hash
        if cloud():
            if body.password is not None:raise HTTPException(422,'Las contraseñas de nube se administran en Supabase.')
            try:subject=str(UUID(body.auth_subject or ''))
            except ValueError:raise HTTPException(422,'Indica el ID de la cuenta creada en Supabase.') from None
            item=User(email=body.email.strip().lower(),auth_subject=subject,password_hash='external-auth-only',active=True)
        else:
            if body.password is None or body.auth_subject is not None:raise HTTPException(422,'La cuenta local necesita una contraseña exclusiva.')
            item=User(email=body.email.strip().lower(),password_hash=make_hash(body.password.get_secret_value()),active=True)
        try:
            session.add(item);session.flush()
            session.add(AuditEvent(project_id=None,user_id=user.id,action='platform.user.create',target=str(item.id)))
            session.commit();return dict(id=item.id,email=item.email)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'La cuenta ya existe.') from None

    @app.patch('/api/platform/users/{user_id}')
    def user_state(user_id:int,body:UserState,user=Depends(current_user),session:Session=Depends(db)):
        guard(user,session)
        if user_id==user.id and not body.active:raise HTTPException(422,'No desactives tu propia cuenta desde esta sesión.')
        target=session.get(User,user_id)
        if target is None:raise HTTPException(404,'Cuenta no disponible.')
        target.active=body.active
        session.add(AuditEvent(project_id=None,user_id=user.id,action='platform.user.state',target=f'{user_id}:{body.active}'))
        session.commit();return dict(id=user_id,active=body.active)

    @app.post('/api/platform/projects')
    def create_project(body:ProjectInput,user=Depends(current_user),session:Session=Depends(db)):
        guard(user,session)
        owner=session.get(User,body.owner_user_id or user.id)
        if not owner or not owner.active:raise HTTPException(422,'La cuenta responsable no está disponible.')
        name=' '.join(body.name.split())
        if len(name)<2:raise HTTPException(422,'Indica un nombre de proyecto.')
        try:
            item=Project(name=name,slug=body.slug,status='active');session.add(item);session.flush()
            session.add(Membership(user_id=owner.id,project_id=item.id,role='admin'))
            session.flush()
            if cloud():
                from .cloud_workspace import ensure_owner_memberships
                ensure_owner_memberships(session,user,commit=False)
            else:
                for grant in session.scalars(select(PlatformGrant).where(PlatformGrant.active.is_(True))).all():bind_projects(session,grant,[item])
            session.add(PulseConfig(project_id=item.id,territory=body.territory.strip(),min_classified=20,connector='{}',version=1))
            session.add(AuditEvent(project_id=item.id,user_id=user.id,action='platform.project.create',target=str(item.id)))
            session.commit();return dict(id=item.id,name=item.name,slug=item.slug)
        except IntegrityError:
            session.rollback();raise HTTPException(409,'El identificador del proyecto ya existe.') from None

    @app.get('/api/platform/projects/{pid}/members')
    def members(pid:int,user=Depends(current_user),session:Session=Depends(db)):
        guard(user,session)
        return [dict(user_id=m.user_id,role=m.role) for m in session.scalars(select(Membership).where(Membership.project_id==pid)).all()]

    @app.put('/api/platform/projects/{pid}/members')
    def member(pid:int,body:MemberInput,user=Depends(current_user),session:Session=Depends(db)):
        guard(user,session)
        project=session.get(Project,pid);target=session.get(User,body.user_id)
        if not project or not target or not target.active:raise HTTPException(404,'Proyecto o cuenta no disponible.')
        grant=session.get(PlatformGrant,body.user_id)
        if grant and grant.active and body.role!='admin':raise HTTPException(409,'Una cuenta de plataforma mantiene acceso completo. Su revocación se realiza mediante el procedimiento local de propietario.')
        row=session.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==body.user_id))
        if row:row.role=body.role
        else:session.add(Membership(project_id=pid,user_id=body.user_id,role=body.role))
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='platform.member',target=f'{body.user_id}:{body.role}'))
        session.commit();return dict(project_id=pid,user_id=body.user_id,role=body.role)
