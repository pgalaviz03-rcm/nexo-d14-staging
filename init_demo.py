"""Crear proyecto y usuario de prueba de NEXO. Ejecutar una sola vez con el servidor detenido."""
import os,re,json,sys,secrets,argparse
from pathlib import Path
from sqlalchemy import select
from app.database import create_database
from app.models import Base,User,Project,Membership,SectionMetric,AuditEvent
from app.security import make_hash
if os.getenv('NEXO_ENV','local')!='local':
    raise SystemExit('Usa scripts/bootstrap_cloud.py; no crear usuarios demo en la nube')

p=argparse.ArgumentParser()
p.add_argument('--email',default='admin@nexo.local')
p.add_argument('--password',default=None,help='Si se omite se genera una contraseña aleatoria')
a=p.parse_args()
Path('storage').mkdir(exist_ok=True)
engine,SessionLocal=create_database()
Base.metadata.create_all(engine)
with SessionLocal() as s:
    email=a.email.lower().strip()
    user=s.scalar(select(User).where(User.email==email))
    if user:print('Usuario ya existe; no se modifica su contraseña.')
    else:
        pw=a.password or secrets.token_urlsafe(18)
        if len(pw)<12:raise SystemExit('La contraseña debe tener 12 caracteres como mínimo')
        user=User(email=email,password_hash=make_hash(pw));s.add(user);s.flush()
        print('USUARIO CREADO:',email,'\nCONTRASEÑA TEMPORAL:',pw)
    proj=s.scalar(select(Project).where(Project.slug=='d14'))
    if not proj:
        proj=Project(name='Distrito 14 · Aguascalientes',slug='d14');s.add(proj);s.flush()
    membership=s.scalar(select(Membership).where(Membership.user_id==user.id,Membership.project_id==proj.id))
    if not membership:s.add(Membership(user_id=user.id,project_id=proj.id,role='admin'))
    data=json.loads((Path(__file__).resolve().parent/'data'/'secciones_2024.json').read_text(encoding='utf-8'))
    added=0
    for k,v in data.items():
        previous=s.scalar(select(SectionMetric).where(SectionMetric.project_id==proj.id,SectionMetric.section==int(k),SectionMetric.election_year==2024))
        if previous:continue
        s.add(SectionMetric(project_id=proj.id,section=int(k),election_year=2024,nominal_list=v['ln'],territorial_votes=v['votes'],polling_places=v['boxes'],null_votes=v['nulls'],source='Cómputo oficial diputación local D14, 6 junio 2024; LN: base PREP'))
        added+=1
    s.add(AuditEvent(project_id=proj.id,user_id=user.id,action='seed.historical',target=f'{added} sections'))
    s.commit()
print(f'Distrito 14 listo. {added} secciones añadidas (de {len(data)}).')
print('Inicia servidor: uvicorn app.main:app --host 127.0.0.1 --port 8000')
