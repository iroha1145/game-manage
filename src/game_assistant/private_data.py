"""Cloud-only private shards. Never adopt a local ledger or infer an owner.

Each shard has an immutable owner manifest; the hash includes all three internal
identifiers. Legacy SQL keys stay unchanged inside this physically isolated file.
"""
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

from .accounts.models import AccountScope


def validate_scope(scope):
    if not isinstance(scope, AccountScope) or any(
        not isinstance(v,str) or not v.strip() or len(v)>256 or '\0' in v
        for v in (scope.user_id,scope.account_id,scope.role_id)):
        raise ValueError('A complete AccountScope is required')
    return (scope.user_id,scope.account_id,scope.role_id)


def scope_directory(root,scope):
    values=validate_scope(scope)
    digest=hashlib.sha256(json.dumps(values,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    base=Path(root).resolve()
    target=base/digest
    if target.resolve().parent!=base:
        raise PermissionError('Private scope path is invalid')
    return target


def _manifest(path,scope,kind,role_uid,server_id,*,create=False):
    expected=(*validate_scope(scope),kind,role_uid,server_id)
    with sqlite3.connect(path) as db:
        db.execute('BEGIN IMMEDIATE' if create else 'BEGIN')
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='private_scope' AND type='table'").fetchone()
        if not exists:
            if not create or db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
                raise PermissionError('Private shard has no owner manifest')
            db.execute('CREATE TABLE private_scope (singleton INTEGER PRIMARY KEY CHECK(singleton=1),'
                'user_id TEXT NOT NULL,account_id TEXT NOT NULL,role_id TEXT NOT NULL,'
                'kind TEXT NOT NULL,role_uid TEXT NOT NULL,server_id TEXT NOT NULL,'
                'UNIQUE(user_id,account_id,role_id))')
            db.execute('INSERT INTO private_scope VALUES(1,?,?,?,?,?,?)',expected)
        rows=db.execute('SELECT user_id,account_id,role_id,kind,role_uid,server_id FROM private_scope').fetchall()
        if rows!=[expected]:
            raise PermissionError('Private shard owner does not match')


class ScopedLedger:
    """Every public operation receives and verifies the already-resolved scope."""
    METHODS={
        'nte':{'preview','import_document','records','rules','set_rule','summary','export'},
        'wuwa_gacha':{'import_records','read'},
        'wuwa_history':{'append','capture','read','backfill'},
        'endfield_gacha':{'sync','summary','records','export','add_records'},
        'blueprints':{'items','save','delete'},
    }
    TABLES={'nte':('records','batches','rules','accounts'),
        'wuwa_gacha':('wuwa_gacha','wuwa_gacha_imports'), 'wuwa_history':('wuwa_history',),
        'endfield_gacha':('records','pools','breaks'),'blueprints':('blueprints',)}

    def __init__(self,scope,path,kind,role_uid,server_id,store):
        self.scope,self.path,self.kind=scope,path,kind
        self.role_uid,self.server_id,self._store=role_uid,server_id,store
        self._lock=threading.RLock()

    def _check(self,scope):
        validate_scope(scope)
        if scope!=self.scope:
            raise PermissionError('Private scope does not match')
        _manifest(self.path,scope,self.kind,self.role_uid,self.server_id)

    def __getattr__(self,name):
        if name not in self.METHODS[self.kind]:
            raise AttributeError(name)
        def operation(scope,*args,**kwargs):
            with self._lock:
                self._check(scope)
                if self.kind=='blueprints':
                    return getattr(self._store,name)(*args,**kwargs)
                if self.kind=='wuwa_history' and name=='capture':
                    kwargs['expected']=(self.role_uid,self.server_id)
                    return self._store.capture(*args,**kwargs)
                if self.kind=='wuwa_history' and name=='backfill':
                    raise ValueError('Cloud history backfill requires scoped snapshots')
                if self.kind=='wuwa_gacha' and name=='import_records':
                    return self._store.import_records(args[0],self.role_uid,self.server_id,**kwargs)
                prefix=(self.role_uid,self.server_id) if self.kind.startswith('wuwa_') else (self.role_uid,)
                method='_add' if name=='add_records' else name
                return getattr(self._store,method)(*prefix,*args,**kwargs)
        return operation

    def clear(self,scope):
        """Explicit user data deletion; authorization revocation preserves ledgers."""
        with self._lock:
            self._check(scope)
            with sqlite3.connect(self.path) as db:
                for table in self.TABLES[self.kind]:
                    db.execute('DELETE FROM '+table)

    def close(self):
        conn=getattr(self._store,'conn',None)
        if conn is not None:
            conn.close()


def scoped_ledger(cls,kind,scope,root,*,role_uid,server_id):
    validate_scope(scope)
    if not isinstance(role_uid,str) or not role_uid or not isinstance(server_id,str) or not server_id:
        raise ValueError('Trusted role and server are required')
    directory=scope_directory(root,scope)/kind
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/('ledger.endfield-blueprints.sqlite3' if kind=='blueprints' else 'ledger.sqlite3')
    _manifest(path,scope,kind,role_uid,server_id,create=True)
    if kind in ('wuwa_gacha','wuwa_history'):
        conn=sqlite3.connect(path,check_same_thread=False)
        store=cls(conn,threading.Lock())
    elif kind=='blueprints':
        store=cls(directory/'ledger.db')
    else:
        store=cls(path)
    return ScopedLedger(scope,path,kind,role_uid,server_id,store)


def list_scope_files(root):
    """Backup inventory only; callers must SQLite-backup, not copy active files."""
    base=Path(root).resolve()
    result=[]
    if not base.exists():
        return result
    for path in sorted(base.glob('*/*/*.sqlite3')):
        if path.resolve().is_relative_to(base) is False:
            raise PermissionError('Private shard path escaped its root')
        with sqlite3.connect(path) as db:
            rows=db.execute('SELECT user_id,account_id,role_id,kind,role_uid,server_id FROM private_scope').fetchall()
        if len(rows)!=1:
            raise PermissionError('Private shard has invalid manifest')
        user,account,role,kind,uid,server=rows[0]
        scope=AccountScope(user,account,role)
        if path.parent.parent!=scope_directory(base,scope) or path.parent.name!=kind:
            raise PermissionError('Private shard path and owner disagree')
        _manifest(path,scope,kind,uid,server)
        result.append(dict(scope=scope,kind=kind,path=path))
    return result


def backup_scope_files(root,destination):
    """Consistent per-file SQLite backups; no cross-file transaction implied."""
    base=Path(root).resolve(); destination=Path(destination).resolve()
    if destination.is_relative_to(base) or base.is_relative_to(destination):
        raise ValueError('Backup source and destination must not overlap')
    inventory=list_scope_files(root)
    for item in inventory:
        target=destination/item['path'].relative_to(base)
        target.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(item['path']) as source, sqlite3.connect(target) as backup:
            source.backup(backup)
    return inventory
