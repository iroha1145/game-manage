"""One-time CurrentUser DPAPI key copy; no plaintext file, key hash or secret logs."""
import argparse
import ctypes
from ctypes import wintypes
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid

from scripts.cloud.local_pull import SSHTransport, prepare_root, safe_path

KEY_ROOT = 'C:/Zcode/game-manage-cloud-backups/key'
BLOB_NAME = 'grants.key.dpapi'
MAX_CIPHER_BYTES = 8192
REMOTE = b'''
import os, pathlib, pwd, stat, sys
try:
    path = pathlib.Path('/etc/game-manage-cloud-trial/grants.key')
    allowed = {0, pwd.getpwnam('game-manage-trial').pw_uid}
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid not in allowed or info.st_mode & 0o022:
            raise ValueError('unsafe_parent')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid not in allowed or info.st_mode & 0o077 or info.st_size != 32 or info.st_nlink != 1:
            raise ValueError('unsafe_key')
        value = os.read(fd, 33)
        if len(value) != 32:
            raise ValueError('invalid_key')
        os.write(sys.stdout.fileno(), value)
    finally:
        os.close(fd)
except Exception:
    sys.exit(2)
'''


def wipe(value):
    if value:
        ctypes.memset((ctypes.c_ubyte * len(value)).from_buffer(value), 0, len(value))


def dpapi(value, *, decrypt=False):
    if os.name != 'nt' or not value or len(value) > MAX_CIPHER_BYTES:
        raise ValueError('dpapi_input_invalid')
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = (ctypes.c_ubyte * len(value)).from_buffer(value)
    source, target = Blob(len(value), buffer), Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    # UI_FORBIDDEN only; never LOCAL_MACHINE. DPAPI binds to the current user.
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('dpapi_failed')
    try:
        if not 0 < target.size <= MAX_CIPHER_BYTES:
            raise ValueError('dpapi_output_invalid')
        output = bytearray(target.size)
        ctypes.memmove((ctypes.c_ubyte * len(output)).from_buffer(output), target.data, target.size)
        return output
    finally:
        ctypes.memset(target.data, 0, target.size)
        kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


def fetch_key():
    transport = SSHTransport()
    process = subprocess.Popen(transport.base + ['sudo -n /usr/bin/python3 -'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    timer = threading.Timer(60, process.kill)
    timer.start()
    buffer = bytearray(33)
    try:
        process.stdin.write(REMOTE)
        process.stdin.close()
        size = 0
        while size < len(buffer):
            read = process.stdout.readinto(memoryview(buffer)[size:])
            if not read:
                break
            size += read
        if size != 32 or process.wait(timeout=5) != 0:
            raise ValueError('key_transfer_failed')
        return buffer[:32]
    finally:
        wipe(buffer)
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def check_cipher(path, expected=None):
    path = safe_path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_CIPHER_BYTES:
        raise ValueError('cipher_invalid')
    cipher = bytearray(path.read_bytes())
    plaintext = dpapi(cipher, decrypt=True)
    try:
        if len(plaintext) != 32 or expected is not None and not hmac.compare_digest(plaintext, expected):
            raise ValueError('roundtrip_failed')
        return len(plaintext)
    finally:
        wipe(plaintext)


def prepare_key_root(value):
    root = safe_path(value)
    if root.exists() and any(entry.name != BLOB_NAME for entry in root.iterdir()):
        raise ValueError('unmanaged_key_root')
    return prepare_root(root, allowed_files=(BLOB_NAME,))


def save(root, fetch=fetch_key):
    root = prepare_key_root(root)
    destination = safe_path(root / BLOB_NAME)
    if destination.exists():
        raise ValueError('destination_exists')  # No second server read, ever.
    raw = fetch()
    try:
        if not isinstance(raw, bytearray) or len(raw) != 32:
            raise ValueError('key_length_invalid')
        cipher = dpapi(raw)
        decoded = dpapi(cipher, decrypt=True)
        try:
            if not hmac.compare_digest(decoded, raw):
                raise ValueError('roundtrip_failed')
        finally:
            wipe(decoded)
        stage = root / ('.pending-key-' + uuid.uuid4().hex[:12] + '.dpapi')
        # Only ciphertext reaches the filesystem, even in an interrupted stage.
        with stage.open('xb') as output:
            output.write(cipher)
            output.flush()
            os.fsync(output.fileno())
        length = check_cipher(stage, raw)
        safe_path(destination)
        os.rename(stage, destination)  # Windows atomic no-replace.
        prepare_key_root(root)
        return {'status': 'saved', 'verified': True, 'plaintext_bytes': length,
                'ciphertext_bytes': len(cipher), 'scope': 'CurrentUser', 'path': str(destination)}
    finally:
        if isinstance(raw, bytearray):
            wipe(raw)


def verify(root):
    if not safe_path(root).is_dir():
        raise ValueError('key_root_missing')
    root = prepare_key_root(root)
    destination = safe_path(root / BLOB_NAME)
    length = check_cipher(destination)
    return {'status': 'verified', 'verified': True, 'plaintext_bytes': length,
            'ciphertext_bytes': destination.stat().st_size, 'scope': 'CurrentUser', 'path': str(destination)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--execute', action='store_true')
    action.add_argument('--verify', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = save(KEY_ROOT) if args.execute else verify(KEY_ROOT) if args.verify else {
            'status': 'explicit_action_required', 'scope': 'CurrentUser'}
        print(json.dumps(result))
        return 0
    except Exception:
        print('local_key_backup_failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
