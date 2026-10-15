"""Atomic identity-only upgrade; never rewrite the committed v1 schema."""

import sqlite3

from .cloud_v1 import migrate_cloud_schema


def migrate_identity_schema(connection: sqlite3.Connection) -> int:
    nested = connection.in_transaction
    if not nested:
        connection.execute('PRAGMA foreign_keys=ON')
    if not connection.execute('PRAGMA foreign_keys').fetchone()[0]:
        raise RuntimeError('Identity migration requires foreign keys')
    connection.execute('SAVEPOINT identity_schema' if nested else 'BEGIN IMMEDIATE')
    try:
        version = connection.execute('PRAGMA user_version').fetchone()[0]
        exists = connection.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
        ledger = connection.execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations').fetchone()[0] if exists else 0
        if max(version, ledger) > 2:
            raise RuntimeError('Cloud database schema is newer than this application supports')
        if max(version, ledger) < 2:
            migrate_cloud_schema(connection)
            connection.execute('''CREATE TABLE preauth_sessions (
                token_hash TEXT PRIMARY KEY NOT NULL,
                csrf_token_hash TEXT NOT NULL, expires_at TEXT NOT NULL)''')
            connection.execute('''CREATE TABLE recoveries (
                recovery_id TEXT PRIMARY KEY NOT NULL,
                token_hash TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL REFERENCES users(user_id),
                created_by TEXT NOT NULL REFERENCES users(user_id), created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, consumed_at TEXT, revoked_at TEXT)''')
            connection.execute('''CREATE TABLE identity_rate_limits (
                bucket TEXT PRIMARY KEY NOT NULL, window_start INTEGER NOT NULL,
                attempts INTEGER NOT NULL CHECK(attempts>=0))''')
            connection.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(2,strftime('%Y-%m-%dT%H:%M:%fZ','now'))")
            connection.execute('PRAGMA user_version=2')
        connection.execute('RELEASE SAVEPOINT identity_schema') if nested else connection.commit()
    except BaseException:
        if nested:
            connection.execute('ROLLBACK TO SAVEPOINT identity_schema')
            connection.execute('RELEASE SAVEPOINT identity_schema')
        else:
            connection.rollback()
        raise
    return 2
