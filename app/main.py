import os,re,csv,io,hashlib,json,uuid,zipfile
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI,Depends,HTTPException,UploadFile,File,Header,Request,Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from defusedxml import ElementTree as SafeET
from .models import Base,User,Project,Membership,Dataset,SectionMetric,AuditEvent,DatasetBlob
from .rss_api import install_rss_api
from .database import create_database
from .security import sign,unsign,verify
from .config import cloud
from .cloud_auth import install_auth,decode_token,COOKIE
from .controls import Guard,take_quota
from contextlib import asynccontextmanager
from sqlalchemy import text

MAX_UPLOAD=12*1024*1024
ACCEPTED={'.csv','.kml','.geojson','.json','.xlsx','.pdf'}

class Login(BaseModel):
    email:str
    password:str


def create_app(db_url=None,storage_dir=None):
    engine,SessionLocal=create_database(db_url)
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)  # piloto local; PostgreSQL usa Alembic
    root=Path(__file__).resolve().parent.parent
    uploads=Path(storage_dir or os.getenv('NEXO_STORAGE_DIR',str(root/'storage'/'uploads'))).resolve()
    uploads.mkdir(parents=True,exist_ok=True)
    @asynccontextmanager
    async def lifespan(app):
        if cloud():
            from .preflight import check_database
            check_database(engine)
        yield
        engine.dispose()
    app=FastAPI(title='NEXO API',version='0.5',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.engine=engine
    app.state.SessionLocal=SessionLocal

    def db():
        with SessionLocal() as s:yield s

    def current_user(request:Request,authorization:str|None=Header(default=None),session:Session=Depends(db)):
        token=request.cookies.get(COOKIE) if cloud() else None
        if not token and authorization and authorization.startswith('Bearer '): token=authorization[7:]
        if not token:raise HTTPException(401,'Sesión requerida')
        if cloud():
            subject=decode_token(token)['sub']
            session.info['nexo.auth_subject']=subject
            user=session.scalar(select(User).where(User.auth_subject==subject))
        else:
            uid=unsign(token)
            session.info['nexo.actor_id']=str(uid or '')
            user=session.get(User,uid) if uid else None
        if not user or not user.active:raise HTTPException(401,'Sesión inválida')
        session.info['nexo.actor_id']=str(user.id)
        if session.bind.dialect.name == 'postgresql':
            session.execute(text("SELECT set_config('nexo.actor_id', :user_id, true)"), {'user_id':str(user.id)})
        return user

    def allow(pid:int,user:User,session:Session,roles=None):
        membership=session.scalar(select(Membership).where(Membership.project_id==pid,Membership.user_id==user.id))
        project=session.get(Project,pid)
        if not project or project.status!='active' or not membership:raise HTTPException(404,'Proyecto no disponible')
        if roles and membership.role not in roles:raise HTTPException(403,'Permiso insuficiente')
        return project,membership

    @app.get('/api/health')
    def health():return {'status':'ok','version':'0.5'}

    @app.get('/api/ready')
    def ready(session:Session=Depends(db)):
        try:
            session.execute(text('SELECT 1'))
            return {'status':'ready','version':'0.5'}
        except Exception:
            raise HTTPException(503,'Base de datos no disponible')

    @app.post('/api/auth/login')
    def login(data:Login,response:Response,session:Session=Depends(db)):
        if len(data.email)>255 or len(data.password)>1024:raise HTTPException(422,'Credenciales inválidas')
        if cloud():
            from .cloud_auth import login as cloud_login
            return cloud_login(data.email.strip().lower(),data.password,response)
        user=session.scalar(select(User).where(User.email==data.email.strip().lower()))
        if not user or not user.active or not verify(data.password,user.password_hash):raise HTTPException(401,'Credenciales incorrectas')
        return {'token':sign(user.id),'user':{'email':user.email}}

    @app.get('/api/projects')
    def projects(user:User=Depends(current_user),session:Session=Depends(db)):
        rows=session.execute(select(Project,Membership.role).join(Membership,Membership.project_id==Project.id).where(Membership.user_id==user.id,Project.status=='active')).all()
        return [{'id':p.id,'slug':p.slug,'name':p.name,'role':role} for p,role in rows]

    @app.get('/api/projects/{pid}/summary')
    def summary(pid:int,user:User=Depends(current_user),session:Session=Depends(db)):
        project,_=allow(pid,user,session)
        data=session.execute(select(SectionMetric).where(SectionMetric.project_id==pid,SectionMetric.election_year==2024)).scalars().all()
        ds_count=session.scalar(select(func.count(Dataset.id)).where(Dataset.project_id==pid))
        historical=json.loads((root/'data'/'secciones_2024.json').read_text(encoding='utf-8'))
        snapshot={str(x.section):{'ln':x.nominal_list,'votes':x.territorial_votes,'boxes':x.polling_places,'nulls':x.null_votes} for x in data}
        expected={k:{field:v[field] for field in ('ln','votes','boxes','nulls')} for k,v in historical.items()}
        complete=project.slug=='d14' and snapshot==expected
        return {'project':project.name,'sections':len(data),'nominal_list':sum(x.nominal_list for x in data),'territorial_votes':sum(x.territorial_votes for x in data),'official_votes':sum(x.territorial_votes for x in data)+8 if complete else None,'year':2024,'datasets':ds_count,'note':'Histórico del paquete D14 2024. Las 8 boletas anticipadas solo se agregan si las 45 secciones coinciden con la base conservada; no se georreferencian.'}

    @app.get('/api/projects/{pid}/sections')
    def sections(pid:int,user:User=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        data=session.scalars(select(SectionMetric).where(SectionMetric.project_id==pid).order_by(SectionMetric.section)).all()
        return [{'id':x.section,'ln':x.nominal_list,'votes':x.territorial_votes,'rate':round(100*x.territorial_votes/x.nominal_list,2) if x.nominal_list else 0,'boxes':x.polling_places,'nulls':x.null_votes,'year':x.election_year,'source':x.source} for x in data]

    @app.get('/api/projects/{pid}/datasets')
    def datasets(pid:int,user:User=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        ds=session.scalars(select(Dataset).where(Dataset.project_id==pid).order_by(Dataset.id.desc())).all()
        return [{'id':x.id,'filename':x.filename,'status':x.status,'size_bytes':x.size_bytes,'sha256':x.sha256,'record_count':x.record_count,'detail':x.detail,'created_at':x.created_at.isoformat()} for x in ds]

    @app.get('/api/projects/{pid}/sections/export')
    def export_sections(pid:int,user:User=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        take_quota(session,pid,'sections.export',20)
        rows=session.scalars(select(SectionMetric).where(SectionMetric.project_id==pid).order_by(SectionMetric.section)).all()
        output=io.StringIO();writer=csv.writer(output)
        writer.writerow(['Seccion','Anio','Lista nominal','Votos territoriales','Casillas','Nulos'])
        writer.writerows([x.section,x.election_year,x.nominal_list,x.territorial_votes,x.polling_places,x.null_votes] for x in rows)
        session.add(AuditEvent(project_id=pid,user_id=user.id,action='sections.export',target=str(len(rows))));session.commit()
        return Response(content='\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="NEXO_Secciones_Historicas.csv"'})

    @app.post('/api/projects/{pid}/datasets')
    async def import_dataset(pid:int,file:UploadFile=File(...),user:User=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session,roles={'admin','editor','analyst'})
        take_quota(session,pid,'dataset.upload',20)
        name=Path(file.filename or '').name
        ext=Path(name).suffix.lower()
        if ext not in ACCEPTED or not name or len(name)>240:raise HTTPException(400,'Extensión o nombre no permitido')
        raw=await file.read(MAX_UPLOAD+1)
        if len(raw)>MAX_UPLOAD:raise HTTPException(413,'Archivo demasiado grande (máximo 12 MB)')
        if not raw:raise HTTPException(400,'Archivo vacío')
        used=session.scalar(select(func.coalesce(func.sum(Dataset.size_bytes),0)).where(Dataset.project_id==pid))
        if used+len(raw)>250*1024*1024:raise HTTPException(429,'Almacenamiento del proyecto: máximo 250 MB')
        status='staged';count=0;detail='Guardado para revisión y vinculación de esquema.'
        try:
            if ext=='.csv':
                decoded=raw.decode('utf-8-sig')
                records=list(csv.reader(io.StringIO(decoded)))
                if not records or len(records[0])>200:raise ValueError('CSV sin encabezados válidos')
                count=max(len(records)-1,0)
                if count>300000:raise ValueError('Exceso de registros')
                status='validated';detail='CSV tabular validado; no sobrescribe datos oficiales.'
            elif ext=='.kml':
                xml=SafeET.fromstring(raw)
                count=sum(1 for element in xml.iter() if element.tag.endswith('Placemark'))
                status='validated';detail=f'KML bien formado con {count} objetos; geometrías aún no incorporadas al mapa.'
            elif ext in ('.geojson','.json'):
                parsed=json.loads(raw)
                count=len(parsed.get('features',[])) if isinstance(parsed,dict) else len(parsed) if isinstance(parsed,list) else 0
                status='validated';detail='JSON válido; geometrías sujetas a revisión.'
            elif ext=='.xlsx':
                if not zipfile.is_zipfile(io.BytesIO(raw)):raise ValueError('Libro XLSX inválido')
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    if '[Content_Types].xml' not in archive.namelist():raise ValueError('Libro XLSX no válido')
                detail='XLSX almacenado; falta revisión y correspondencia de columnas.'
            elif ext=='.pdf':
                if not raw.startswith(b'%PDF-'):raise ValueError('PDF inválido')
                detail='PDF almacenado; falta extracción e indexación autorizada.'
        except (UnicodeDecodeError,ValueError,csv.Error,SafeET.ParseError,json.JSONDecodeError,zipfile.BadZipFile) as exc:
            raise HTTPException(422,'Validación fallida: '+str(exc)[:180])
        digest=hashlib.sha256(raw).hexdigest()
        exists=session.scalar(select(Dataset).where(Dataset.project_id==pid,Dataset.sha256==digest))
        if exists:raise HTTPException(409,'Archivo duplicado en el proyecto')
        directory=uploads/str(pid);directory.mkdir(parents=True,exist_ok=True)
        diskpath=directory/(uuid.uuid4().hex+ext)
        database_storage=os.getenv('NEXO_STORAGE_MODE','filesystem')=='database'
        if not database_storage:diskpath.write_bytes(raw)
        try:
            dataset=Dataset(project_id=pid,uploaded_by=user.id,filename=name,media_type=ext,sha256=digest,size_bytes=len(raw),status=status,record_count=count,detail=detail,path='database' if database_storage else str(diskpath))
            session.add(dataset);session.flush()
            if database_storage:session.add(DatasetBlob(dataset_id=dataset.id,project_id=pid,content=raw))
            session.add(AuditEvent(project_id=pid,user_id=user.id,action='dataset.upload',target=str(dataset.id)))
            session.commit()
        except Exception:
            session.rollback();diskpath.unlink(missing_ok=True);raise
        return {'id':dataset.id,'filename':dataset.filename,'status':dataset.status,'records':count,'sha256':digest,'detail':detail}

    install_rss_api(app,db,current_user,allow)
    install_auth(app)

    @app.get('/')
    def index():return FileResponse(root/'static'/'index.html')
    @app.get('/favicon.ico')
    def favicon():return {'ok':True}
    script=re.search(r'<script>([\s\S]*?)</script>',(root/'static'/'index.html').read_text(encoding='utf-8')).group(1)
    import base64
    app.add_middleware(Guard,script_hash='sha256-'+base64.b64encode(hashlib.sha256(script.encode()).digest()).decode())
    return app

app=create_app()
