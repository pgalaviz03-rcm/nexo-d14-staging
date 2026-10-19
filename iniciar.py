"""Iniciar NEXO local. No publica datos en Internet. Requiere dependencias instaladas."""
import os,subprocess,sys,secrets,json,threading,time,urllib.request,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
from dotenv import load_dotenv
load_dotenv(ROOT/'.env', override=False)
if os.getenv('NEXO_ENV','local')!='local':
    raise SystemExit('iniciar.py es exclusivo del entorno local')
( ROOT/'storage').mkdir(exist_ok=True)
secret_file=ROOT/'storage'/'.session_secret'
if not os.environ.get('NEXO_SECRET_KEY'):
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32),encoding='utf-8')
        try:secret_file.chmod(0o600)
        except OSError:pass
    os.environ['NEXO_SECRET_KEY']=secret_file.read_text(encoding='utf-8').strip()
os.environ.setdefault('DATABASE_URL','sqlite:///./storage/nexo.db')
if not os.environ['DATABASE_URL'].startswith('sqlite:'):
    raise SystemExit('El inicio local requiere una base SQLite local. Revisa DATABASE_URL antes de continuar.')
os.environ.setdefault('NEXO_STORAGE_DIR',str(ROOT/'storage'/'uploads'))
from app.database import create_database
from app.models import Base,User
from sqlalchemy import select
engine,SessionLocal=create_database()
Base.metadata.create_all(engine)
with SessionLocal() as s:
    has_users=s.scalar(select(User.id).limit(1)) is not None
if not has_users:
    print('\n== PRIMER INICIO: CREANDO ADMINISTRADOR LOCAL ==')
    subprocess.run([sys.executable,str(ROOT/'init_demo.py')],check=True)
    print('GUARDA LA CONTRASEÑA MOSTRADA ARRIBA ANTES DE ENTRAR.\n')
else:
    print('Usuarios locales existentes. Se respetan las cuentas ya creadas.')
print('Abre en tu navegador: http://127.0.0.1:8000')
print('Para detener el servidor pulsa Ctrl+C.\n')
if os.getenv('NEXO_OPEN_BROWSER','true').lower()=='true':
    def open_local_browser():
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(60):
            try:
                with opener.open('http://127.0.0.1:8000/api/health',timeout=0.5) as response:
                    healthy=json.loads(response.read(1024)).get('version')=='0.5'
                if healthy:
                    webbrowser.open('http://127.0.0.1:8000')
                    return
            except (OSError,ValueError):
                pass
            time.sleep(0.25)
    threading.Thread(target=open_local_browser,daemon=True).start()
import uvicorn
uvicorn.run('app.main:app',host='127.0.0.1',port=8000,reload=False)
