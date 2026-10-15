"""Invitation-only website identities; secrets are random and stored as digests."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from uuid import uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from .models import Principal


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def session_csrf(token: str) -> str:
    # Domain separation prevents token disclosure; stable across tabs/restarts.
    return hmac.new(token.encode(), b'game-assistant:website-csrf:v1', hashlib.sha256).hexdigest()


def timestamp(seconds=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


class IdentityError(Exception):
    def __init__(self, code, status_code=400):
        self.code, self.status_code = code, status_code
        super().__init__(code)


@dataclass(frozen=True)
class Session:
    principal: Principal
    session_id: str
    token: str


class IdentityService:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings
        # 19 MiB / 2 iterations / 1 lane; bounded memory for the small server.
        self.hasher = PasswordHasher(type=Type.ID, memory_cost=19456, time_cost=2, parallelism=1)
        self._dummy_hash = self.hasher.hash(secrets.token_urlsafe(24))

    @staticmethod
    def _username(username):
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', username):
            raise IdentityError('invalid_username')
        return username.lower()

    @staticmethod
    def _password(password):
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise IdentityError('invalid_password')
        return password

    @staticmethod
    def _admin(db, principal):
        row = db.execute('SELECT is_admin FROM users WHERE user_id=? AND disabled_at IS NULL', (principal.user_id,)).fetchone()
        if row is None or not row['is_admin']:
            raise IdentityError('admin_required', 403)

    def bootstrap_admin(self, username, password):
        username = self._username(username)
        password_hash = self.hasher.hash(self._password(password))
        principal = Principal(str(uuid4()), True)
        with self.store.connect(write=True) as db:
            if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                raise IdentityError('bootstrap_already_complete', 409)
            db.execute('INSERT INTO users(user_id,username,password_hash,is_admin) VALUES(?,?,?,1)',
                       (principal.user_id, username, password_hash))
        return principal

    def create_invite(self, admin):
        token = secrets.token_urlsafe(32)
        with self.store.connect(write=True) as db:
            self._admin(db, admin)
            db.execute('INSERT INTO invites(invite_id,token_hash,created_by,expires_at) VALUES(?,?,?,?)',
                       (str(uuid4()), digest(token), admin.user_id, timestamp(self.settings.cloud_invite_seconds)))
        return token

    def create_recovery(self, admin, user_id):
        token, now = secrets.token_urlsafe(32), timestamp()
        with self.store.connect(write=True) as db:
            self._admin(db, admin)
            if not db.execute('SELECT 1 FROM users WHERE user_id=? AND disabled_at IS NULL', (user_id,)).fetchone():
                raise IdentityError('user_not_found', 404)
            db.execute('UPDATE recoveries SET revoked_at=? WHERE user_id=? AND consumed_at IS NULL', (now, user_id))
            db.execute('INSERT INTO recoveries(recovery_id,token_hash,user_id,created_by,created_at,expires_at) VALUES(?,?,?,?,?,?)',
                       (str(uuid4()), digest(token), user_id, admin.user_id, now, timestamp(self.settings.cloud_recovery_seconds)))
        return token

    def _limit(self, kind, account, source, maximum=10):
        now = int(time.time())
        # Digest account/IP so the limiter does not become a plaintext identity log.
        keys = [kind + ':account:' + digest(account), kind + ':ip:' + digest(source)]
        limited = False
        with self.store.connect(write=True) as db:
            db.execute('DELETE FROM identity_rate_limits WHERE window_start<?', (now - 600,))
            for key in keys:
                row = db.execute('SELECT attempts FROM identity_rate_limits WHERE bucket=?', (key,)).fetchone()
                if row is not None and row['attempts'] >= maximum:
                    limited = True
            if not limited:
                for key in keys:
                    db.execute('''INSERT INTO identity_rate_limits(bucket,window_start,attempts) VALUES(?,?,1)
                                  ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1''', (key, now))
        if limited:
            raise IdentityError('rate_limited', 429)

    def _new_session(self, db, principal, old_token=None):
        if old_token:
            db.execute('UPDATE sessions SET revoked_at=? WHERE token_hash=?', (timestamp(), digest(old_token)))
        token, session_id = secrets.token_urlsafe(32), str(uuid4())
        db.execute('INSERT INTO sessions(session_id,user_id,token_hash,csrf_token_hash,expires_at) VALUES(?,?,?,?,?)',
                   (session_id, principal.user_id, digest(token), digest(session_csrf(token)),
                    timestamp(self.settings.cloud_session_seconds)))
        return Session(principal, session_id, token)

    def register(self, username, password, invite, source, old_token=None):
        username = self._username(username)
        self._limit('register', username, source)
        password_hash = self.hasher.hash(self._password(password))
        principal = Principal(str(uuid4()), False)
        try:
            with self.store.connect(write=True) as db:
                row = db.execute('''SELECT invite_id FROM invites WHERE token_hash=? AND consumed_at IS NULL
                                    AND revoked_at IS NULL AND expires_at>?''', (digest(invite), timestamp())).fetchone()
                if row is None:
                    raise IdentityError('invalid_invite')
                db.execute('INSERT INTO users(user_id,username,password_hash) VALUES(?,?,?)', (principal.user_id, username, password_hash))
                db.execute('UPDATE invites SET consumed_by=?,consumed_at=? WHERE invite_id=?', (principal.user_id, timestamp(), row['invite_id']))
                return self._new_session(db, principal, old_token)
        except sqlite3.IntegrityError:
            raise IdentityError('registration_unavailable') from None

    def login(self, username, password, source, old_token=None):
        username = self._username(username)
        self._limit('login', username, source)
        with self.store.connect() as db:
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        password_hash = user['password_hash'] if user is not None else self._dummy_hash
        try:
            valid = self.hasher.verify(password_hash, self._password(password))
        except (VerificationError, InvalidHashError, IdentityError):
            valid = False
        if not valid or user is None or user['disabled_at'] is not None:
            raise IdentityError('invalid_credentials', 401)
        with self.store.connect(write=True) as db:
            current = db.execute('SELECT * FROM users WHERE user_id=? AND disabled_at IS NULL', (user['user_id'],)).fetchone()
            if current is None or current['password_hash'] != password_hash:
                raise IdentityError('invalid_credentials', 401)
            if self.hasher.check_needs_rehash(password_hash):
                db.execute('UPDATE users SET password_hash=? WHERE user_id=?', (self.hasher.hash(password), user['user_id']))
            return self._new_session(db, Principal(user['user_id'], bool(user['is_admin'])), old_token)

    def authenticate(self, token):
        if not token:
            return None
        with self.store.connect() as db:
            row = db.execute('''SELECT s.session_id,u.user_id,u.is_admin FROM sessions s JOIN users u ON u.user_id=s.user_id
                                WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?
                                AND u.disabled_at IS NULL''', (digest(token), timestamp())).fetchone()
        return Session(Principal(row['user_id'], bool(row['is_admin'])), row['session_id'], token) if row else None

    def csrf(self, session_token=None, preauth_token=None, source='unknown'):
        session = self.authenticate(session_token)
        if session:
            return session_csrf(session.token), None
        if not session:
            self._limit('csrf', source, source, maximum=60)
        csrf = secrets.token_urlsafe(32)
        with self.store.connect(write=True) as db:
            token = secrets.token_urlsafe(32)
            if preauth_token:
                db.execute('DELETE FROM preauth_sessions WHERE token_hash=?', (digest(preauth_token),))
            db.execute('DELETE FROM preauth_sessions WHERE expires_at<=?', (timestamp(),))
            db.execute('INSERT INTO preauth_sessions VALUES(?,?,?)', (digest(token), digest(csrf), timestamp(900)))
        return csrf, token

    def check_csrf(self, session, preauth_token, csrf, *, preauth=False):
        with self.store.connect() as db:
            if session:
                row = db.execute('SELECT csrf_token_hash FROM sessions WHERE session_id=? AND revoked_at IS NULL AND expires_at>?',
                                 (session.session_id, timestamp())).fetchone()
            elif preauth and preauth_token:
                row = db.execute('SELECT csrf_token_hash FROM preauth_sessions WHERE token_hash=? AND expires_at>?',
                                 (digest(preauth_token), timestamp())).fetchone()
            else:
                raise IdentityError('authentication_required', 401)
        if not row:
            raise IdentityError('authentication_required', 401)
        if not csrf or not hmac.compare_digest(row['csrf_token_hash'], digest(csrf)):
            raise IdentityError('csrf_required', 403)

    def consume_preauth(self, token):
        if token:
            with self.store.connect(write=True) as db:
                db.execute('DELETE FROM preauth_sessions WHERE token_hash=?', (digest(token),))

    def recover(self, recovery, password, source):
        self._limit('recover', digest(recovery), source)
        password_hash = self.hasher.hash(self._password(password))
        now = timestamp()
        with self.store.connect(write=True) as db:
            row = db.execute('''SELECT r.recovery_id,r.user_id FROM recoveries r JOIN users u ON u.user_id=r.user_id
                                WHERE r.token_hash=? AND r.consumed_at IS NULL AND r.revoked_at IS NULL
                                AND r.expires_at>? AND u.disabled_at IS NULL''', (digest(recovery), now)).fetchone()
            if row is None:
                raise IdentityError('invalid_recovery')
            db.execute('UPDATE users SET password_hash=? WHERE user_id=?', (password_hash, row['user_id']))
            db.execute('UPDATE recoveries SET consumed_at=? WHERE recovery_id=?', (now, row['recovery_id']))
            db.execute('UPDATE recoveries SET revoked_at=? WHERE user_id=? AND consumed_at IS NULL AND revoked_at IS NULL',
                       (now, row['user_id']))
            db.execute('UPDATE sessions SET revoked_at=? WHERE user_id=?', (now, row['user_id']))

    def sessions(self, principal):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute('''SELECT session_id,created_at,expires_at FROM sessions
                      WHERE user_id=? AND revoked_at IS NULL AND expires_at>? ORDER BY created_at''',
                      (principal.user_id, timestamp()))]

    def revoke(self, principal, session_id):
        with self.store.connect(write=True) as db:
            changed = db.execute('UPDATE sessions SET revoked_at=? WHERE user_id=? AND session_id=?',
                                 (timestamp(), principal.user_id, session_id)).rowcount
            if not changed:
                raise IdentityError('session_not_found', 404)
