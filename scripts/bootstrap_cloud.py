"""Explicit identity binding with migration credentials. Never print passwords."""
import sys, os, argparse, json
from pathlib import Path
from uuid import UUID
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.database import create_database
from app.models import User, Project, Membership, SectionMetric, AuditEvent

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--subject',required=True,type=UUID)
    p.add_argument('--email',required=True)
    p.add_argument('--role',choices=['admin','editor','analyst','viewer'],default='admin')
    a=p.parse_args()
    engine,Session=create_database(os.environ['NEXO_MIGRATION_DATABASE_URL'])
    data=json.loads((Path(__file__).resolve().parents[1]/'data/secciones_2024.json').read_text(encoding='utf-8'))
    with Session() as s:
        u=s.scalar(select(User).where(User.email==a.email.strip().lower()))
        if u and u.auth_subject not in (None,str(a.subject)):
            raise SystemExit('La cuenta ya está vinculada a otra identidad')
        if not u:
            u=User(email=a.email.strip().lower(),password_hash='IDP_ONLY',auth_subject=str(a.subject))
            s.add(u);s.flush()
        u.auth_subject=str(a.subject)
        project=s.scalar(select(Project).where(Project.slug=='d14'))
        if not project:
            project=Project(slug='d14',name='Distrito 14 · Aguascalientes');s.add(project);s.flush()
        mem=s.scalar(select(Membership).where(Membership.user_id==u.id,Membership.project_id==project.id))
        if mem: mem.role=a.role
        else:s.add(Membership(user_id=u.id,project_id=project.id,role=a.role))
        added=0
        for section,v in data.items():
            old=s.scalar(select(SectionMetric).where(SectionMetric.project_id==project.id,
                SectionMetric.section==int(section),SectionMetric.election_year==2024))
            fields=dict(nominal_list=v['ln'],territorial_votes=v['votes'],polling_places=v['boxes'],null_votes=v['nulls'])
            if old:
                if any(getattr(old,k)!=val for k,val in fields.items()):raise SystemExit('Conflicto histórico: revisar antes de continuar')
            else:
                s.add(SectionMetric(project_id=project.id,section=int(section),election_year=2024,
                    source='Histórico conservado del paquete NEXO v0.4 D14 2024',**fields));added+=1
        s.add(AuditEvent(project_id=project.id,user_id=u.id,action='identity.bind',target='explicit-idp-mapping'))
        s.commit()
    print(f'Identidad vinculada. Secciones históricas añadidas: {added}. Sin contraseñas locales.')

if __name__=='__main__':main()
