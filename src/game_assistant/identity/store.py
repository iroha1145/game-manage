"""Short-lived, foreign-key enabled connections to the separate cloud DB."""

from contextlib import contextmanager
from pathlib import Path
import sqlite3

from game_assistant.migrations.current import initialize_cloud_schema


class IdentityStore:
    def __init__(self, path: str):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            initialize_cloud_schema(connection)

    @contextmanager
    def connect(self, *, write=False):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            if write:
                connection.execute('BEGIN IMMEDIATE')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
