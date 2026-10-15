"""Offline migration: preview by default; apply only publishes a new directory.

Mapping v1: {identity_database: path, version: 1, datasets:
 [{database: relative_sqlite_path, kind: ledger_kind_or_snapshots,
   user_id: provisioned_id, account_id: provisioned_id, role_id: provisioned_id}],
 exclude_tables: [{database: relative_path, table: known_public_table, reason: text}]}.
Unknown private tables/files always block. Use consistent offline source backups.
"""
import argparse
import json
import os
import sqlite3
import sys
import uuid
import threading
from contextlib import closing
from pathlib import Path

from .offline import (MigrationError, build_plan, content_digest, file_digest,
                      load_mapping, overlap, quote, snapshot, validate_scope)


def preview(source, mapping):
    return build_plan(source,mapping)['report']


def write_report(report, output, *, source, protected_files=()):
    output, root = Path(output).resolve(), Path(source).resolve()
    if output.is_relative_to(root) or output == root or any(overlap(output,p) for p in protected_files):
        raise MigrationError('report_output_overlaps_protected_input')
    # Exclusive creation: an existing report must be deliberately renamed first.
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)


def _tree_hashes(root):
    if any(p.is_symlink() for p in root.rglob('*')):
        raise MigrationError('destination_symlink_rejected')
    return {p.relative_to(root).as_posix(): file_digest(p)
            for p in sorted(root.rglob('*')) if p.is_file() and p != root/'migration-manifest.json'}


def _rename_noreplace(stage, destination):
    if os.name == 'nt':
        os.rename(stage,destination)  # Windows refuses any existing destination.
    elif sys.platform.startswith('linux'):
        # Linux os.rename can replace an empty directory. RENAME_NOREPLACE
        # atomically refuses even a competing writer after our preflight check.
        import ctypes
        library = ctypes.CDLL(None,use_errno=True)
        rename = getattr(library,'renameat2',None)
        if rename is None: raise MigrationError('atomic_no_replace_rename_unavailable')
        rename.argtypes = [ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(-100,os.fsencode(stage),-100,os.fsencode(destination),1):
            errno = ctypes.get_errno()
            raise OSError(errno,os.strerror(errno))
    else:
        raise MigrationError('atomic_no_replace_rename_unavailable')


def _promote(stage, destination):
    if destination.exists(): raise MigrationError('destination_already_exists')
    _rename_noreplace(stage,destination)


def _initialize_ledgers(stage,plan):
    from game_assistant.wuwa_history import WuwaHistory
    from game_assistant.wuwa_gacha import GachaStore as WuwaGacha
    from game_assistant.nte_gacha import GachaStore as NteGacha
    from game_assistant.endfield_gacha import EndfieldGachaStore
    from game_assistant.endfield_blueprints import BlueprintStore
    factories = {'wuwa_history':WuwaHistory,'wuwa_gacha':WuwaGacha,'nte':NteGacha,
                 'endfield_gacha':EndfieldGachaStore,'blueprints':BlueprintStore}
    from game_assistant.private_data import scope_directory
    paths = {}
    for d in plan['datasets']:
        key = (d['scope'],d['kind'])
        if d['kind']=='snapshots' or key in paths: continue
        directory = scope_directory(stage/'private',d['scope'])/d['kind']
        directory.mkdir(parents=True,exist_ok=True)
        path = directory/('ledger.endfield-blueprints.sqlite3' if d['kind']=='blueprints' else 'ledger.sqlite3')
        # Same immutable Task5 manifest. Use explicitly closed offline handles;
        # a live facade owns connections and is not a staging lifecycle manager.
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE private_scope (singleton INTEGER PRIMARY KEY CHECK(singleton=1),'
                       'user_id TEXT NOT NULL,account_id TEXT NOT NULL,role_id TEXT NOT NULL,'
                       'kind TEXT NOT NULL,role_uid TEXT NOT NULL,server_id TEXT NOT NULL,'
                       'UNIQUE(user_id,account_id,role_id))')
            db.execute('INSERT INTO private_scope VALUES(1,?,?,?,?,?,?)',
                       (*validate_scope(d['scope']),d['kind'],d['uid'],d['server']))
        if d['kind'].startswith('wuwa_'):
            with closing(sqlite3.connect(path)) as db:
                factories[d['kind']](db,threading.Lock())
        elif d['kind']=='blueprints':
            factories[d['kind']](directory/'ledger.db')
        else:
            factories[d['kind']](path)
        paths[key] = path
    return paths


def _write_stage(stage,plan):
    from game_assistant.snapshots import SnapshotStore
    report = plan['report']
    with snapshot(plan['identity']) as identity:
        target = sqlite3.connect(stage/'cloud.db')
        try:
            identity.backup(target)
            target.execute('PRAGMA foreign_keys=ON')
            with target:
                for name in plan['invalidated_identity_tables']:
                    target.execute('DELETE FROM '+name)
                target.execute("UPDATE grants SET state='pending',encrypted_payload=NULL,version=version+1")
            # Erase freed pages so discarded auth ciphertext is not retained.
            target.execute('PRAGMA secure_delete=ON')
            target.execute('VACUUM')
            if target.execute('PRAGMA integrity_check').fetchall()!=[('ok',)] or target.execute('PRAGMA foreign_key_check').fetchall():
                raise MigrationError('target_identity_integrity_failed')
        finally:
            target.close()
    store = SnapshotStore(str(stage/'snapshots.db'))
    store._conn.close()
    paths = _initialize_ledgers(stage,plan)
    report['reconciliation'] = []
    for group in plan['collections'].values():
        d,table,columns = group['dataset'],group['table'],group['columns']
        path = stage/'snapshots.db' if d['kind']=='snapshots' else paths[(d['scope'],d['kind'])]
        rows = list(group['rows'].values())
        with closing(sqlite3.connect(path)) as db:
            with db:
                db.executemany('INSERT INTO '+quote(table)+' ('+','.join(map(quote,columns))+') VALUES ('+','.join('?' for _ in columns)+')',rows)
            where, args = (' WHERE user_id=? AND account_id=? AND role_id=?',validate_scope(d['scope'])) if d['kind']=='snapshots' else ('',())
            actual = db.execute('SELECT '+','.join(map(quote,columns))+' FROM '+quote(table)+where,args).fetchall()
            expected_hash, actual_hash = content_digest(rows), content_digest(actual)
            if len(actual)!=len(rows) or expected_hash!=actual_hash or db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:
                raise MigrationError('target_content_reconciliation_failed')
        report['reconciliation'].append(dict(scope=dict(zip(('user_id','account_id','role_id'),validate_scope(d['scope']))),
            kind=d['kind'],table=table,source_count=group['received'],duplicates=group['duplicates'],
            target_count=len(actual),expected_sha256=expected_hash,target_sha256=actual_hash,
            source_tables=[dict(database=a,table=b) for a,b in sorted(group['origins'])],verified=True))
    report['checks']['reconciled'] = True
    report['destination_settings'] = {'cloud_db_path':'cloud.db','cloud_data_root':'.',
                                     'snapshots':'snapshots.db','private':'private',
                                     'cloud_credentials_key_path':'provision_a_new_external_key_before_reauthorization'}
    report['activation_ready'] = False
    with (stage/'report.json').open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)


def apply(source, mapping, destination):
    destination, root = Path(destination).resolve(), Path(source).resolve()
    mapping = load_mapping(mapping)
    if overlap(destination,root) or overlap(destination,Path(mapping['identity_database'])):
        raise MigrationError('destination_overlaps_source')
    plan = build_plan(root,mapping)
    if not plan['report']['ready']: raise MigrationError('migration_requires_manual_review',plan['report'])
    if destination.exists():
        try:
            manifest = json.loads((destination/'migration-manifest.json').read_text(encoding='utf-8'))
            if manifest['version']!=1 or manifest['fingerprint']!=plan['fingerprint'] or manifest['files']!=_tree_hashes(destination):
                raise MigrationError('destination_not_identical')
            report = json.loads((destination/'report.json').read_text(encoding='utf-8'))
        except (OSError,ValueError,KeyError,TypeError):
            raise MigrationError('existing_destination_not_verified') from None
        return dict(report,already_applied=True)
    destination.parent.mkdir(parents=True,exist_ok=True)
    lock = destination.parent / ('.'+destination.name+'.migration.lock')
    try:
        fd = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        raise MigrationError('destination_migration_locked') from None
    os.close(fd)
    stage = destination.parent/('.'+destination.name+'.migration-'+uuid.uuid4().hex[:8])
    try:
        stage.mkdir(mode=0o700)
        _write_stage(stage,plan)
        # Fail before publication if source/identity changed during target writes.
        verify = build_plan(root,mapping)
        if verify['fingerprint']!=plan['fingerprint'] or not verify['report']['ready']:
            raise MigrationError('source_changed_before_publication')
        with (stage/'migration-manifest.json').open('x',encoding='utf-8') as stream:
            json.dump(dict(version=1,fingerprint=plan['fingerprint'],files=_tree_hashes(stage)),stream,sort_keys=True,indent=2)
        _promote(stage,destination)
        return plan['report']
    finally:
        # Failed stage is retained for audit/recovery; it is never usable as the
        # destination and never reused by a subsequent attempt.
        lock.unlink()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ('preview','apply'): argv.insert(0,'preview')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    for command in ('preview','apply'):
        item = sub.add_parser(command)
        item.add_argument('--source',required=True)
        item.add_argument('--mapping',required=True)
        item.add_argument('--output',required=command=='preview')
        if command=='apply': item.add_argument('--destination',required=True)
    args = parser.parse_args(argv)
    try:
        mapping = load_mapping(args.mapping)
        # Validate report path before any migration side effect.
        if args.output:
            output = Path(args.output).resolve()
            protected = [Path(args.mapping).resolve(),Path(mapping['identity_database']).resolve()]
            if output.is_relative_to(Path(args.source).resolve()) or any(overlap(output,p) for p in protected) or output.exists():
                raise MigrationError('unsafe_or_existing_report_output')
            if args.command=='apply' and overlap(output,Path(args.destination).resolve()):
                raise MigrationError('report_output_overlaps_destination')
        report = preview(args.source,mapping) if args.command=='preview' else apply(args.source,mapping,args.destination)
        if args.output: write_report(report,args.output,source=args.source,protected_files=protected)
        print(json.dumps({'ready':report['ready'],'migrated':report['migrated'],'duplicates':report['duplicates'],
                          'unassigned':report['unassigned'],'issues':len(report['issues'])}))
        return 0 if report['ready'] else 2
    except (MigrationError,sqlite3.Error,OSError,ValueError):
        # Never log exception text: SQLite/path/JSON failures can contain source values.
        print('migration_failed_review_inputs',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
