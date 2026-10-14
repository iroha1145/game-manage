"""Explicit online SQLite backups. No credential key or payload logging."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import stat
from pathlib import Path
import sqlite3
import sys
import time
import uuid


class OperationError(ValueError):
    pass


def safe_path(value):
    path = Path(value).absolute()
    if any(item.is_symlink() or (item.exists() and getattr(item.lstat(),'st_file_attributes',0)
            & getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)) for item in (path, *path.parents)):
        raise OperationError('symlink_path_rejected')
    return path.resolve()


def separate(*paths):
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            if left == right or left.is_relative_to(right) or right.is_relative_to(left):
                raise OperationError('overlapping_paths')


def key_digest(path):
    from game_assistant.auth.store import CredentialStore, CredentialStoreError
    try:
        return hashlib.sha256(CredentialStore('unused', key_path=safe_path(path))._grant_key()).hexdigest()
    except CredentialStoreError:
        raise OperationError('key_unavailable') from None


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def connect_readonly(path):
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=10)


def database_version(path):
    with closing(connect_readonly(path)) as db:
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise OperationError('database_integrity_failed')
        return db.execute('PRAGMA user_version').fetchone()[0]


def credential_check(identity, key):
    from game_assistant.auth.store import CredentialStore, CredentialStoreError
    with closing(connect_readonly(identity)) as db:
        credentials = CredentialStore('unused', connection=db, key_path=key)
        rows = db.execute("SELECT g.user_id,g.grant_id FROM grants g JOIN users u ON u.user_id=g.user_id "
            "WHERE g.state='active' AND u.disabled_at IS NULL").fetchall()
        try:
            for owner, grant in rows:
                credentials.load_grant(owner, grant)
        except CredentialStoreError:
            raise OperationError('credential_readability_failed') from None
    return 'verified' if rows else 'no_active_grants'


def identity_version(path):
    from game_assistant.migrations.offline import identity_schema_valid
    with closing(connect_readonly(path)) as db:
        rows=db.execute('SELECT version FROM schema_migrations ORDER BY version').fetchall()
        version=rows[-1][0] if rows else 0
        if (version not in (2,3,4) or rows!=[(number,) for number in range(1,version+1)]
                or db.execute('PRAGMA user_version').fetchone()[0]!=version
                or db.execute('PRAGMA foreign_key_check').fetchall()
                or not identity_schema_valid(db,version)):
            raise OperationError('unsupported_identity_schema')
    return version


def inventory(root, identity):
    """Known runtime files only; private manifest validates ownership/path."""
    from game_assistant.private_data import list_scope_files
    known = {identity: 'identity.db'}
    for name in ('snapshots.db', 'public.db', 'public.endfield-public.sqlite3',
                 'public.nte-guides.sqlite3', 'public.wuwa-guides.sqlite3',
                 'public.endfield-gacha.sqlite3', 'public.endfield-blueprints.sqlite3'):
        candidate = root / name
        if candidate.exists() and candidate != identity:
            known[candidate] = 'data/' + name
    for name in ('migration-manifest.json','report.json'):
        candidate = root / name
        if candidate.exists():
            known[candidate] = 'data/' + name
    for item in list_scope_files(root / 'private'):
        path = safe_path(item['path'])
        known[path] = 'data/' + path.relative_to(root).as_posix()
    # Sidefiles with credentials are deliberately refused, not silently omitted.
    # Cloud public collectors do not provision community credentials.
    for path in root.rglob('*'):
        safe_path(path)
        if not path.is_file() or path in known:
            continue
        if path.name == 'scheduler.lock' or path.name.endswith(('-wal', '-shm', '-journal')):
            continue
        if path.relative_to(root).parts[0] == 'logs':
            continue
        raise OperationError('unrecognized_data_file')
    if not identity.is_file() or not (root / 'snapshots.db').is_file():
        raise OperationError('required_database_missing')
    return sorted(known.items(), key=lambda item: item[1])


def backup(source, identity, destination, key):
    root, identity, destination, key = map(safe_path, (source, identity, destination, key))
    separate(root, destination, key)
    separate(identity, destination)
    if destination.exists():
        raise OperationError('destination_exists')
    files = inventory(root, identity)
    fingerprint = key_digest(key)
    # Keep staging name short: Windows SQLite may still use MAX_PATH internally.
    stage = destination.parent / ('.b-' + uuid.uuid4().hex[:12])
    stage.mkdir(parents=True, mode=0o700)
    entries = []
    # Interrupted or failed stages remain unpublished for explicit operator review.
    for source_path, relative in files:
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix == '.json':
            raw=source_path.read_bytes()
            json.loads(raw)
            target.write_bytes(raw)
            if digest(source_path)!=digest(target):
                raise OperationError('sidefile_changed_retry_after_quiescence')
            version=None
        else:
            deadline=time.monotonic()+120
            def progress(status,remaining,total):
                if time.monotonic()>deadline:
                    raise OperationError('online_backup_timeout')
            with closing(connect_readonly(source_path)) as source_db, closing(sqlite3.connect(target)) as target_db:
                source_db.backup(target_db,pages=256,sleep=0.01,progress=progress)
                # A portable backup must not create WAL/SHM files when read;
                # this changes only the copy, never live source journal mode.
                target_db.execute('PRAGMA journal_mode=DELETE')
            version=database_version(target)
        entries.append({'path':relative, 'sha256':digest(target), 'size':target.stat().st_size,
                        'kind':'sidefile' if version is None else 'sqlite','sqlite_user_version':version})
    if files != inventory(root, identity):
        raise OperationError('inventory_changed_retry_after_quiescence')
    schema = identity_version(stage / 'identity.db')
    readability = credential_check(stage / 'identity.db', key)
    manifest = {'format_version':1, 'identity_schema_version':schema,
        'created_at':datetime.now(timezone.utc).isoformat(), 'consistency':'per_file_online',
        'whole_system_snapshot':False, 'key_included':False, 'key_sha256':fingerprint,
        'credential_readability':readability, 'files':entries}
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    publish(stage, destination)
    return manifest


def publish(stage, destination):
    # Reuse the migration's platform-specific atomic no-replace publisher.
    from game_assistant.migrations.cli import _rename_noreplace
    try:
        _rename_noreplace(stage, destination)
    except (OSError, ValueError):
        raise OperationError('destination_publish_failed') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Explicit cloud_data_root')
    parser.add_argument('--identity', required=True, help='Explicit cloud identity database')
    parser.add_argument('--destination', required=True, help='New backup directory outside all sources')
    parser.add_argument('--key', required=True, help='Provisioned external 32-byte key; never copied')
    args = parser.parse_args(argv)
    try:
        result = backup(args.source, args.identity, args.destination, args.key)
        print(json.dumps({'status':'backed_up', 'files':len(result['files']),
                          'consistency':result['consistency'], 'key_included':False}))
        return 0
    except (OperationError, OSError, sqlite3.Error, PermissionError):
        print('backup_failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
