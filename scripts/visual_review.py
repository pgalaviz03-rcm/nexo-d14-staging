"""Private synthetic-only visual review on loopback. Never touches pilot data."""
import argparse,hashlib,json,os,secrets,sqlite3,subprocess,sys
from pathlib import Path
from datetime import datetime,timedelta,timezone

def prepare(code,source,private):
    private.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        account=(os.environ.get('USERDOMAIN','')+'\\'+os.environ['USERNAME']).lstrip('\\')
        r=subprocess.run(['icacls',str(private),'/inheritance:r','/grant:r',account+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],
            capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode:raise RuntimeError('No se pudo proteger la carpeta de prueba.')
    database=private/'visual.sqlite';uploads=private/'uploads';uploads.mkdir(exist_ok=True)
    key=private/'session.key'
    if not key.exists():key.write_text(secrets.token_urlsafe(48),encoding='ascii')
    os.environ.update(NEXO_ENV='local',NEXO_LOCAL_WORKSPACE='true',NEXO_VISUAL_REVIEW='true',NEXO_OFFLINE='true',
        NEXO_AI_ENABLED='false',NEXO_RSS_ALLOWED_HOSTS='',NEXO_STORAGE_MODE='database',NEXO_SECRET_KEY=key.read_text(encoding='ascii'),
        DATABASE_URL='sqlite:///'+database.as_posix(),NEXO_STORAGE_DIR=str(uploads),NEXO_RELEASE_APPROVED='false')
    for name in list(os.environ):
        if name.startswith(('OPENAI_','ANTHROPIC_','SUPABASE_','NEXO_SUPABASE_','APIFY_')):os.environ.pop(name,None)
    sys.path.insert(0,str(code))
    from app.main import create_app
    from app.models import User,Project,Membership
    from app.pulse_models import PulseConfig,PulseActor,PulseBatch,PulseDocument,PulseMention,PulseAccount,PulseRule
    from sqlalchemy import select
    app=create_app(os.environ['DATABASE_URL'],str(uploads))
    now=datetime.now(timezone.utc)
    with app.state.SessionLocal() as session:
        old=session.get(Project,1)
        if not old:
            # Reuse only local authentication hashes in this private folder.
            # No credentials, client files or original project rows enter outputs.
            with sqlite3.connect(Path(source).resolve(strict=True).as_uri()+'?mode=ro',uri=True) as original:
                users=original.execute('select id,email,password_hash from users where active=1').fetchall()
            if not users:raise RuntimeError('No hay una cuenta local para revisar la interfaz.')
            for uid,email,password_hash in users:session.add(User(id=uid,email=email,password_hash=password_hash,active=True))
            session.add(Project(id=1,slug='muestra-visual',name='Ciudad de ejemplo'));session.flush()
            for uid,_,_ in users:session.add(Membership(project_id=1,user_id=uid,role='viewer'))
            uid=users[0][0];session.add(PulseConfig(project_id=1,territory='Observatorio de muestra',min_classified=20))
            batch=PulseBatch(project_id=1,provider='synthetic_fixture',dataset_ref='visual-review-v1',sha256=hashlib.sha256(b'visual-review-v1').hexdigest(),is_demo=True,created_by=uid)
            session.add(batch);session.flush()
            titles=['Nuevos horarios para la atención en centros comunitarios','Vecinos reportan cambios en la frecuencia del transporte',
                'La agenda de servicios públicos concentra la conversación','Se presenta el calendario de actividades culturales',
                'Luminarias y mantenimiento: los temas más comentados','Apertura de espacios deportivos reúne comentarios positivos']
            for index,(name,pos,neg,neutral) in enumerate([('Ana Valdés',90,30,24),('Bruno Ríos',48,36,12),('Celia Mora',18,42,12),('Diego Solís',24,12,12)]):
                actor=PulseActor(project_id=1,name=name,kind='primary' if index==0 else 'comparator',is_demo=True,created_by=uid)
                session.add(actor);session.flush()
                for age,tones in [(0,['positive']*pos+['negative']*neg+['neutral']*neutral),
                                  (20,['positive']*20+['negative']*20+['neutral']*10)]:
                    for n,tone in enumerate(tones):
                        network=['facebook','press','instagram','x'][n%4]
                        document=PulseDocument(project_id=1,batch_id=batch.id,network=network,external_id=f'visual-{index}-{age}-{n}',
                            url=f'https://example.org/visual/{index}/{age}/{n}',title=titles[(index+n)%len(titles)],
                            text='Contenido completamente ficticio para revisar la presentación del observatorio.',
                            published_at=now-timedelta(days=age,minutes=20+n*7),collected_at=now,
                            interactions=80+n*11,is_demo=True)
                        session.add(document);session.flush()
                        emotion='joy' if tone=='positive' else ['anger','sadness','fear'][n%3] if tone=='negative' else 'surprise'
                        session.add(PulseMention(project_id=1,document_id=document.id,actor_id=actor.id,is_demo=True,sentiment=tone,
                            emotion=emotion,method='synthetic_fixture:visual-v1',version=1,reviewed_by=uid))
                for network,base in [('facebook',12840-index*1700),('instagram',7920-index*850)]:
                    for age,delta in [(8,-420),(0,0)]:
                        session.add(PulseAccount(project_id=1,actor_id=actor.id,network=network,url=f'https://example.org/visual-account/{index}/{network}',
                            captured_at=now-timedelta(days=age,minutes=15),metrics=json.dumps(dict(followers=base+delta,posts=62-index*7,
                                interactions=4380-index*400)),is_demo=True,created_by=uid))
                if index==0:
                    for name,metric,threshold in [('Aumento de conversación','mentions',100),('Atención a tono desfavorable','negative_share',20)]:
                        session.add(PulseRule(project_id=1,actor_id=actor.id,name=name,metric=metric,threshold=threshold,min_mentions=20,is_demo=True,created_by=uid))
            session.commit();(private/'fixture.json').write_text(json.dumps(dict(created_utc=now.isoformat(),synthetic=True)),encoding='utf-8')
        else:
            stamp=json.loads((private/'fixture.json').read_text())['created_utc'];shift=now-datetime.fromisoformat(stamp)
            for item in session.scalars(select(PulseDocument)).all():
                item.published_at=item.published_at.replace(tzinfo=timezone.utc)+shift;item.collected_at=now
            for item in session.scalars(select(PulseAccount)).all():item.captured_at=item.captured_at.replace(tzinfo=timezone.utc)+shift
            session.commit();(private/'fixture.json').write_text(json.dumps(dict(created_utc=now.isoformat(),synthetic=True)),encoding='utf-8')
    return app

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args();code=Path(__file__).resolve().parents[1]
    if args.directory.resolve().is_relative_to(code) or args.directory.resolve()==args.source.resolve().parent:
        raise ValueError('La prueba debe quedar separada del código y del piloto.')
    app=prepare(code,args.source,args.directory.resolve())
    if args.prepare_only:
        print(json.dumps(dict(prepared=True,synthetic=True,project_count=1,owner_grants=0,external_calls=0)))
        app.state.engine.dispose();return
    import uvicorn
    print('NEXO · PRUEBA VISUAL CON DATOS FICTICIOS',flush=True)
    print('Abre http://127.0.0.1:8003 y entra con tu cuenta LOCAL habitual.',flush=True)
    print('Esta copia muestra la experiencia de consulta. Ctrl+C la detiene.',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8003,access_log=False,log_level='warning')

if __name__=='__main__':main()
