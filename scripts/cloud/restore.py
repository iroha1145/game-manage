"""Restore a verified backup into a new directory, preserving the source."""
import argparse
import json
from pathlib import PurePosixPath
import shutil
import sqlite3
import sys
import uuid

try:
    from .backup import (OperationError, safe_path, separate, key_digest, digest,
                         database_version, credential_check, publish, connect_readonly, inventory, identity_version)
except ImportError:
    from backup import (OperationError, safe_path, separate, key_digest, digest,
                        database_version, credential_check, publish, connect_readonly, inventory, identity_version)


def validate(source, key):
    source, key = map(safe_path, (source, key))
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format_version') != 1:
        raise OperationError('unsupported_backup_version')
    if manifest.get('identity_schema_version') not in (2, 3, 4):
        raise OperationError('unsupported_identity_version')
    if key_digest(key) != manifest.get('key_sha256'):
        raise OperationError('key_mismatch')
    expected = {'manifest.json'}
    for entry in manifest.get('files', []):
        relative = PurePosixPath(entry['path'])
        if (relative.is_absolute() or '..' in relative.parts or '\\' in entry['path']
                or ':' in entry['path'] or str(relative) in expected):
            raise OperationError('invalid_manifest_path')
        if str(relative) != 'identity.db' and (len(relative.parts) < 2 or relative.parts[0] != 'data'):
            raise OperationError('invalid_manifest_path')
        path = safe_path(source / str(relative))
        if not path.is_relative_to(source) or not path.is_file():
            raise OperationError('invalid_manifest_file')
        if path.stat().st_size != entry['size'] or digest(path) != entry['sha256']:
            raise OperationError('backup_digest_mismatch')
        if entry.get('kind')=='sidefile':
            if str(relative) not in {'data/migration-manifest.json','data/report.json'}:
                raise OperationError('invalid_sidefile')
            json.loads(path.read_text(encoding='utf-8'))
        elif entry.get('kind')=='sqlite':
            if database_version(path) != entry['sqlite_user_version']:
                raise OperationError('database_version_mismatch')
        else:
            raise OperationError('invalid_manifest_kind')
        expected.add(str(relative))
    actual = {path.relative_to(source).as_posix() for path in source.rglob('*') if path.is_file()}
    for path in source.rglob('*'):
        safe_path(path)
    if actual != expected or not {'identity.db','data/snapshots.db'} <= expected:
        raise OperationError('backup_inventory_mismatch')
    from contextlib import closing
    with closing(connect_readonly(source / 'identity.db')) as db:
        if db.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0] != manifest['identity_schema_version']:
            raise OperationError('identity_version_mismatch')
        if db.execute('PRAGMA user_version').fetchone()[0] != manifest['identity_schema_version']:
            raise OperationError('identity_version_mismatch')
    inventory(source / 'data', source / 'identity.db')
    if identity_version(source/'identity.db')!=manifest['identity_schema_version']:
        raise OperationError('identity_version_mismatch')
    manifest['credential_readability'] = credential_check(source / 'identity.db', key)
    return manifest


def restore(source, destination, key, *, live_root=None):
    source, destination, key = map(safe_path, (source, destination, key))
    separate(source, destination, key)
    if live_root is not None:
        separate(safe_path(live_root),destination)
    if destination.exists():
        raise OperationError('destination_exists')
    manifest = validate(source, key)
    stage = destination.parent / ('.r-' + uuid.uuid4().hex[:12])
    stage.mkdir(parents=True, mode=0o700)
    for entry in manifest['files']:
        path = entry['path']
        target = stage / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / path, target)
        if digest(target) != entry['sha256']:
            raise OperationError('backup_changed_during_restore')
    result = {'status':'restored', 'format_version':1,
        'identity_schema_version':manifest['identity_schema_version'],
        'credential_readability':credential_check(stage / 'identity.db', key),
        'whole_system_snapshot':manifest.get('whole_system_snapshot') is True}
    (stage / 'restore-report.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    publish(stage, destination)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, help='Backup containing manifest.json')
    parser.add_argument('--destination', required=True, help='New, non-overlapping restore directory')
    parser.add_argument('--key', required=True, help='Separately restored matching external key')
    parser.add_argument('--live-root', required=True, help='Current cloud data root to protect from restore overlap')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(restore(args.source, args.destination, args.key,live_root=args.live_root)))
        return 0
    except (OperationError, OSError, sqlite3.Error, ValueError, KeyError, TypeError):
        print('restore_failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
