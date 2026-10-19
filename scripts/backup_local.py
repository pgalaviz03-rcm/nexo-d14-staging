"""Windows local backup and isolated restore; never connects to cloud databases.

DPAPI CurrentUser binds recovery to this Windows profile/computer. This is not
an offsite/disaster-recovery backup. Plaintext archives stay in memory.
"""
import argparse
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import time
import uuid
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b'NEXO-LOCAL-DPAPI-1\n'
MAX_BYTES = 128 * 1024 * 1024


def dpapi(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Este respaldo requiere Windows y el mismo perfil que lo creo.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
    api = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = api.CryptUnprotectData if decrypt else api.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    incoming, outgoing = Blob(len(data), buffer), Blob()
    if not function(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise RuntimeError('Windows no pudo proteger o recuperar esta copia con el perfil actual.')
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData)
    finally:
        kernel.LocalFree(ctypes.cast(outgoing.pbData, ctypes.c_void_p))


def inventory(connection):
    if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('La base no supera la comprobacion de integridad.')
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise ValueError('La base contiene referencias inconsistentes.')
    names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    counts = {name: connection.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
              for name in sorted(names)}
    return counts


def make_archive(root):
    root = Path(root).resolve()
    db = root / 'storage/nexo.db'
    if not db.is_file():
        raise ValueError('No existe una base local para respaldar.')
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=5) as source:
        with sqlite3.connect(':memory:') as snapshot:
            deadline = time.monotonic() + 20
            def progress(status, remaining, total):
                if time.monotonic() > deadline:
                    raise TimeoutError('La base sigue ocupada; intenta el respaldo de nuevo.')
            source.backup(snapshot, pages=100, progress=progress, sleep=0.05)
            counts = inventory(snapshot)
            files = {'storage/nexo.db': snapshot.serialize()}
            references = []
            for row in snapshot.execute("SELECT id,path,sha256 FROM datasets WHERE path<>'database'"):
                path = Path(row[1]).resolve()
                relative = path.relative_to((root / 'storage/uploads').resolve())
                name = 'storage/uploads/' + relative.as_posix()
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != row[2]:
                    raise ValueError('Un archivo cargado no coincide con su hash registrado.')
                files[name] = raw
                references.append({'id': row[0], 'file': name})
    secret = root / 'storage/.session_secret'
    if not secret.is_file():
        raise ValueError('Falta la clave de sesion local; no se creara una copia incompleta.')
    files['storage/.session_secret'] = secret.read_bytes()
    if sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('La copia supera el limite de 128 MiB de este piloto.')
    manifest = {'format': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'counts': counts, 'references': references,
                'sha256': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}}
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False))
    return output.getvalue(), manifest


def read_archive(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('Copia demasiado grande.')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 10000:
            raise ValueError('Entradas duplicadas o demasiados archivos.')
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (info.orig_filename != info.filename or '\\' in info.filename or ':' in info.filename or path.is_absolute()
                    or '..' in path.parts or path.as_posix() != info.filename
                    or info.filename != 'manifest.json' and not info.filename.startswith('storage/')):
                raise ValueError('Ruta de archivo no permitida.')
        if sum(i.file_size for i in archive.infolist()) > MAX_BYTES:
            raise ValueError('Contenido descomprimido demasiado grande.')
        if 'manifest.json' not in names:
            raise ValueError('Falta el manifiesto de la copia.')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format') != 1 or set(names) != set(manifest['sha256']) | {'manifest.json'}:
            raise ValueError('Manifiesto no valido.')
        files = {name: archive.read(name) for name in manifest['sha256']}
    for name, data in files.items():
        if hashlib.sha256(data).hexdigest() != manifest['sha256'][name]:
            raise ValueError('La copia no coincide con sus hashes.')
    if not {'storage/nexo.db', 'storage/.session_secret'}.issubset(files):
        raise ValueError('Copia incompleta.')
    for reference in manifest['references']:
        if reference['file'] not in files or not reference['file'].startswith('storage/uploads/'):
            raise ValueError('Archivo cargado ausente o fuera de la carpeta permitida.')
    with sqlite3.connect(':memory:') as check:
        check.deserialize(files['storage/nexo.db'])
        if inventory(check) != manifest['counts']:
            raise ValueError('La base no coincide con el inventario.')
        actual_ids = {r[0] for r in check.execute("SELECT id FROM datasets WHERE path<>'database'")}
        if actual_ids != {r['id'] for r in manifest['references']}:
            raise ValueError('Inventario de archivos incompleto.')
    return files, manifest


def create_backup(root, destination):
    raw, manifest = make_archive(root)
    encrypted = MAGIC + dpapi(raw)
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as target:
        target.write(encrypted)
    return manifest


def restore_backup(backup, destination):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('La restauracion exige una carpeta nueva; nunca sobrescribe datos existentes.')
    encrypted = Path(backup).read_bytes()
    if not encrypted.startswith(MAGIC) or len(encrypted) > MAX_BYTES + 65536:
        raise ValueError('Formato de copia no valido.')
    files, manifest = read_archive(dpapi(encrypted[len(MAGIC):], decrypt=True))
    destination.mkdir(parents=False, exist_ok=False)
    for name, raw in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as target:
            target.write(raw)
    with sqlite3.connect(destination / 'storage/nexo.db') as check:
        for reference in manifest['references']:
            check.execute('UPDATE datasets SET path=? WHERE id=?',
                          (str(destination / reference['file']), reference['id']))
        check.commit()
        if inventory(check) != manifest['counts']:
            raise ValueError('La restauracion no supera la comprobacion final.')
    return manifest


def main():
    parser = argparse.ArgumentParser(description='Copia cifrada local y ensayo en carpeta nueva, Windows CurrentUser.')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--directory', type=Path, default=ROOT / 'storage/backups')
    parser.add_argument('--restore', type=Path)
    parser.add_argument('--target', type=Path)
    parser.add_argument('--human', action='store_true')
    args = parser.parse_args()
    if args.restore:
        if not args.target:
            parser.error('--restore requiere --target con una carpeta nueva')
        result = restore_backup(args.restore, args.target)
        print(json.dumps({'restored_to': str(args.target.resolve()), 'counts': result['counts'],
                          'active_database_overwritten': False}, ensure_ascii=False))
        return
    folder = args.directory.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    backup, restored = folder / (tag + '.nexobak'), folder / (tag + '-ensayo')
    original = create_backup(args.root, backup)
    verified = restore_backup(backup, restored)
    if args.human:
        print('Copia cifrada creada y recuperacion de ensayo comprobada.')
        print('Respaldo: ' + str(backup))
        print('Ensayo aislado: ' + str(restored))
        print('Secciones recuperadas: ' + str(verified['counts'].get('section_metrics', 0)))
        print('Se recupera con este mismo perfil de Windows y computadora.')
        return
    print(json.dumps({'backup': str(backup), 'restore_check': str(restored),
                      'counts_equal': original['counts'] == verified['counts'],
                      'sections': verified['counts'].get('section_metrics', 0),
                      'protection': 'DPAPI CurrentUser: mismo perfil Windows y computadora',
                      'cloud_backup': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
