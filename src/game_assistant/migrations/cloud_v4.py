"""Atomic one-message QQ code redemption and append-only legacy link compatibility."""
import sqlite3
from .cloud_v3 import migrate_qq_schema

STATEMENTS = (
    '''CREATE TABLE qq_link_redemptions (
        message_key TEXT PRIMARY KEY NOT NULL, code_hash TEXT NOT NULL,
        link_id TEXT NOT NULL REFERENCES qq_links(link_id), created_at TEXT NOT NULL)''',
    "UPDATE qq_link_attempts SET status='rejected' WHERE status='pending'",
    "UPDATE qq_link_codes SET revoked_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE consumed_at IS NULL AND revoked_at IS NULL",
)


def migrate_qq_redemption_schema(connection: sqlite3.Connection) -> int:
    nested=connection.in_transaction
    if not nested:connection.execute('PRAGMA foreign_keys=ON')
    if not connection.execute('PRAGMA foreign_keys').fetchone()[0]:
        raise RuntimeError('QQ migration requires foreign keys')
    connection.execute('SAVEPOINT qq_redemption_schema' if nested else 'BEGIN IMMEDIATE')
    try:
        version=connection.execute('PRAGMA user_version').fetchone()[0]
        exists=connection.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
        ledger=connection.execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations').fetchone()[0] if exists else 0
        if max(version,ledger)>4:raise RuntimeError('Cloud database schema is newer than this application supports')
        if max(version,ledger)<4:
            migrate_qq_schema(connection)
            for statement in STATEMENTS:connection.execute(statement)
            connection.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(4,strftime('%Y-%m-%dT%H:%M:%fZ','now'))")
            connection.execute('PRAGMA user_version=4')
        connection.execute('RELEASE SAVEPOINT qq_redemption_schema') if nested else connection.commit()
    except BaseException:
        if nested:
            connection.execute('ROLLBACK TO SAVEPOINT qq_redemption_schema')
            connection.execute('RELEASE SAVEPOINT qq_redemption_schema')
        else:connection.rollback()
        raise
    return 4
