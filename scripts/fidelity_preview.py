"""Disposable synthetic Fidelidad review. Human launcher, loopback only."""
import argparse,json,os,secrets,sqlite3,subprocess,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo

def prepare(source,private):
    code=Path(__file__).resolve().parents[1];private.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        account=(os.environ.get('USERDOMAIN','')+'\\'+os.environ['USERNAME']).lstrip('\\')
        p=subprocess.run(['icacls',str(private),'/inheritance:r','/grant:r',account+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],
            capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        if p.returncode:raise RuntimeError('No se pudo proteger la carpeta privada.')
    db=private/'fidelity-review.sqlite';uploads=private/'uploads';uploads.mkdir(exist_ok=True);key=private/'session.key'
    if not key.exists():key.write_text(secrets.token_urlsafe(48),encoding='ascii')
    os.environ.update(NEXO_ENV='local',NEXO_LOCAL_WORKSPACE='true',NEXO_OFFLINE='true',NEXO_VISUAL_REVIEW='false',
        NEXO_AI_ENABLED='false',NEXO_RSS_ALLOWED_HOSTS='',NEXO_SECRET_KEY=key.read_text(encoding='ascii'),
        DATABASE_URL='sqlite:///'+db.as_posix(),NEXO_STORAGE_DIR=str(uploads),NEXO_STORAGE_MODE='database',NEXO_RELEASE_APPROVED='false')
    for k in list(os.environ):
        if k.startswith(('APIFY_','OPENAI_','ANTHROPIC_','SUPABASE_','NEXO_SUPABASE_')):os.environ.pop(k,None)
    sys.path.insert(0,str(code))
    from app.main import create_app
    from app.models import User,Project,Membership
    from app.pulse_models import PulseActor,PlatformGrant
    from app.actor_models import ActorProfile
    from app.fidelity import FidelityCapture,AtalayaPublicationBatch,fingerprint
    from app.continuity_models import AudienceSnapshot
    from app.fidelity_team import TeamMember,TeamObservation
    from sqlalchemy import select,delete
    app=create_app(os.environ['DATABASE_URL'],str(uploads));now=datetime.now(timezone.utc);end=now.astimezone(ZoneInfo('America/Mexico_City')).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    with app.state.SessionLocal() as s:
        project=s.get(Project,1)
        if not project:
            with sqlite3.connect(source.resolve(strict=True).as_uri()+'?mode=ro',uri=True) as original:
                users=original.execute('select id,email,password_hash from users where active=1').fetchall()
            if not users:raise RuntimeError('No hay cuentas locales activas.')
            for uid,email,password_hash in users:s.add(User(id=uid,email=email,password_hash=password_hash,active=True))
            s.add(Project(id=1,name='Revisión de Fidelidad · datos ficticios',slug='fidelity-review'));s.flush()
            for uid,_,_ in users:s.add(Membership(project_id=1,user_id=uid,role='viewer'))
            uid=users[0][0];s.add(PulseActor(id=1,project_id=1,name='Cuenta de muestra',kind='primary',active=True,is_demo=False,created_by=uid));s.flush()
            refs=[dict(network=n,url=u,enabled=True) for n,u in [('facebook','https://facebook.com/nexo.cuenta.de.ejemplo'),('instagram','https://instagram.com/nexo.cuenta.de.ejemplo')]]
            s.add(ActorProfile(actor_id=1,project_id=1,is_demo=False,channels_json=json.dumps(refs),updated_by=uid));s.commit()
        if s.get(Project,1).slug!='fidelity-review' or s.scalar(select(PlatformGrant)) is not None:raise RuntimeError('La base no es la muestra aislada de consulta.')
        uid=s.scalar(select(User.id).where(User.active.is_(True)));refs=json.loads(s.get(ActorProfile,1).channels_json)
        # Only this explicitly disposable review project is refreshed.
        s.execute(delete(TeamObservation).where(TeamObservation.project_id==1));s.execute(delete(TeamMember).where(TeamMember.project_id==1))
        s.execute(delete(FidelityCapture).where(FidelityCapture.project_id==1));s.execute(delete(AudienceSnapshot).where(AudienceSnapshot.project_id==1))
        examples=[]
        team=[]
        for i,label in enumerate(['Colaborador de muestra A','Colaboradora de muestra B','Colaborador de muestra C']):
            m=TeamMember(project_id=1,external_key='synthetic-'+str(i),display_name=label,
                profiles_json=json.dumps(dict(facebook='nexo.equipo.ejemplo.'+str(i),instagram='nexo.equipo.ejemplo.'+str(i))),
                active=True,source_sha256='0'*64,updated_by=uid)
            s.add(m);s.flush();team.append(m)
        topics=['Abrimos nuevos horarios en la biblioteca comunitaria','Jornada de mantenimiento en espacios públicos','Agenda cultural del fin de semana',
                'Información sobre rutas de transporte','Encuentro abierto sobre servicios de la ciudad','Actividades para recuperar espacios deportivos']
        for index,ref in enumerate(refs):
            publications=[dict(url=ref['url']+('/posts/' if ref['network']=='facebook' else '/p/')+str(i+1),
                published_at=now-timedelta(hours=8+i*11),text=topics[i%len(topics)],reactions=30+i*3,comments=7+i,
                shares=(2+i%3) if ref['network']=='facebook' else None,followers=3980+index*2200) for i in range(18)]
            body=AtalayaPublicationBatch(actor_id=1,network=ref['network'],account_url=ref['url'],captured_at=now,publications=publications);raw,digest=fingerprint(body)
            s.add(FidelityCapture(project_id=1,actor_id=1,is_demo=False,network=ref['network'],account_url=ref['url'],captured_at=now,
                payload_json=raw,sha256=digest,source_kind='synthetic',created_by=uid))
            for back,n,r,old in [(0,1200,720,1500),(1,1500,750,1600)]:
                period_to=end-timedelta(days=7*back);period_from=period_to-timedelta(days=7)
                s.add(AudienceSnapshot(project_id=1,actor_id=1,is_demo=False,network=ref['network'],url=ref['url'],provider='manual',
                    measurement_id='synthetic-review-v1',contract_version='participating-accounts-v1',period_from=period_from,period_to=period_to,
                    reference_from=period_from-timedelta(days=7),reference_to=period_from,captured_at=now,
                    participants=n,returning=r,reference_participants=old,created_by=uid))
            for member_index,m in enumerate(team):
                for post_index,pub in enumerate(publications[:max(2,10-member_index*3)]):
                    for kind in (['reaction','comment_presence'] if post_index%3==0 else ['reaction']):
                        s.add(TeamObservation(project_id=1,member_id=m.id,actor_id=1,is_demo=False,network=ref['network'],post_url=pub['url'],
                            kind=kind,source_key='',observed_at=now,source_kind='synthetic'))
            examples.extend([dict(url=p['url'],red=ref['network'],cuenta=ref['url'],fecha=p['published_at'].isoformat(),texto=p['text'],
                reacciones=p['reactions'],comentarios=p['comments'],compartidos=p['shares'],seguidores=p['followers']) for p in publications])
        s.commit();(private/'example-publications.json').write_text(json.dumps(dict(actualizado=now.isoformat(),publicaciones=examples),ensure_ascii=False,indent=2),encoding='utf-8')
    return app

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--directory',type=Path,required=True);p.add_argument('--prepare-only',action='store_true');args=p.parse_args()
    if args.directory.resolve()==args.source.resolve().parent or args.directory.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('La muestra debe estar separada del piloto y del código.')
    app=prepare(args.source,args.directory.resolve())
    if args.prepare_only:
        app.state.engine.dispose();print(json.dumps(dict(prepared=True,synthetic=True,external_calls=0)));return
    import uvicorn
    print('NEXO · FIDELIDAD DE PRUEBA: http://127.0.0.1:8004',flush=True)
    print('Entra con tu cuenta LOCAL habitual y abre Fidelidad. Esta copia es de consulta y tiene datos ficticios.',flush=True)
    print('No se conectan APIs. Ctrl+C detiene la muestra.',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8004,access_log=False,log_level='warning')
if __name__=='__main__':main()
