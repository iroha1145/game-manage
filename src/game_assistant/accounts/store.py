"""SQLite account ownership resolution; no credential reads or HTTP coupling."""

import sqlite3

from game_assistant.identity.models import Principal

from .models import AccountScope


class AccountNotFoundError(LookupError):
    """Map missing and inaccessible objects to the same HTTP 404 upstream."""

    code = "account_not_found"

    def __init__(self) -> None:
        super().__init__("Account scope not found")


class AccountStore:
    """Use a cloud connection initialized by migrate_cloud_schema.

    The caller owns the connection and its transactions. Administrators have
    no bypass to private game data. Authentication must supply the Principal;
    a request body containing user_id is not a trusted identity.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def resolve(self, principal: Principal, account_id: str, role_id: str) -> AccountScope:
        row = self.connection.execute(
            """SELECT a.user_id, a.account_id, r.role_id
               FROM accounts AS a
               JOIN users AS u ON u.user_id = a.user_id
               JOIN roles AS r ON r.account_id = a.account_id
                 AND r.user_id = a.user_id AND r.game = a.game
                 AND r.channel = a.channel AND r.server = a.server
                 AND r.provider = a.provider
               JOIN grants AS g ON g.grant_id = a.grant_id
                 AND g.user_id = a.user_id AND g.provider = a.provider
               WHERE a.user_id = ? AND a.account_id = ? AND r.role_id = ?
                 AND u.disabled_at IS NULL""",
            (principal.user_id, account_id, role_id),
        ).fetchone()
        if row is None:
            raise AccountNotFoundError()
        return AccountScope(row[0], row[1], row[2])
