import sqlite3

import pytest

from game_assistant.accounts.models import AccountScope
from game_assistant.accounts.store import AccountNotFoundError, AccountStore
from game_assistant.identity.models import Principal
from game_assistant.migrations.cloud_v1 import migrate_cloud_schema


def add_user(connection, user_id):
    connection.execute(
        "INSERT INTO users (user_id, username, password_hash) VALUES (?, ?, ?)",
        (user_id, user_id, "test-password-hash"),
    )


def add_account(connection, user_id, account_id, role_id, *, provider="kuro",
                game="wuwa", channel="official", server="cn", game_uid="12345"):
    grant_id = f"grant-{account_id}"
    connection.execute(
        "INSERT INTO grants (grant_id, user_id, provider) VALUES (?, ?, ?)",
        (grant_id, user_id, provider),
    )
    connection.execute(
        """INSERT INTO accounts
           (account_id, user_id, grant_id, game, channel, server, provider, account_uid)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (account_id, user_id, grant_id, game, channel, server, provider, "same-account"),
    )
    connection.execute(
        """INSERT INTO roles
           (role_id, account_id, user_id, game, channel, server, provider, game_uid)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (role_id, account_id, user_id, game, channel, server, provider, game_uid),
    )


@pytest.fixture
def connection():
    with sqlite3.connect(":memory:") as database:
        assert migrate_cloud_schema(database) == 1
        add_user(database, "user-a")
        add_user(database, "user-b")
        add_account(database, "user-a", "account-a", "role-a")
        add_account(database, "user-b", "account-b", "role-b")
        database.commit()
        yield database


@pytest.mark.parametrize("is_admin", [False, True])
def test_scope_rejects_other_owner(connection, is_admin):
    store = AccountStore(connection)
    # Shared upstream UID must never substitute for the internal owner.
    assert store.resolve(Principal("user-a", is_admin), "account-a", "role-a") == (
        AccountScope("user-a", "account-a", "role-a")
    )
    assert store.resolve(Principal("user-b", False), "account-b", "role-b") == (
        AccountScope("user-b", "account-b", "role-b")
    )
    with pytest.raises(AccountNotFoundError) as other_owner:
        store.resolve(Principal("user-a", is_admin), "account-b", "role-b")
    with pytest.raises(AccountNotFoundError) as missing:
        store.resolve(Principal("user-a", is_admin), "missing", "missing")
    assert other_owner.value.code == missing.value.code == "account_not_found"
    assert str(other_owner.value) == str(missing.value)


def test_role_must_belong_to_account(connection):
    add_account(connection, "user-a", "account-a2", "role-a2", server="cn-2")
    store = AccountStore(connection)
    with pytest.raises(AccountNotFoundError):
        store.resolve(Principal("user-a", False), "account-a", "role-a2")


@pytest.mark.parametrize("field, value", [
    ("user_id", "user-b"), ("game", "nte"), ("channel", "bilibili"),
    ("server", "other"), ("provider", "other"), ("account_id", "missing"),
])
def test_database_rejects_role_identity_outside_account(connection, field, value):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(f"UPDATE roles SET {field} = ? WHERE role_id = 'role-a'", (value,))


@pytest.mark.parametrize("field, value", [("user_id", "user-b"), ("provider", "other")])
def test_database_rejects_grant_outside_account_owner_and_provider(connection, field, value):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(f"UPDATE accounts SET {field} = ? WHERE account_id = 'account-a'", (value,))


def test_account_identity_includes_all_source_dimensions(connection):
    for index, overrides in enumerate([
        {"game": "nte"}, {"channel": "bilibili"}, {"server": "cn-2"},
        {"provider": "second-provider"},
    ]):
        add_account(connection, "user-a", f"account-{index}", f"role-{index}", **overrides)
    with pytest.raises(sqlite3.IntegrityError):
        add_account(connection, "user-a", "duplicate-account", "duplicate-role")


def test_role_uid_is_unique_within_account(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """INSERT INTO roles
               (role_id, account_id, user_id, game, channel, server, provider, game_uid)
               VALUES ('duplicate', 'account-a', 'user-a', 'wuwa', 'official', 'cn', 'kuro', '12345')"""
        )


def test_endfield_authorizations_and_roles_remain_separate(connection):
    add_account(connection, "user-a", "endfield-draw", "draw-role", game="endfield", provider="hypergryph")
    add_account(connection, "user-a", "endfield-profile", "profile-role", game="endfield", provider="skland")
    store = AccountStore(connection)
    assert store.resolve(Principal("user-a", False), "endfield-draw", "draw-role").role_id == "draw-role"
    with pytest.raises(AccountNotFoundError):
        store.resolve(Principal("user-a", False), "endfield-draw", "profile-role")


def test_default_account_is_unique_per_user_and_game(connection):
    add_account(connection, "user-a", "account-a2", "role-a2", server="cn-2")
    connection.execute("UPDATE accounts SET is_default = 1 WHERE account_id = 'account-a'")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE accounts SET is_default = 1 WHERE account_id = 'account-a2'")
    connection.execute("UPDATE accounts SET is_default = 1 WHERE account_id = 'account-b'")


def test_default_role_is_unique_per_account(connection):
    connection.execute(
        """INSERT INTO roles
           (role_id, account_id, user_id, game, channel, server, provider, game_uid)
           VALUES ('role-a2', 'account-a', 'user-a', 'wuwa', 'official', 'cn', 'kuro', '54321')"""
    )
    connection.execute("UPDATE roles SET is_default = 1 WHERE role_id = 'role-a'")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE roles SET is_default = 1 WHERE role_id = 'role-a2'")


def test_migration_is_atomic(tmp_path):
    path = tmp_path / "cloud.sqlite"
    with sqlite3.connect(path) as database:
        database.execute("CREATE TABLE legacy (value TEXT)")
        database.execute("INSERT INTO legacy VALUES ('preserved')")
        database.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        database.execute("INSERT INTO schema_migrations VALUES (0, 'baseline')")
        database.commit()

        def deny_roles(action, arg1, arg2, schema, source):
            if action == sqlite3.SQLITE_CREATE_TABLE and arg1 == "roles":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        database.set_authorizer(deny_roles)
        with pytest.raises(sqlite3.DatabaseError):
            migrate_cloud_schema(database)
        database.set_authorizer(None)
        assert not database.in_transaction

    with sqlite3.connect(path) as reopened:
        assert reopened.execute("SELECT * FROM legacy").fetchall() == [("preserved",)]
        assert reopened.execute("SELECT * FROM schema_migrations").fetchall() == [(0, "baseline")]
        assert reopened.execute("PRAGMA user_version").fetchone() == (0,)
        assert reopened.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall() == [
            ("legacy",), ("schema_migrations",),
        ]
        assert migrate_cloud_schema(reopened) == 1


def test_schema_upgrade_is_idempotent(tmp_path):
    path = tmp_path / "cloud.sqlite"
    with sqlite3.connect(path) as database:
        assert migrate_cloud_schema(database) == 1
        add_user(database, "user-a")
        add_account(database, "user-a", "account-a", "role-a")
        database.commit()
        before = list(database.iterdump())
        assert migrate_cloud_schema(database) == 1
        assert list(database.iterdump()) == before
    with sqlite3.connect(path) as reopened:
        assert migrate_cloud_schema(reopened) == 1
        assert reopened.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert reopened.execute("SELECT count(*) FROM schema_migrations WHERE version = 1").fetchone() == (1,)
        assert AccountStore(reopened).resolve(Principal("user-a", False), "account-a", "role-a") == (
            AccountScope("user-a", "account-a", "role-a")
        )


def test_migration_preserves_caller_transaction(connection):
    add_user(connection, "uncommitted-user")
    assert migrate_cloud_schema(connection) == 1
    assert connection.in_transaction
    connection.rollback()
    assert connection.execute("SELECT 1 FROM users WHERE user_id = 'uncommitted-user'").fetchone() is None


def test_migration_rejects_transaction_without_foreign_keys():
    with sqlite3.connect(":memory:") as database:
        database.execute("CREATE TABLE legacy (value TEXT)")
        database.execute("INSERT INTO legacy VALUES ('pending')")
        with pytest.raises(RuntimeError, match="foreign keys"):
            migrate_cloud_schema(database)
        assert database.in_transaction
        database.rollback()


def test_migration_rejects_future_schema_without_downgrade(connection):
    connection.execute("INSERT INTO schema_migrations (version) VALUES (2)")
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    with pytest.raises(RuntimeError, match="newer"):
        migrate_cloud_schema(connection)
    assert connection.execute("PRAGMA user_version").fetchone() == (2,)


def test_sessions_invites_and_grants_enforce_user_references(connection):
    statements = [
        "INSERT INTO sessions (session_id, user_id, token_hash, csrf_token_hash, expires_at) VALUES ('s', 'missing', 'hash', 'csrf', '2026-10-13T00:00:00Z')",
        "INSERT INTO invites (invite_id, token_hash, created_by, expires_at) VALUES ('i', 'hash', 'missing', '2026-10-13T00:00:00Z')",
        "INSERT INTO grants (grant_id, user_id, provider) VALUES ('g', 'missing', 'kuro')",
    ]
    for statement in statements:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(statement)


def test_grant_versions_are_positive(connection):
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE grants SET version = 0 WHERE grant_id = 'grant-account-a'")


def test_resolve_rejects_disabled_user(connection):
    connection.execute("UPDATE users SET disabled_at = '2026-10-12T00:00:00Z' WHERE user_id = 'user-a'")
    with pytest.raises(AccountNotFoundError):
        AccountStore(connection).resolve(Principal("user-a", False), "account-a", "role-a")
