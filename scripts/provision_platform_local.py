"""Owner-operated local provisioning. No HTTP endpoint can grant this access."""
import argparse,os,sys
from pathlib import Path
from sqlalchemy import select
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import create_database
from app.models import User,AuditEvent
from app.pulse_models import PlatformGrant
from app.platform_access import bind_projects,unbind_projects


def main():
    p=argparse.ArgumentParser();p.add_argument('--database',type=Path,required=True);p.add_argument('--email',required=True)
    p.add_argument('--grant',action='store_true');p.add_argument('--revoke',action='store_true');args=p.parse_args()
    if args.grant==args.revoke:p.error('Elige explícitamente grant o revoke.')
    if os.getenv('NEXO_ENV','local')!='local':p.error('Solo se admite desarrollo local.')
    database=args.database.resolve(strict=True)
    if database.suffix not in {'.db','.sqlite'}:p.error('Se requiere el archivo SQLite local.')
    engine,Session=create_database('sqlite:///'+database.as_posix())
    try:
        with Session() as s:
            user=s.scalar(select(User).where(User.email==args.email.strip().lower(),User.active.is_(True)))
            if not user:raise RuntimeError('No se encontró la cuenta local activa solicitada.')
            row=s.get(PlatformGrant,user.id)
            if not row:row=PlatformGrant(user_id=user.id,active=args.grant);s.add(row)
            else:row.active=args.grant
            s.flush()
            if args.grant:bind_projects(s,row)
            else:unbind_projects(s,row)
            s.add(AuditEvent(project_id=None,user_id=user.id,action='platform.provision',target='grant' if args.grant else 'revoke'))
            s.commit()
        print('Permiso de plataforma local y membresías auditadas actualizados.')
    finally:engine.dispose()


if __name__=='__main__':main()
