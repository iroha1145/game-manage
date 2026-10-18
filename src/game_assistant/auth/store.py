"""Atomic credential storage, encrypted for the current Windows user with DPAPI.

On other platforms AES-GCM uses a separate owner-only local key file. The key
must be backed up together with the ciphertext. No secrets are logged.
"""
import ctypes
import json
import os
import tempfile
from pathlib import Path


class CredentialStoreError(Exception):
    pass


def _dpapi(data: bytes, decrypt: bool = False) -> bytes:
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_byte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p,
                         ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise CredentialStoreError('本地凭据无法解密或保存，请使用原 Windows 用户重新登录')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class CredentialStore:
    def __init__(self, path, *, connection=None, key_path=None):
        self.path = Path(path)
        self.connection = connection
        self.key_path = Path(key_path) if key_path is not None else None

    def _grant_key(self):
        # Cloud keys are provisioned explicitly; never generate a replacement.
        if self.key_path is None:
            raise CredentialStoreError('授权密钥不可用')
        try:
            if self.key_path.is_symlink():
                raise ValueError('symlink')
            if os.name != 'nt' and self.key_path.stat().st_mode & 0o077:
                raise ValueError('permissions')
            key = self.key_path.read_bytes()
            if len(key) != 32:
                raise ValueError('key length')
            return key
        except Exception:
            raise CredentialStoreError('授权密钥不可用') from None

    @staticmethod
    def _binding(user_id, grant_id, version):
        return json.dumps(['cloud-grant-v1', user_id, grant_id, version],
                          separators=(',', ':')).encode()

    def seal_grant(self, user_id, grant_id, credentials, version):
        try:
            from Crypto.Cipher import AES
            if not isinstance(credentials, dict) or type(version) is not int or version < 1:
                raise ValueError('invalid grant')
            cipher = AES.new(self._grant_key(), AES.MODE_GCM, nonce=os.urandom(16))
            cipher.update(self._binding(user_id, grant_id, version))
            body, tag = cipher.encrypt_and_digest(json.dumps(credentials, ensure_ascii=False).encode())
            return b'GRANT1\n' + cipher.nonce + tag + body
        except Exception:
            raise CredentialStoreError('授权凭据保存失败') from None

    def load_grant(self, user_id: str, grant_id: str) -> dict:
        try:
            row = self.connection.execute(
                'SELECT g.version,g.encrypted_payload,g.provider FROM grants g JOIN users u ON u.user_id=g.user_id '
                "WHERE g.user_id=? AND g.grant_id=? AND g.state='active' AND u.disabled_at IS NULL",
                (user_id, grant_id)).fetchone()
            if row is None:
                raise ValueError('grant unavailable')
            version, raw, provider = row
            if not isinstance(raw, bytes) or not raw.startswith(b'GRANT1\n'):
                raise ValueError('envelope')
            from Crypto.Cipher import AES
            cipher = AES.new(self._grant_key(), AES.MODE_GCM, nonce=raw[7:23])
            cipher.update(self._binding(user_id, grant_id, version))
            data = json.loads(cipher.decrypt_and_verify(raw[39:], raw[23:39]))
            if not isinstance(data, dict):
                raise ValueError('payload')
            if data.get('_parent') is not None:
                if provider != 'skland':
                    raise ValueError('invalid parent provider')
                self.validate_parent(user_id, data['_parent'])
            return data
        except Exception:
            raise CredentialStoreError('授权凭据不可用，请重新授权') from None

    def validate_parent(self, user_id, parent):
        """A derived grant is usable only while its exact owned authorization exists."""
        if not isinstance(parent, dict):
            raise CredentialStoreError('来源授权不可用')
        row = self.connection.execute(
            "SELECT g.grant_id,g.provider_subject,r.game_uid,a.server,a.channel FROM accounts a "
            "JOIN roles r ON r.account_id=a.account_id AND r.user_id=a.user_id "
            "AND r.provider=a.provider AND r.game=a.game AND r.channel=a.channel AND r.server=a.server "
            "JOIN grants g ON g.grant_id=a.grant_id AND g.user_id=a.user_id "
            "WHERE a.user_id=? AND a.account_id=? AND r.role_id=? AND a.provider='hypergryph' "
            "AND g.provider='hypergryph' AND g.state='active'",
            (user_id, parent.get('account_id'), parent.get('role_id'))).fetchone()
        if row is None or tuple(row[:4]) != tuple(parent.get(k) for k in ('grant_id','subject','game_uid','server')) or row[4] != parent.get('channel', 'official'):
            raise CredentialStoreError('来源授权已改变')
        credentials = self.load_grant(user_id, row[0])
        # Legacy cloud grants need no re-login or mutation. Reauthorization replaces this marker.
        identity = credentials.get('_authorization_id') or 'legacy:' + row[0]
        from game_assistant.accounts.identities import has_verified_role
        if str(credentials.get('uid') or '') != row[1] or credentials.get('_parent') or identity != parent.get('authorization_id') or not has_verified_role(
                credentials, row[2], row[3], row[4]):
            raise CredentialStoreError('来源授权已改变')
        return credentials

    def save_grant(self, user_id: str, grant_id: str, credentials: dict, version: int) -> None:
        sealed = self.seal_grant(user_id, grant_id, credentials, version)
        from game_assistant.accounts.service import transaction
        try:
            with transaction(self.connection):
                cursor = self.connection.execute(
                    "UPDATE grants SET encrypted_payload=?,state='active',updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                    "WHERE user_id=? AND grant_id=? AND version=? AND state IN ('pending','active') "
                    'AND EXISTS(SELECT 1 FROM users WHERE user_id=? AND disabled_at IS NULL)',
                    (sealed, user_id, grant_id, version, user_id))
                if cursor.rowcount != 1:
                    raise CredentialStoreError('授权版本已失效')
        except CredentialStoreError:
            raise
        except Exception:
            raise CredentialStoreError('授权凭据保存失败') from None

    def _key(self, create=False):
        key_path = self.path.with_suffix(self.path.suffix + '.key')
        if create and not key_path.exists():
            try:
                fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, 'wb') as file:
                    file.write(os.urandom(32))
        return key_path.read_bytes()

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            raw = self.path.read_bytes()
            if raw.startswith(b'DPAPI1\n') and os.name == 'nt':
                plain = _dpapi(raw[7:], decrypt=True)
            elif raw.startswith(b'AESGCM1\n'):
                from Crypto.Cipher import AES
                nonce, tag, body = raw[8:24], raw[24:40], raw[40:]
                plain = AES.new(self._key(), AES.MODE_GCM, nonce=nonce).decrypt_and_verify(body, tag)
            else:
                raise ValueError('unsupported store')
            data = json.loads(plain)
            if not isinstance(data, dict) or any(not isinstance(v, dict) for v in data.values()):
                raise ValueError('invalid store')
            return data
        except Exception:
            raise CredentialStoreError('本地凭据文件无法读取，请检查文件及当前系统用户') from None

    def save(self, accounts: dict) -> None:
        temp = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            plain = json.dumps(accounts, ensure_ascii=False).encode('utf-8')
            if os.name == 'nt':
                sealed = b'DPAPI1\n' + _dpapi(plain)
            else:
                from Crypto.Cipher import AES
                cipher = AES.new(self._key(create=True), AES.MODE_GCM)
                body, tag = cipher.encrypt_and_digest(plain)
                sealed = b'AESGCM1\n' + cipher.nonce + tag + body
            fd, temp = tempfile.mkstemp(dir=self.path.parent, prefix='.credentials-')
            with os.fdopen(fd, 'wb') as file:
                file.write(sealed)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.path)
        except Exception:
            raise CredentialStoreError('本地凭据保存失败，原登录状态已保留') from None
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)
