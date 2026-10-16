"""Shared local-only probe storage and deliberately small evidence output."""
from __future__ import annotations

import asyncio
import csv
import ctypes
import getpass
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import warnings

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


def emit(step: str, status: str, elapsed_ms: int = 0, error_type: str | None = None):
    # No arbitrary strings/response bodies/identifiers accepted as evidence.
    if not re.fullmatch(r'[a-z0-9_.]+', step) or status not in {'passed', 'failed', 'untested'}:
        raise ValueError('invalid evidence')
    row = {'step': step, 'status': status, 'elapsed_ms': elapsed_ms}
    if error_type is not None:
        row['error_type'] = error_type if re.fullmatch(r'[A-Za-z0-9_]+', error_type) else 'ProbeError'
    print(json.dumps(row, ensure_ascii=True), flush=True)


async def measure(step, operation, timeout=60):
    started = time.monotonic()
    try:
        await asyncio.wait_for(operation(), timeout)
    except Exception as error:
        emit(step, 'failed', round((time.monotonic() - started) * 1000), type(error).__name__)
        return False
    emit(step, 'passed', round((time.monotonic() - started) * 1000))
    return True


def quiet_logging():
    # Third-party exception/debug logs can contain response bodies and credentials.
    logging.disable(sys.maxsize)


def secret_input(prompt):
    if not sys.stdin.isatty():
        raise ValueError('interactive terminal required')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        value = getpass.getpass(prompt).strip()
    if not value or len(value) > 8192 or any(ord(c) < 32 for c in value):
        raise ValueError('invalid input')
    return value


def owner_only(path: Path, directory=False):
    if os.name != 'nt':
        os.chmod(path, 0o700 if directory else 0o600)
        return
    # Replace the DACL rather than only removing inherited ACEs. Fail closed.
    sid = next(csv.reader(io.StringIO(subprocess.check_output(
        ['whoami', '/user', '/fo', 'csv', '/nh'], text=True))))[1]
    if not re.fullmatch(r'S-1-[0-9-]+', sid):
        raise ValueError('invalid owner SID')
    from ctypes import wintypes
    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    descriptor = ctypes.c_void_p()
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                                                          ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    advapi.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    flags = 'OICI' if directory else ''
    if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        f'D:P(A;{flags};FA;;;{sid})', 1, ctypes.byref(descriptor), None):
        raise OSError('permission setup failed')
    try:
        if not advapi.SetFileSecurityW(str(path), 0x80000004, descriptor):
            raise OSError('permission setup failed')
    finally:
        kernel.LocalFree(descriptor)


def safe_path(path):
    from game_assistant.paths import through_link
    path = Path(path).absolute()
    if through_link(path):
        raise ValueError('symlink or junction not allowed')
    if not path.name.endswith('.credentials.json'):
        raise ValueError('use ignored credentials filename')
    # Only this deliberately named private directory can have its DACL replaced.
    # An arbitrary Documents/home/workspace parent must never be chmod/ACL'ed.
    if path.parent.name != '.private-cloud-probes':
        raise ValueError('dedicated private directory required')
    return path


def save_config(path, data, replace=False):
    from game_assistant.auth.store import CredentialStore
    path = safe_path(path)
    if path.exists() and not replace:
        raise FileExistsError('configuration exists')
    path.parent.mkdir(parents=True, exist_ok=True)
    owner_only(path.parent, directory=True)
    CredentialStore(path).save(data)
    owner_only(path)
    key = path.with_suffix(path.suffix + '.key')
    if key.exists():
        owner_only(key)


def load_config(path):
    from game_assistant.auth.store import CredentialStore
    path = safe_path(path)
    if not path.is_file():
        raise FileNotFoundError('configuration missing')
    owner_only(path.parent, directory=True)
    owner_only(path)
    return CredentialStore(path).load()
