"""Administración local de proyectos. Usar solo desde computadora de confianza."""
import argparse,os,secrets
from pathlib import Path
from sqlalchemy import select
from app.models import User,Project,Membership,Base
from app.database import create_database
from app.security import make_hash
root=Path(__file__).resolve().parent
os.chdir(root)
os.environ.setdefault('DATABASE_URL','sqlite:///./storage/nexo.db')
p=argparse.ArgumentParser()
s=p.add_subparsers(dest='cmd',required=True)
a=s.add_parser('usuario');a.add_argument('email');a.add_argument('--clave')
a=s.add_parser('proyecto');a.add_argument('slug');a.add_argument('nombre')
a=s.add_parser('permiso');a.add_argument('email');a.add_argument('slug');a.add_argument('rol',choices=['admin','analyst','editor','viewer'])
a=s.add_parser('listar')
args=p.parse_args()
engine,Local=create_database()
Base.metadata.create_all(engine)
with Local() as db:
 if args.cmd=='usuario':
    if db.scalar(select(User).where(User.email==args.email.lower())):raise SystemExit('Usuario existente')
    pw=args.clave or secrets.token_urlsafe(18)
    if len(pw)<12:raise SystemExit('Clave mínima: 12 caracteres')
    db.add(User(email=args.email.lower(),password_hash=make_hash(pw)))
    print('Usuario creado:',args.email.lower(),'\nContraseña:',pw)
 if args.cmd=='proyecto':
    if db.scalar(select(Project).where(Project.slug==args.slug)):raise SystemExit('Proyecto existente')
    db.add(Project(slug=args.slug,name=args.nombre));print('Proyecto creado:',args.slug)
 if args.cmd=='permiso':
    user=db.scalar(select(User).where(User.email==args.email.lower()))
    project=db.scalar(select(Project).where(Project.slug==args.slug))
    if not user or not project:raise SystemExit('Usuario/proyecto no encontrado')
    membership=db.scalar(select(Membership).where(Membership.user_id==user.id,Membership.project_id==project.id))
    if membership:membership.role=args.rol
    else:db.add(Membership(user_id=user.id,project_id=project.id,role=args.rol))
    print('Permiso asignado:',args.email,args.slug,args.rol)
 if args.cmd=='listar':
    for project in db.scalars(select(Project)).all():
        print('Proyecto:',project.id,project.slug,project.name)
        for mem in db.scalars(select(Membership).where(Membership.project_id==project.id)).all():
            user=db.get(User,mem.user_id)
            print(' -',user.email,mem.role)
 db.commit()
