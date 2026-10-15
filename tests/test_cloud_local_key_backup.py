import json
import os
import sys
from types import SimpleNamespace

import pytest

from scripts.cloud import local_key_backup as keys
from scripts.cloud import local_pull

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows CurrentUser DPAPI and NTFS ACL only')


def test_current_user_dpapi_roundtrip_without_plaintext_file(tmp_path):
    raw = bytearray(range(32))
    cipher = keys.dpapi(raw)
    assert cipher != raw
    decoded = keys.dpapi(cipher, decrypt=True)
    assert decoded == raw
    keys.wipe(decoded)
    assert not any(decoded)
    assert not list(tmp_path.iterdir())


def test_save_and_verify_ciphertext_and_never_reread_existing_key(tmp_path):
    root = tmp_path / 'key'
    raw = bytearray(range(32))
    before = bytes(raw)
    report = keys.save(root, lambda: raw)
    assert report['verified'] is True
    assert report['plaintext_bytes'] == 32
    assert not any(raw)
    assert list(root.iterdir()) == [root / keys.BLOB_NAME]
    assert before not in (root / keys.BLOB_NAME).read_bytes()
    assert keys.verify(root)['verified'] is True
    with pytest.raises(ValueError, match='exists'):
        keys.save(root, lambda: (_ for _ in ()).throw(AssertionError('must not reread server')))
    assert (root / keys.BLOB_NAME).read_bytes()


@pytest.mark.parametrize('name', ['unknown.txt', '.pull.lock'])
def test_unexpected_file_stops_before_secret_read(tmp_path, name):
    root = local_pull.prepare_root(tmp_path / 'key')
    (root / name).write_text('keep')
    with pytest.raises(ValueError, match='unmanaged'):
        keys.save(root, lambda: (_ for _ in ()).throw(AssertionError('must not read server')))
    assert (root / name).read_text() == 'keep'


def test_invalid_plaintext_length_never_publishes(tmp_path):
    for length in (0, 31, 33):
        raw = bytearray(length)
        root = tmp_path / str(length)
        with pytest.raises(ValueError, match='length'):
            keys.save(root, lambda: raw)
        assert not (root / keys.BLOB_NAME).exists()
        assert not any(raw)


def test_tampered_ciphertext_is_rejected_without_exception_payload(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'key'
    keys.save(root, lambda: bytearray(range(32)))
    (root / keys.BLOB_NAME).write_bytes(b'invalid')
    monkeypatch.setattr(keys, 'KEY_ROOT', str(root))
    assert keys.main(['--verify']) == 2
    output = capsys.readouterr()
    assert output.err.strip() == 'local_key_backup_failed'
    assert 'invalid' not in output.out + output.err


def test_default_cli_never_reads_key_or_creates_directory(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'key'
    monkeypatch.setattr(keys, 'KEY_ROOT', str(root))
    monkeypatch.setattr(keys, 'fetch_key', lambda: (_ for _ in ()).throw(AssertionError('secret read')))
    assert keys.main([]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'explicit_action_required'
    assert not root.exists()


@pytest.mark.parametrize('length', [32, 33])
def test_secret_pipe_is_bounded_to_exactly_32_bytes(monkeypatch, length):
    code = 'import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b"s"*' + str(length) + ')'
    monkeypatch.setattr(keys, 'SSHTransport', lambda: SimpleNamespace(base=[sys.executable, '-c', code]))
    if length == 33:
        with pytest.raises(ValueError, match='transfer'):
            keys.fetch_key()
    else:
        value = keys.fetch_key()
        assert len(value) == 32
        keys.wipe(value)
