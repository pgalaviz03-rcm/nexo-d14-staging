"""Reuse verified DPAPI/restore format for the private development workspace."""
import hashlib
import json
from pathlib import Path
import uuid
from datetime import datetime,timezone

from backup_local import make_archive,dpapi,MAGIC,restore_backup


def main():
    task=Path(__file__).resolve().parents[3]
    private=task/'work/private/nexo-local-workspace'
    destination=private/'backups';destination.mkdir(exist_ok=True)
    raw,manifest=make_archive(private,db_file=private/'workspace.sqlite',
                              uploads_directory=private/'uploads',secret_file=private/'session.key')
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    backup=destination/(name+'.nexobak');encrypted=MAGIC+dpapi(raw)
    with backup.open('xb') as stream:stream.write(encrypted)
    restored=restore_backup(backup,destination/(name+'-ensayo'))
    if restored['counts']!=manifest['counts']:raise RuntimeError('La restauración no coincide.')
    result=dict(date_utc=manifest['created_utc'],encrypted=True,dpapi_current_user=True,
                isolated_restore_verified=True,table_counts=manifest['counts'],backup_file=backup.name,
                sha256=hashlib.sha256(encrypted).hexdigest(),cloud_backup=False,offsite_backup=False)
    (task/'outputs/NEXO_LOCAL_RESPALDO_RESULTADO.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Copia cifrada y recuperación aislada verificadas. Solo cubre este perfil Windows y esta copia local.')


if __name__=='__main__':
    try:main()
    except Exception:
        print('No se completó la copia local. No se sobrescribió la base activa.')
        raise SystemExit(1)
