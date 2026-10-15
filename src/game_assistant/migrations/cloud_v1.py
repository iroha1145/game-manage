"""Version 1 of the separate cloud database.

Only schema is created here: no local credentials or private data are imported.
Foreign keys must remain enabled on every connection that writes this database.
Token/CSRF/invite fields store digests, password_hash stores a password hash,
and encrypted_payload is reserved for separately encrypted provider credentials.
This migration does not implement hashing, encryption, or authentication.
"""

import sqlite3


SCHEMA_VERSION = 1

_STATEMENTS = (
    """CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY CHECK (version >= 0),
        applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )""",
    """CREATE TABLE users (
        user_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(user_id)) > 0),
        username TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (length(trim(username)) > 0),
        password_hash TEXT NOT NULL CHECK (length(password_hash) > 0),
        is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        disabled_at TEXT
    )""",
    """CREATE TABLE sessions (
        session_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(session_id)) > 0),
        user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE CHECK (length(token_hash) > 0),
        csrf_token_hash TEXT NOT NULL CHECK (length(csrf_token_hash) > 0),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        expires_at TEXT NOT NULL,
        revoked_at TEXT
    )""",
    "CREATE INDEX sessions_by_user ON sessions(user_id)",
    """CREATE TABLE invites (
        invite_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(invite_id)) > 0),
        token_hash TEXT NOT NULL UNIQUE CHECK (length(token_hash) > 0),
        created_by TEXT NOT NULL REFERENCES users(user_id),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        expires_at TEXT NOT NULL,
        consumed_by TEXT REFERENCES users(user_id),
        consumed_at TEXT,
        revoked_at TEXT,
        CHECK ((consumed_by IS NULL) = (consumed_at IS NULL))
    )""",
    """CREATE TABLE grants (
        grant_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(grant_id)) > 0),
        user_id TEXT NOT NULL REFERENCES users(user_id),
        provider TEXT NOT NULL CHECK (length(trim(provider)) > 0),
        provider_subject TEXT,
        version INTEGER NOT NULL DEFAULT 1 CHECK (typeof(version) = 'integer' AND version > 0),
        state TEXT NOT NULL DEFAULT 'pending',
        encrypted_payload BLOB,
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        UNIQUE (grant_id, user_id, provider)
    )""",
    "CREATE INDEX grants_by_owner_provider ON grants(user_id, provider)",
    """CREATE TABLE accounts (
        account_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(account_id)) > 0),
        user_id TEXT NOT NULL REFERENCES users(user_id),
        grant_id TEXT NOT NULL,
        game TEXT NOT NULL CHECK (length(trim(game)) > 0),
        channel TEXT NOT NULL CHECK (length(trim(channel)) > 0),
        server TEXT NOT NULL CHECK (length(trim(server)) > 0),
        provider TEXT NOT NULL CHECK (length(trim(provider)) > 0),
        account_uid TEXT NOT NULL CHECK (length(trim(account_uid)) > 0),
        is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (grant_id, user_id, provider) REFERENCES grants(grant_id, user_id, provider),
        UNIQUE (user_id, game, channel, server, provider, account_uid),
        UNIQUE (account_id, user_id, game, channel, server, provider)
    )""",
    "CREATE UNIQUE INDEX default_account_by_user_game ON accounts(user_id, game) WHERE is_default = 1",
    "CREATE INDEX accounts_by_grant ON accounts(grant_id, user_id, provider)",
    """CREATE TABLE roles (
        role_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(role_id)) > 0),
        account_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        game TEXT NOT NULL,
        channel TEXT NOT NULL,
        server TEXT NOT NULL,
        provider TEXT NOT NULL,
        game_uid TEXT NOT NULL CHECK (length(trim(game_uid)) > 0),
        display_name TEXT,
        is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (account_id, user_id, game, channel, server, provider)
            REFERENCES accounts(account_id, user_id, game, channel, server, provider),
        UNIQUE (account_id, game_uid)
    )""",
    "CREATE UNIQUE INDEX default_role_by_account ON roles(account_id) WHERE is_default = 1",
    "CREATE INDEX roles_by_owner ON roles(user_id, account_id)",
)


def migrate_cloud_schema(connection: sqlite3.Connection) -> int:
    """Upgrade atomically and return the supported schema version.

    Outside an existing transaction this commits only the migration. Inside a
    transaction a savepoint preserves caller changes and transaction ownership;
    foreign keys must already be enabled because SQLite cannot enable them there.
    Future versions are rejected rather than downgraded. No executescript is
    used, since its implicit commit would break rollback of earlier DDL.
    """
    nested = connection.in_transaction
    if not nested:
        connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise RuntimeError("Cloud migration requires enabled foreign keys before a transaction")

    if nested:
        connection.execute("SAVEPOINT cloud_schema_migration")
    else:
        connection.execute("BEGIN IMMEDIATE")
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        version = 0
        if exists:
            version = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
        file_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if max(version, file_version) > SCHEMA_VERSION:
            raise RuntimeError("Cloud database schema is newer than this application supports")
        if version < SCHEMA_VERSION:
            for statement in _STATEMENTS[int(bool(exists)):]:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))",
                (SCHEMA_VERSION,),
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        if nested:
            connection.execute("RELEASE SAVEPOINT cloud_schema_migration")
        else:
            connection.commit()
    except BaseException:
        if nested:
            connection.execute("ROLLBACK TO SAVEPOINT cloud_schema_migration")
            connection.execute("RELEASE SAVEPOINT cloud_schema_migration")
        else:
            connection.rollback()
        raise
    return SCHEMA_VERSION
