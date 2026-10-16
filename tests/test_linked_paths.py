"""Private bot and operator files are never reached through a symlink or junction."""
import importlib.util
from pathlib import Path

import pytest


def linked_dir(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    link = tmp_path / 'link'
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip('Host does not permit creating symlinks')
    return real, link


def test_bot_config_file_behind_a_link_is_refused(tmp_path):
    from game_assistant.qq.client import QqClientError
    from game_assistant.qq.runner import private_file
    real, link = linked_dir(tmp_path)
    (real / 'qq.json').write_text('{}')
    (real / 'qq.json').chmod(0o600)
    assert private_file(real / 'qq.json') == (real / 'qq.json').absolute()
    with pytest.raises(QqClientError, match='qq_config_symlink_rejected'):
        private_file(link / 'qq.json')


def test_bot_state_behind_a_link_is_refused(tmp_path):
    from game_assistant.qq.transport import BotState
    _, link = linked_dir(tmp_path)
    with pytest.raises(ValueError, match='without links'):
        BotState(link / 'state.db')


def test_operator_backup_path_behind_a_link_is_refused(tmp_path):
    from scripts.cloud.backup import OperationError, safe_path
    real, link = linked_dir(tmp_path)
    assert safe_path(real / 'backup') == (real / 'backup').resolve()
    with pytest.raises(OperationError, match='symlink_path_rejected'):
        safe_path(link / 'backup')


def test_probe_credentials_behind_a_link_are_refused(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'scripts/cloud/probe_common.py'
    spec = importlib.util.spec_from_file_location('probe_common_links', path)
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    _, link = linked_dir(tmp_path)
    with pytest.raises(ValueError, match='symlink or junction'):
        common.safe_path(link / '.private-cloud-probes' / 'a.credentials.json')
