"""QQ tables; append-only v3 schema upgrade, preserving caller transactions."""
import sqlite3
from .cloud_v2 import migrate_identity_schema

STATEMENTS = (
    '''CREATE TABLE qq_link_codes (
        code_id TEXT PRIMARY KEY NOT NULL, user_id TEXT NOT NULL REFERENCES users(user_id),
        code_hash TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
        consumed_at TEXT, revoked_at TEXT)''',
    '''CREATE TABLE qq_link_attempts (
        attempt_id TEXT PRIMARY KEY NOT NULL, code_id TEXT NOT NULL UNIQUE REFERENCES qq_link_codes(code_id),
        user_id TEXT NOT NULL REFERENCES users(user_id), app_id TEXT NOT NULL,
        scene TEXT NOT NULL CHECK(scene IN ('group','c2c')), group_openid TEXT, sender_openid TEXT NOT NULL,
        challenge_hash TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending','confirmed','rejected')),
        CHECK((scene='group' AND group_openid IS NOT NULL AND length(group_openid)>0) OR (scene='c2c' AND group_openid IS NULL)))''',
    '''CREATE TABLE qq_links (
        link_id TEXT PRIMARY KEY NOT NULL, user_id TEXT NOT NULL REFERENCES users(user_id),
        attempt_id TEXT NOT NULL UNIQUE REFERENCES qq_link_attempts(attempt_id), app_id TEXT NOT NULL,
        scene TEXT NOT NULL CHECK(scene IN ('group','c2c')), group_openid TEXT, sender_openid TEXT NOT NULL,
        created_at TEXT NOT NULL, revoked_at TEXT,
        CHECK((scene='group' AND group_openid IS NOT NULL AND length(group_openid)>0) OR (scene='c2c' AND group_openid IS NULL)))''',
    "CREATE UNIQUE INDEX qq_active_identity ON qq_links(app_id,scene,COALESCE(group_openid,''),sender_openid) WHERE revoked_at IS NULL",
    'CREATE INDEX qq_attempts_by_owner ON qq_link_attempts(user_id,created_at)',
    '''CREATE TABLE qq_rate_limits (bucket TEXT PRIMARY KEY NOT NULL,
        window_start INTEGER NOT NULL, attempts INTEGER NOT NULL CHECK(attempts>=0))''',
)

def migrate_qq_schema(connection: sqlite3.Connection) -> int:
    nested=connection.in_transaction
    if not nested: connection.execute('PRAGMA foreign_keys=ON')
    if not connection.execute('PRAGMA foreign_keys').fetchone()[0]:
        raise RuntimeError('QQ migration requires foreign keys')
    connection.execute('SAVEPOINT qq_schema' if nested else 'BEGIN IMMEDIATE')
    try:
        version=connection.execute('PRAGMA user_version').fetchone()[0]
        exists=connection.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
        ledger=connection.execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations').fetchone()[0] if exists else 0
        if max(version,ledger)>3: raise RuntimeError('Cloud database schema is newer than this application supports')
        if max(version,ledger)<3:
            migrate_identity_schema(connection)
            for statement in STATEMENTS: connection.execute(statement)
            connection.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(3,strftime('%Y-%m-%dT%H:%M:%fZ','now'))")
            connection.execute('PRAGMA user_version=3')
        connection.execute('RELEASE SAVEPOINT qq_schema') if nested else connection.commit()
    except BaseException:
        if nested:
            connection.execute('ROLLBACK TO SAVEPOINT qq_schema')
            connection.execute('RELEASE SAVEPOINT qq_schema')
        else: connection.rollback()
        raise
    return 3
