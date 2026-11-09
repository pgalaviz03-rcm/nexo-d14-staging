"""Local workspace with a private one-time snapshot; cloud credentials unused."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import uuid
from contextlib import closing


def main():
    parser=argparse.ArgumentParser(description='NEXO local: datos propios y conectores desactivados')
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    code=Path(__file__).resolve().parents[1]
    source=args.source.resolve(strict=True);private=args.directory.resolve()
    if private.is_relative_to(code) or source.is_relative_to(private):
        parser.error('La copia privada debe quedar separada de código y base original.')
    private.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        account=(os.environ.get('USERDOMAIN','')+'\\'+os.environ['USERNAME']).lstrip('\\')
        result=subprocess.run(['icacls',str(private),'/inheritance:r','/grant:r',
                               account+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],
                              capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
        if result.returncode:raise RuntimeError('No se pudieron proteger los archivos de la copia local.')
    snapshot=private/'workspace.sqlite';uploads=private/'uploads';fresh=False
    if not snapshot.exists():
        fresh=True
        pending=private/('workspace.initializing-'+uuid.uuid4().hex[:8]+'.sqlite')
        # An interrupted first copy never becomes the active workspace.
        with pending.open('xb'):pass
        with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as original:
            with closing(sqlite3.connect(pending)) as target:
                original.backup(target)
                # Relocate referenced files, verifying hash and private scope.
                allowed=(source.parent/'uploads').resolve()
                for did,pid,path,digest in target.execute('SELECT id,project_id,path,sha256 FROM datasets').fetchall():
                    if path=='database':continue
                    old=Path(path).resolve()
                    if not old.is_relative_to(allowed) or not old.is_file():
                        raise RuntimeError('Un archivo referenciado necesita revisión antes de copiarse.')
                    raw=old.read_bytes()
                    if hashlib.sha256(raw).hexdigest()!=digest:raise RuntimeError('Un archivo no coincide con su huella.')
                    new=uploads/str(pid)/(str(did)+old.suffix)
                    new.parent.mkdir(parents=True,exist_ok=True);new.write_bytes(raw)
                    target.execute('UPDATE datasets SET path=? WHERE id=?',(str(new),did))
                target.commit()
        if snapshot.exists():raise RuntimeError('Otra instancia ya preparó la copia local.')
        pending.rename(snapshot)
    with closing(sqlite3.connect(snapshot.as_uri()+'?mode=ro',uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise RuntimeError('La copia no supera la comprobación de integridad.')
        counts=dict(news=db.execute('SELECT count(*) FROM news_articles').fetchone()[0],
                    historical=list(db.execute('SELECT count(*),sum(territorial_votes),sum(nominal_list) FROM section_metrics').fetchone()))
    keyfile=private/'session.key'
    if not keyfile.exists():
        with keyfile.open('x',encoding='ascii') as f:f.write(secrets.token_urlsafe(48))
    os.environ.update(NEXO_ENV='local',DATABASE_URL='sqlite:///'+snapshot.as_posix(),
                      NEXO_STORAGE_MODE='filesystem',NEXO_STORAGE_DIR=str(uploads),
                      NEXO_SECRET_KEY=keyfile.read_text(encoding='ascii'),NEXO_AI_ENABLED='false',
                      NEXO_RELEASE_APPROVED='false',NEXO_RSS_ALLOWED_HOSTS='',
                      NEXO_LOCAL_WORKSPACE='true',NEXO_OFFLINE='true',NEXO_VISUAL_REVIEW='false')
    # Ignore inherited provider credentials in this process; never read their values.
    for name in list(os.environ):
        if name.startswith(('OPENAI_','ANTHROPIC_','SUPABASE_','NEXO_SUPABASE_','APIFY_')):
            os.environ.pop(name,None)
    if args.prepare_only:
        print(json.dumps(dict(prepared=True,new_snapshot=fresh,counts=counts,external_connections=False)))
        return
    sys.path.insert(0,str(code))
    import uvicorn
    from app.main import app
    print('NEXO LOCAL: http://127.0.0.1:8002',flush=True)
    print('Usa tu cuenta LOCAL habitual. No se necesita la cuenta de nube.',flush=True)
    print('Copia privada; las dos fuentes y sus noticias guardadas están disponibles.',flush=True)
    print('APIs externas e IA desactivadas. Ctrl+C detiene esta copia.',flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8002,access_log=False,log_level='warning')


if __name__=='__main__':
    try:main()
    except Exception:
        print('No se inició NEXO local. Revisa la copia privada, sus archivos y si el puerto 8002 está libre. No compartas claves.')
        raise SystemExit(1)
