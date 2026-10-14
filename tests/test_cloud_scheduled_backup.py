from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from scripts.cloud import nightly_backup as nightly


def test_retention_keeps_recent_and_four_weekly_representatives():
    now = datetime(2026, 10, 14, tzinfo=timezone.utc)
    names = [(now - timedelta(days=n)).strftime('%Y%m%dT%H%M%SZ') + '-12345678' for n in range(45)]
    keep = nightly.keep_names(names, now)
    assert set(names[:7]) <= keep
    assert len(keep) <= 11
    assert names[-1] not in keep


def test_qq_live_wal_copy_is_independent(tmp_path):
    live = tmp_path / 'qq.db'
    with sqlite3.connect(live) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE sent(id INTEGER)')
        db.execute('INSERT INTO sent VALUES(1)')
        db.commit()
        nightly.copy_qq(live, tmp_path / 'copy.db')
        with sqlite3.connect(tmp_path / 'copy.db') as copy:
            assert copy.execute('PRAGMA quick_check').fetchone() == ('ok',)
            assert copy.execute('SELECT COUNT(*) FROM sent').fetchone() == (1,)
            assert copy.execute('PRAGMA journal_mode').fetchone() == ('delete',)


def test_qq_failure_never_publishes_or_prunes(tmp_path, monkeypatch):
    stage = tmp_path / 'stage'
    stage.mkdir()
    calls = []
    monkeypatch.setattr(nightly, 'backup', lambda *args: calls.append('central'))
    monkeypatch.setattr(nightly, 'copy_qq', lambda *args: (_ for _ in ()).throw(ValueError('synthetic failure')))
    monkeypatch.setattr(nightly, 'publish', lambda *args: calls.append('publish'))
    with pytest.raises(ValueError):
        nightly.build_set(stage, tmp_path / 'central', tmp_path / 'id', tmp_path / 'key', tmp_path / 'qq')
    assert calls == ['central']
    assert not (stage / 'complete.json').exists()


def test_retention_rejects_unmarked_directory(tmp_path):
    invalid = tmp_path / '20261001T000000Z-12345678'
    invalid.mkdir()
    with pytest.raises(ValueError, match='unmanaged_backup'):
        nightly.managed_sets(tmp_path)
    assert invalid.exists()
