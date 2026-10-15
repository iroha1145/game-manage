"""Owned account management. Only validated provider responses create identities."""
from contextlib import contextmanager
import uuid

from game_assistant.identity.models import Principal
from .store import AccountNotFoundError, AccountStore


PROVIDER_GAMES = {'kuro': 'wuthering_waves', 'tajiduo': 'nte',
                  'hypergryph': 'endfield', 'skland': 'endfield'}


@contextmanager
def transaction(connection):
    nested = connection.in_transaction
    if nested:
        connection.execute('SAVEPOINT account_mutation')
    else:
        connection.execute('BEGIN IMMEDIATE')
    try:
        yield
        if nested:
            connection.execute('RELEASE SAVEPOINT account_mutation')
        else:
            connection.commit()
    except BaseException:
        if nested:
            connection.execute('ROLLBACK TO SAVEPOINT account_mutation')
            connection.execute('RELEASE SAVEPOINT account_mutation')
        else:
            connection.rollback()
        raise


def require_scope(principal, account_id, role_id, *, connection):
    return AccountStore(connection).resolve(principal, account_id, role_id)


class AccountService:
    def __init__(self, connection, credential_store, *, clear_private=None):
        self.connection, self.credentials = connection, credential_store
        self.clear_private = clear_private
        self._listeners = []

    def require_scope(self, principal, account_id, role_id):
        return require_scope(principal, account_id, role_id, connection=self.connection)

    def _user(self, principal):
        if not self.connection.execute('SELECT 1 FROM users WHERE user_id=? AND disabled_at IS NULL',
                                       (principal.user_id,)).fetchone():
            raise AccountNotFoundError()

    def list_accounts(self, principal):
        self._user(principal)
        rows = self.connection.execute(
            'SELECT a.account_id,a.grant_id,a.game,a.channel,a.server,a.provider,a.is_default,g.version,g.state '
            'FROM accounts a JOIN grants g ON g.grant_id=a.grant_id AND g.user_id=a.user_id '
            'WHERE a.user_id=? ORDER BY a.created_at,a.account_id', (principal.user_id,)).fetchall()
        result = []
        keys = ('account_id', 'grant_id', 'game', 'channel', 'server', 'provider', 'is_default', 'version', 'state')
        for row in rows:
            item = dict(zip(keys, row))
            item['roles'] = [dict(zip(('role_id', 'display_name', 'is_default'), r))
                             for r in self.connection.execute(
                                 'SELECT role_id,display_name,is_default FROM roles WHERE account_id=? AND user_id=?',
                                 (row[0], principal.user_id))]
            result.append(item)
        return result

    def describe(self, scope, *, active=True):
        self.require_scope(Principal(scope.user_id, False), scope.account_id, scope.role_id)
        row = self.connection.execute(
            'SELECT a.game,a.provider,a.grant_id,g.version,g.state,r.game_uid,a.server '
            'FROM accounts a JOIN grants g ON g.grant_id=a.grant_id JOIN roles r ON r.account_id=a.account_id '
            'WHERE a.account_id=? AND r.role_id=? AND a.user_id=?',
            (scope.account_id, scope.role_id, scope.user_id)).fetchone()
        if active and row[4] != 'active':
            raise AccountNotFoundError()
        return dict(zip(('game','provider','grant_id','version','state','game_uid','server'), row))

    def save_verified(self, principal, provider, credentials):
        """Internal-only: credentials are returned by a verified provider, never body UIDs."""
        self._user(principal)
        game = PROVIDER_GAMES[provider]
        subject_key = {'kuro': 'user_id', 'tajiduo': 'center_uid', 'hypergryph': 'uid', 'skland': 'user_id'}[provider]
        subject = str(credentials.get(subject_key) or '')
        role = str(credentials.get('role_id') or '')
        server = str(credentials.get('server_id') or ('official' if provider == 'tajiduo' else ''))
        if not subject or not role or not server:
            from game_assistant.auth.service import LoginError
            raise LoginError('社区未提供已验证的账号和角色标识', 502)
        if self.connection.in_transaction:
            raise RuntimeError('Account mutations require a dedicated idle connection')
        verified = credentials.get('_verified_roles',credentials.get('roles')) or [
            {'role_id':role,'server_id':server,'nickname':credentials.get('nickname')}]
        if not isinstance(verified,list) or any(not isinstance(item,dict) or not str(item.get('role_id') or '') or
                not str(item.get('server_id') or '') for item in verified):
            from game_assistant.auth.service import LoginError
            raise LoginError('社区角色资料格式不正确',502)
        credentials = {**credentials,'_verified_roles':verified}
        if not any(str(item['role_id'])==role and str(item['server_id'])==server for item in verified):
            from game_assistant.auth.service import LoginError
            raise LoginError('默认角色不在社区绑定列表中',502)
        with transaction(self.connection):
            old = self.connection.execute('SELECT grant_id FROM grants WHERE user_id=? AND provider=? AND provider_subject=? ORDER BY created_at LIMIT 1',
                                          (principal.user_id,provider,subject)).fetchone()
            if old:
                grant_id = old[0]
                self.connection.execute("UPDATE grants SET version=version+1,state='pending' WHERE grant_id=?", (grant_id,))
            else:
                grant_id = uuid.uuid4().hex
                self.connection.execute('INSERT INTO grants(grant_id,user_id,provider,provider_subject) VALUES(?,?,?,?)',
                                        (grant_id,principal.user_id,provider,subject))
            version = self.connection.execute('SELECT version FROM grants WHERE grant_id=?', (grant_id,)).fetchone()[0]
            self.credentials.save_grant(principal.user_id,grant_id,credentials,version)
            selected = None
            seen_servers = set()
            for item in verified:
                upstream_role,upstream_server = str(item['role_id']),str(item['server_id'])
                account = self.connection.execute('SELECT account_id FROM accounts WHERE user_id=? AND game=? AND channel=? AND server=? AND provider=? AND account_uid=?',
                                                  (principal.user_id,game,'official',upstream_server,provider,subject)).fetchone()
                account_id = account[0] if account else uuid.uuid4().hex
                if not account:
                    default = not self.connection.execute('SELECT 1 FROM accounts WHERE user_id=? AND game=? AND is_default=1',
                                                           (principal.user_id,game)).fetchone()
                    self.connection.execute('INSERT INTO accounts(account_id,user_id,grant_id,game,channel,server,provider,account_uid,is_default) VALUES(?,?,?,?,?,?,?,?,?)',
                                            (account_id,principal.user_id,grant_id,game,'official',upstream_server,provider,subject,int(default)))
                else:
                    self.connection.execute('UPDATE accounts SET grant_id=? WHERE account_id=?',(grant_id,account_id))
                role_row = self.connection.execute('SELECT role_id FROM roles WHERE account_id=? AND game_uid=?',(account_id,upstream_role)).fetchone()
                role_id = role_row[0] if role_row else uuid.uuid4().hex
                is_selected = upstream_role==role and upstream_server==server
                default = int(is_selected or upstream_server not in seen_servers)
                if default:
                    self.connection.execute('UPDATE roles SET is_default=0 WHERE account_id=?',(account_id,))
                if role_row:
                    self.connection.execute('UPDATE roles SET display_name=?,is_default=? WHERE role_id=?',(item.get('nickname'),default,role_id))
                else:
                    self.connection.execute('INSERT INTO roles(role_id,account_id,user_id,game,channel,server,provider,game_uid,display_name,is_default) VALUES(?,?,?,?,?,?,?,?,?,?)',
                                            (role_id,account_id,principal.user_id,game,'official',upstream_server,provider,upstream_role,item.get('nickname'),default))
                seen_servers.add(upstream_server)
                if is_selected:
                    selected = account_id,role_id
        self._changed(principal.user_id,grant_id)
        cleanup_pending = self._cleanup_after_commit(principal,grant_id) if old else False
        account_id,role_id = selected
        return {'ok': True, 'account_id': account_id, 'role_id': role_id, 'grant_id': grant_id, 'version': version,
                'cleanup_pending':cleanup_pending}

    def select_role(self, principal, account_id, role_id):
        self.require_scope(principal,account_id,role_id)
        with transaction(self.connection):
            self.connection.execute('UPDATE roles SET is_default=0 WHERE account_id=? AND user_id=?', (account_id,principal.user_id))
            self.connection.execute('UPDATE roles SET is_default=1 WHERE role_id=? AND account_id=? AND user_id=?', (role_id,account_id,principal.user_id))
        return {'ok': True, 'role_id': role_id}

    def _clear_grant(self, principal, grant_id):
        if self.clear_private is not None:
            for row in self.connection.execute('SELECT a.account_id,r.role_id FROM accounts a JOIN roles r ON r.account_id=a.account_id WHERE a.user_id=? AND a.grant_id=?',
                                               (principal.user_id,grant_id)):
                self.clear_private(self.require_scope(principal,*row))

    def _changed(self, user_id, grant_id):
        for callback in self._listeners:
            callback(user_id,grant_id)

    def _cleanup_after_commit(self,principal,grant_id):
        try:
            self._clear_grant(principal,grant_id)
            return False
        except Exception:
            # Independent private databases cannot share this SQLite transaction.
            # The grant remains unavailable even if cache cleanup needs a retry.
            with transaction(self.connection):
                self.connection.execute("UPDATE grants SET state=CASE WHEN state='revoked' THEN 'revoked_cleanup_pending' ELSE 'active_cleanup_pending' END WHERE user_id=? AND grant_id=?",
                                        (principal.user_id,grant_id))
            return True

    def revoke(self, principal, account_id):
        self._user(principal)
        row = self.connection.execute('SELECT grant_id FROM accounts WHERE user_id=? AND account_id=?',
                                      (principal.user_id,account_id)).fetchone()
        if row is None:
            raise AccountNotFoundError()
        grant_id = row[0]
        if self.connection.in_transaction:
            raise RuntimeError('Account mutations require a dedicated idle connection')
        with transaction(self.connection):
            self.connection.execute("UPDATE grants SET version=version+1,state='revoked',encrypted_payload=NULL,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE user_id=? AND grant_id=?",
                                    (principal.user_id,grant_id))
        self._changed(principal.user_id,grant_id)
        return {'ok': True,'cleanup_pending':self._cleanup_after_commit(principal,grant_id)}
