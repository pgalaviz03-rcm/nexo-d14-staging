import hashlib
import io
import os
from pathlib import Path
import sqlite3
import zipfile
import pytest
from scripts import backup_local as backup


@pytest.fixture
def local_project(tmp_path):
    root = tmp_path / 'project'
    uploads = root / 'storage/uploads/1'
    uploads.mkdir(parents=True)
    file = uploads / 'example.csv'
    file.write_bytes(b'column\nexample\n')
    (root / 'storage/.session_secret').write_text('test-only-' + 'x' * 64)
    with sqlite3.connect(root / 'storage/nexo.db') as db:
        db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, password_hash TEXT)')
        db.execute("INSERT INTO users VALUES(1,'test-only-placeholder')")
        db.execute('CREATE TABLE datasets(id INTEGER PRIMARY KEY,path TEXT,sha256 TEXT)')
        db.execute('INSERT INTO datasets VALUES(?,?,?)',
                   (1, str(file), hashlib.sha256(file.read_bytes()).hexdigest()))
    return root


def test_isolated_restore_keeps_source_and_relocates_upload(local_project, tmp_path, monkeypatch):
    # Crypto has its own real Windows test below; this fixture holds artificial data only.
    monkeypatch.setattr(backup, 'dpapi', lambda data, decrypt=False: data)
    source = local_project / 'storage/nexo.db'
    original = source.read_bytes()
    encrypted = tmp_path / 'fixture.nexobak'
    before = backup.create_backup(local_project, encrypted)
    destination = tmp_path / 'recovery'
    after = backup.restore_backup(encrypted, destination)
    assert after['counts'] == before['counts'] == {'datasets': 1, 'users': 1}
    assert source.read_bytes() == original
    with sqlite3.connect(destination / 'storage/nexo.db') as db:
        path = db.execute('SELECT path FROM datasets').fetchone()[0]
        assert Path(path) == destination / 'storage/uploads/1/example.csv'
        assert Path(path).read_bytes() == b'column\nexample\n'
    assert (destination / 'storage/.session_secret').read_bytes() == (local_project / 'storage/.session_secret').read_bytes()
    with pytest.raises(ValueError, match='carpeta nueva'):
        backup.restore_backup(encrypted, destination)


@pytest.mark.parametrize('name', ['../escape', 'storage/../escape', 'storage\\escape', 'C:/escape'])
def test_restore_rejects_paths_outside_storage(name):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(name.replace('\\', '/'), b'test')
    raw = stream.getvalue()
    if '\\' in name:
        raw = raw.replace(name.replace('\\', '/').encode(), name.encode())
    with pytest.raises(ValueError, match='Ruta'):
        backup.read_archive(raw)


def test_archive_rejects_modified_content(local_project):
    raw, manifest = backup.make_archive(local_project)
    stream = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(stream, 'w') as changed:
        for name in source.namelist():
            changed.writestr(name, b'changed' if name == 'storage/.session_secret' else source.read(name))
    with pytest.raises(ValueError, match='hashes'):
        backup.read_archive(stream.getvalue())


def test_missing_upload_fails_instead_of_incomplete_backup(local_project):
    (local_project / 'storage/uploads/1/example.csv').unlink()
    with pytest.raises(FileNotFoundError):
        backup.make_archive(local_project)


def test_backup_does_not_overwrite_existing_file(local_project, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'dpapi', lambda data, decrypt=False: data)
    existing = tmp_path / 'existing'
    existing.write_bytes(b'keep-existing-backup')
    with pytest.raises(FileExistsError):
        backup.create_backup(local_project, existing)
    assert existing.read_bytes() == b'keep-existing-backup'


@pytest.mark.skipif(os.name != 'nt', reason='DPAPI belongs to Windows; archive safety tests run on every OS')
def test_real_dpapi_roundtrip_and_tamper_rejection():
    encrypted = backup.dpapi(b'test-only-nexo-backup-content')
    assert encrypted != b'test-only-nexo-backup-content'
    assert backup.dpapi(encrypted, decrypt=True) == b'test-only-nexo-backup-content'
    modified = bytearray(encrypted)
    modified[-1] ^= 1
    with pytest.raises(RuntimeError):
        backup.dpapi(bytes(modified), decrypt=True)
