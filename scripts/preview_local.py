"""Run the candidate against a private SQLite snapshot, on loopback only."""
import argparse
import os
import secrets
import sqlite3
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Vista candidata NEXO en una copia SQLite aislada')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    candidate = Path(__file__).resolve().parents[1]
    source = args.source.resolve(strict=True)
    private = args.directory.resolve()
    if private.is_relative_to(candidate):
        parser.error('Guarda la copia privada fuera de la carpeta de código')
    private.mkdir(parents=True, exist_ok=True)
    snapshot = private / 'preview.sqlite'
    if source == snapshot:
        parser.error('La copia debe ser distinta de la base activa')
    if not snapshot.exists():
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
            with sqlite3.connect(snapshot) as target:
                original.backup(target)
    with sqlite3.connect(snapshot.as_uri() + '?mode=ro', uri=True) as checked:
        if checked.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('La copia privada no superó la comprobación de integridad')
    os.environ.update(NEXO_ENV='local', DATABASE_URL='sqlite:///' + snapshot.as_posix(),
                      NEXO_STORAGE_MODE='filesystem', NEXO_STORAGE_DIR=str(private / 'uploads'),
                      NEXO_SECRET_KEY=secrets.token_urlsafe(48), NEXO_AI_ENABLED='false',
                      NEXO_RELEASE_APPROVED='false', NEXO_RSS_ALLOWED_HOSTS='')
    sys.path.insert(0, str(candidate))
    import uvicorn
    from app.main import app
    print('CANDIDATO ATALAYA: abre http://127.0.0.1:8001', flush=True)
    print('Copia aislada. Sin IA ni lectura RSS externa en esta vista de prueba.', flush=True)
    print('La cuenta local conserva su contraseña. Ctrl+C detiene solo esta vista.', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=8001, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
