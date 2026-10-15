"""Fixed-root SSH backup reader, shipped over stdin; standard library only."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile

ROOT = Path('/var/lib/game-manage-cloud-trial-backups')
FORMAT = 'game-manage-trial-backup-set-v1'
NAME = re.compile(r'\d{8}T\d{6}Z-[0-9a-f]{8}')
MAX_FILES = 4096
MAX_BYTES = 2 * 1024**3
MAX_METADATA_BYTES = 2 * 1024**2


def safe_relative(value):
    if not isinstance(value, str):
        raise ValueError('invalid_path')
    relative = PurePosixPath(value)
    if (not value or not relative.parts or relative.is_absolute() or str(relative) != value or
            any(c in value for c in '\\:<>"|?*') or '..' in relative.parts):
        raise ValueError('invalid_path')
    for part in relative.parts:
        if (len(part) > 200 or part.endswith((' ', '.')) or
                any(ord(c) < 32 for c in part) or
                part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                    *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
            raise ValueError('invalid_path')
    return relative


def plain(path):
    value = path.lstat()
    if (stat.S_ISLNK(value.st_mode) or
            getattr(value, 'st_file_attributes', 0) & 0x400 or
            not (stat.S_ISDIR(value.st_mode) or stat.S_ISREG(value.st_mode))):
        raise ValueError('unsafe_file')
    return value


def metadata(path):
    if not stat.S_ISREG(plain(path).st_mode) or path.stat().st_size > MAX_METADATA_BYTES:
        raise ValueError('metadata_limit')
    result = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result, dict):
        raise ValueError('invalid_metadata')
    return result


def inspect_set(root, *, verify_hashes=False):
    if not stat.S_ISDIR(plain(root).st_mode):
        raise ValueError('invalid_set')
    if not stat.S_ISDIR(plain(root / 'cloud').st_mode):
        raise ValueError('invalid_set')
    mark = metadata(root / 'complete.json')
    manifest = metadata(root / 'cloud/manifest.json')
    if (mark.get('format') != FORMAT or manifest.get('format_version') != 1 or
            manifest.get('identity_schema_version') not in (2, 3, 4) or
            any(doc.get('key_included') is not False or
                doc.get('whole_system_snapshot') is not False or
                doc.get('consistency') != 'per_file_online' for doc in (mark, manifest))):
        raise ValueError('unsupported_set')
    entries = manifest.get('files')
    if not isinstance(entries, list) or len(entries) + 3 > MAX_FILES:
        raise ValueError('file_limit')
    expected = {'complete.json': None, 'cloud/manifest.json': None,
                'qq-state.db': (None, mark.get('qq_sha256'))}
    for entry in entries:
        relative = safe_relative(entry['path'])
        if (str(relative) != 'identity.db' and (len(relative.parts) < 2 or relative.parts[0] != 'data')):
            raise ValueError('invalid_manifest_path')
        if (relative.name.lower() == 'grants.key' or entry.get('kind') not in {'sqlite', 'sidefile'} or
                type(entry.get('size')) is not int or entry['size'] < 0):
            raise ValueError('invalid_manifest_file')
        name = 'cloud/' + str(relative)
        if name.casefold() in {key.casefold() for key in expected}:
            raise ValueError('duplicate_path')
        expected[name] = (entry['size'], entry.get('sha256'))
    if not {'cloud/identity.db', 'cloud/data/snapshots.db'} <= set(expected):
        raise ValueError('required_file_missing')
    for record in expected.values():
        if record is not None and (not isinstance(record[1], str) or
                                  not re.fullmatch('[0-9a-f]{64}', record[1])):
            raise ValueError('invalid_digest')
    actual, count, size = set(), 0, 0
    # Walk without following directory links; check each entry before descending.
    pending = [root]
    while pending:
        for path in pending.pop().iterdir():
            relative = path.relative_to(root).as_posix()
            safe_relative(relative)
            value = plain(path)
            count += 1
            if count > MAX_FILES * 2:
                raise ValueError('tree_limit')
            if stat.S_ISDIR(value.st_mode):
                if not any(name.startswith(relative + '/') for name in expected):
                    raise ValueError('inventory_mismatch')
                pending.append(path)
                continue
            actual.add(relative)
            size += value.st_size
            if size > MAX_BYTES or len(actual) > MAX_FILES:
                raise ValueError('size_limit')
            if relative not in expected:
                raise ValueError('inventory_mismatch')
            record = expected[relative]
            if record is not None:
                expected_size, expected_hash = record
                if expected_size is not None and expected_size != value.st_size:
                    raise ValueError('digest_mismatch')
                if verify_hashes:
                    h = hashlib.sha256()
                    with path.open('rb') as stream:
                        for chunk in iter(lambda: stream.read(1024**2), b''):
                            h.update(chunk)
                    if h.hexdigest() != expected_hash:
                        raise ValueError('digest_mismatch')
    if actual != set(expected):
        raise ValueError('inventory_mismatch')
    return {'name': root.name, 'files': len(actual), 'bytes': size}


def latest(root):
    for name in sorted((entry.name for entry in root.iterdir() if NAME.fullmatch(entry.name)), reverse=True):
        path = root / name
        plain(path)
        if not (path / 'complete.json').exists():
            continue
        return inspect_set(path)
    return None


def main():
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('linux_root_required')
    for path in (ROOT, *ROOT.parents):
        value = plain(path)
        if value.st_uid != 0 or value.st_mode & 0o022:
            raise ValueError('unsafe_backup_root')
    if ROOT.stat().st_mode & 0o077:
        raise ValueError('unsafe_backup_root')
    if sys.argv[1:] == ['list']:
        print(json.dumps(latest(ROOT)))
    elif len(sys.argv) == 3 and sys.argv[1] == 'archive' and NAME.fullmatch(sys.argv[2]):
        root = ROOT / sys.argv[2]
        inspect_set(root)
        with tarfile.open(fileobj=sys.stdout.buffer, mode='w|', format=tarfile.USTAR_FORMAT) as tar:
            for path in sorted(root.rglob('*')):
                plain(path)
                if path.is_file():
                    tar.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)
    else:
        raise ValueError('invalid_operation')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('remote_backup_read_failed', file=sys.stderr)
        raise SystemExit(2)
