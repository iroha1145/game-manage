#!/usr/bin/env python3
"""Root-owned trial backups only; never copies the grant key."""
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
import uuid

from scripts.cloud.backup import backup, digest, publish, safe_path

ROOT = Path('/var/lib/game-manage-cloud-trial-backups')
LIVE = Path('/var/lib/game-manage-cloud-trial')
KEY = Path('/etc/game-manage-cloud-trial/grants.key')
QQ = Path('/var/lib/game-manage-cloud-trial-qq/state.db')
NAME = re.compile(r'\d{8}T\d{6}Z-[0-9a-f]{8}')
FORMAT = 'game-manage-trial-backup-set-v1'


def copy_qq(source, target):
    source = safe_path(source)
    deadline = time.monotonic() + 120
    def progress(*_):
        if time.monotonic() > deadline:
            raise ValueError('qq_backup_timeout')
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=10)) as live, closing(sqlite3.connect(target)) as copy:
        live.backup(copy, pages=256, sleep=0.01, progress=progress)
        copy.execute('PRAGMA journal_mode=DELETE')
        if copy.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('qq_backup_integrity_failed')


def build_set(stage, data, identity, key, qq):
    backup(data, identity, stage / 'cloud', key)
    copy_qq(qq, stage / 'qq-state.db')
    (stage / 'complete.json').write_text(json.dumps({
        'format': FORMAT, 'consistency': 'per_file_online',
        'whole_system_snapshot': False, 'key_included': False,
        'qq_sha256': digest(stage / 'qq-state.db'),
    }) + '\n', encoding='utf-8')


def keep_names(names, now):
    keep, weeks = set(), set()
    for name in sorted(names, reverse=True):
        created = datetime.strptime(name[:16], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        age = (now - created).total_seconds() / 86400
        if age < 0:
            raise ValueError('future_backup')
        if age < 7:
            keep.add(name)
        elif age < 35:
            week = int((age - 7) // 7)
            if week not in weeks:
                keep.add(name)
                weeks.add(week)
    return keep


def managed_sets(root):
    found = []
    for entry in root.iterdir():
        safe_path(entry)
        if entry.name.startswith('.pending-'):
            continue  # Failed stages require manual inspection, never automatic deletion.
        if not NAME.fullmatch(entry.name) or not entry.is_dir():
            raise ValueError('unmanaged_backup')
        mark = entry / 'complete.json'
        if not mark.is_file() or json.loads(mark.read_text(encoding='utf-8')).get('format') != FORMAT:
            raise ValueError('unmanaged_backup')
        for child in entry.rglob('*'):
            safe_path(child)
        found.append(entry)
    return found


def main():
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('linux_root_required')
    os.umask(0o077)
    root = safe_path(ROOT)
    if not root.is_dir() or root.stat().st_uid != 0 or root.stat().st_mode & 0o077:
        raise ValueError('owner_only_root_required')
    # Preflight inventory before producing a new set; unknown files stop the run.
    managed_sets(root)
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    stage = root / ('.pending-' + name)
    stage.mkdir(mode=0o700)
    build_set(stage, LIVE / 'data', LIVE / 'identity.db', KEY, QQ)
    publish(stage, root / name)
    sets = managed_sets(root)
    keep = keep_names([p.name for p in sets], datetime.now(timezone.utc))
    for path in sets:
        # Revalidate exact root and tree immediately before any recursive delete.
        checked = safe_path(path)
        if checked.parent != root or checked == root:
            raise ValueError('retention_boundary_failed')
        for child in checked.rglob('*'):
            safe_path(child)
        if path.name not in keep:
            shutil.rmtree(checked)
    print('backup_set_complete; consistency=per_file_online; key_included=false')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # No tracebacks, private paths, rows, credentials, or exception payloads.
        print('scheduled_backup_failed', file=__import__('sys').stderr)
        raise SystemExit(2)
