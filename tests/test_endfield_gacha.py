"""终末地寻访账本：分页续传、断档与统计口径（离线假客户端，每页 5 条）。"""
import httpx
import pytest
import sqlite3
from fastapi import FastAPI

from game_assistant.adapters.endfield.hypergryph import EndfieldError
from game_assistant.adapters.endfield.endpoints import CHAR_POOL_TYPES
from game_assistant.config import Settings
from game_assistant.endfield_gacha import EndfieldGachaStore
from game_assistant.endfield_gacha_routes import install_endfield_gacha_routes

SPECIAL = "E_CharacterGachaPoolType_Special"


def rec(seq, rarity=4, name=None, free=False):
    return {"seqId": str(seq), "charId": f"c{seq}", "charName": name or f"干员{seq}", "rarity": rarity,
            "poolId": "special_1", "poolName": "冬猎", "isFree": free, "isNew": False,
            "gachaTs": str(1_780_000_000_000 + seq * 1000)}


def history(first, last, six=()):
    """seqId 由新到旧，与官方分页顺序一致。"""
    return [rec(seq, 6 if seq in six else 4) for seq in range(last, first - 1, -1)]


class FakeClient:
    def __init__(self, special=None, weapons=None, fail_on=None, inclusive=False):
        self.special = special or []
        self.weapons = weapons or {}
        self.fail_on = fail_on
        self.inclusive = inclusive  # 下一页是否从游标那条本身开始
        self.cursors = []

    def _page(self, rows, seq_id):
        self.cursors.append(seq_id)
        if seq_id is not None and seq_id == self.fail_on:
            raise EndfieldError("网络错误: ReadTimeout")
        start = 0 if seq_id is None else next(i for i, row in enumerate(rows) if row["seqId"] == seq_id) + (not self.inclusive)
        return {"list": rows[start:start + 5], "hasMore": start + 5 < len(rows)}

    async def char_records(self, u8_token, pool_type, seq_id=None):
        assert u8_token == "u8"
        return self._page(self.special if pool_type == SPECIAL else [], seq_id)

    async def weapon_pools(self, u8_token):
        return [{"poolId": pool_id, "poolName": name} for pool_id, (name, _) in self.weapons.items()]

    async def weapon_records(self, u8_token, pool_id, seq_id=None):
        return self._page(self.weapons[pool_id][1], seq_id)


async def no_sleep(_):
    pass


async def sync(store, client, budget=100, role="r1"):
    return await store.sync(role, client, "u8", budget=budget, interval=0, sleep=no_sleep)


def pool(store, key=SPECIAL, role="r1"):
    return next(p for p in store.summary(role).pools if p.key == key)


async def test_first_sync_walks_to_window_end_and_counts_since_last_six_star(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    client = FakeClient(special=history(101, 112, six={105}))
    used = await sync(store, client)
    assert used == 1 + 3 + 4  # 武器池列表 + 特许三页 + 其余四类各一页空结果
    special = pool(store)
    assert (special.total, special.six_star, special.gaps, special.pending) == (12, 1, 0, False)
    assert special.since_last_six.model_dump() == {"count": 7, "status": "exact"}
    # 窗口起点之前是否还有抽数未知，第一条 6★ 只能给出下限。
    assert [(h.name, h.pulls, h.status) for h in special.history] == [("干员105", 5, "lower_bound")]
    assert store.summary("r1").complete


async def test_incremental_sync_stops_at_known_records(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    client = FakeClient(special=history(101, 112, six={105}))
    await sync(store, client)
    client.special = history(101, 115, six={105})
    client.cursors = []
    await sync(store, client)
    assert client.cursors == [None] * 5  # 每个角色池只请求最新一页
    assert pool(store).total == 15 and pool(store).since_last_six.count == 10


async def test_budget_exhaustion_leaves_a_gap_that_the_next_sync_resumes(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    client = FakeClient(special=history(1, 30, six={3, 28}))
    assert await sync(store, client, budget=3) == 3
    partial = pool(store)
    assert (partial.total, partial.pending) == (10, True)
    assert not store.summary("r1").complete
    # 断档在 seq 21 之下：最近一次 6★ 之后仍连续，确定；这次 6★ 本身的抽数只能给下限。
    assert partial.since_last_six.model_dump() == {"count": 2, "status": "exact"}
    assert [(h.pulls, h.status) for h in partial.history] == [(8, "lower_bound")]
    await sync(store, client)
    done = pool(store)
    assert (done.total, done.gaps, done.pending) == (30, 0, False)
    assert done.since_last_six.model_dump() == {"count": 2, "status": "exact"}
    assert [(h.pulls, h.status) for h in done.history] == [(25, "exact"), (3, "lower_bound")]
    assert store.summary('r1').complete is True


async def test_budget_at_pool_boundary_keeps_unvisited_pools_pending(tmp_path):
    store = EndfieldGachaStore(tmp_path / 'g.sqlite3')
    client = FakeClient(special=history(1, 5))
    assert await sync(store, client, budget=2) == 2
    summary = store.summary('r1')
    # The first pool ended cleanly. The other four pools have not been read.
    assert summary.pools[0].pending is False and summary.pools[0].gaps == 0
    assert summary.complete is False and summary.report['pending'] is True
    # The state survives closing/reopening the ledger.
    store = EndfieldGachaStore(store.path)
    assert store.summary('r1').complete is False
    await sync(store, client)
    assert store.summary('r1').complete is True


async def test_empty_unvisited_and_successfully_scanned_pools_are_distinct(tmp_path):
    store = EndfieldGachaStore(tmp_path / 'g.sqlite3')
    unseen = store.summary('r1')
    assert unseen.total == 0 and unseen.complete is None and unseen.report['pending'] is None
    await sync(store, FakeClient(), budget=1)  # Discovery used the entire budget.
    pending = store.summary('r1')
    assert pending.pools == [] and pending.total == 0
    assert pending.complete is False and pending.report['pending'] is True
    await sync(store, FakeClient())
    empty = store.summary('r1')
    assert empty.pools == [] and empty.complete is True and empty.report['pending'] is False
    assert store.summary('another-role').complete is None


async def test_discovered_weapon_pool_must_be_scanned_even_when_all_character_pools_are_empty(tmp_path):
    store = EndfieldGachaStore(tmp_path / 'g.sqlite3')
    client = FakeClient(weapons={'weapon_1': ('合成武器池', [])})
    await sync(store, client, budget=1 + len(CHAR_POOL_TYPES))
    summary = store.summary('r1')
    assert summary.total == 0 and summary.pools == []
    assert summary.complete is False and summary.report['pending'] is True
    await sync(store, client)
    assert store.summary('r1').complete is True


@pytest.mark.parametrize('failure', ['discovery', 'first_page', 'empty_has_more'])
async def test_failed_scan_retains_success_time_and_cannot_claim_completion(tmp_path, failure):
    store = EndfieldGachaStore(tmp_path / 'g.sqlite3')
    await sync(store, FakeClient(special=history(1, 5)))
    successful = pool(store).last_sync_at

    class FailedClient(FakeClient):
        async def weapon_pools(self, token):
            if failure == 'discovery':
                raise EndfieldError('synthetic catalog failure')
            return await super().weapon_pools(token)

        async def char_records(self, token, pool_type, seq_id=None):
            if failure == 'empty_has_more':
                return {'list': [], 'hasMore': True}
            raise EndfieldError('synthetic first page failure')

    with pytest.raises((EndfieldError, ValueError)):
        await sync(store, FailedClient())
    failed = store.summary('r1')
    assert failed.complete is False and failed.report['pending'] is True
    assert pool(store).last_sync_at == successful and pool(store).total == 5
    await sync(store, FakeClient(special=history(1, 5)))
    assert store.summary('r1').complete is True


@pytest.mark.parametrize('all_pools,successful,pending_break,expected', [
    (False, True, False, None), (True, False, False, None),
    (True, True, False, True), (True, True, True, False),
])
def test_legacy_coverage_is_inferred_only_from_successful_scans(tmp_path, all_pools, successful, pending_break, expected):
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE pools(role TEXT NOT NULL,pool_key TEXT NOT NULL,kind TEXT NOT NULL,'
                   'label TEXT NOT NULL,last_sync_at TEXT,PRIMARY KEY(role,pool_key))')
        for key, label in (CHAR_POOL_TYPES.items() if all_pools else [(SPECIAL, '特许寻访')]):
            db.execute('INSERT INTO pools VALUES(?,?,?,?,?)',
                       ('r1', key, 'character', label, '2026-10-15T00:00:00Z' if successful else None))
    store = EndfieldGachaStore(path)
    if pending_break:
        with sqlite3.connect(path) as db:
            db.execute('INSERT INTO breaks VALUES(?,?,?,0)', ('r1', SPECIAL, 5))
    summary = store.summary('r1')
    assert summary.complete is expected
    assert summary.report['pending'] is (None if expected is None else not expected)
    assert EndfieldGachaStore(path).summary('r1').complete is expected


async def test_an_inclusive_cursor_still_walks_to_the_window_end(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    client = FakeClient(special=history(1, 17, six={2}), inclusive=True)
    await sync(store, client)
    assert (pool(store).total, pool(store).gaps) == (17, 0)
    assert pool(store).since_last_six.model_dump() == {"count": 15, "status": "exact"}


async def test_a_failed_page_keeps_fetched_records_and_resumes_later(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    client = FakeClient(special=history(1, 20), fail_on="16")
    with pytest.raises(EndfieldError):
        await sync(store, client)
    assert (pool(store).total, pool(store).pending) == (5, True)
    client.fail_on = None
    await sync(store, client)
    assert (pool(store).total, pool(store).pending, pool(store).gaps) == (20, False, 0)


async def test_window_moving_past_old_records_leaves_a_permanent_gap(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    client = FakeClient(special=history(1, 5, six={2}))
    await sync(store, client)
    client.special = history(90, 100)  # 旧记录已滑出官方窗口
    await sync(store, client)
    special = pool(store)
    assert (special.total, special.gaps, special.pending) == (16, 1, False)
    assert store.summary("r1").complete
    assert special.since_last_six.model_dump() == {"count": 11, "status": "lower_bound"}
    client.cursors = []
    await sync(store, client)
    assert client.cursors == [None] * 5  # 永久断档不再续传


async def test_free_pulls_turn_the_count_into_a_lower_bound(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    rows = history(1, 8, six={2})
    rows[0]["isFree"] = True
    await sync(store, FakeClient(special=rows))
    special = pool(store)
    assert special.free == 1
    assert special.since_last_six.model_dump() == {"count": 5, "status": "lower_bound"}


async def test_rerun_is_fetched_and_kept_separate_from_special(tmp_path):
    rerun = 'E_CharacterGachaPoolType_Rerun'

    class RerunClient(FakeClient):
        async def char_records(self, u8_token, pool_type, seq_id=None):
            if pool_type == rerun:
                rows = [{**row, 'poolId': 'rerun_1', 'poolName': '绚丽异彩'}
                        for row in history(10, 12, six={11})]
                return self._page(rows, seq_id)
            return await super().char_records(u8_token, pool_type, seq_id)

    store = EndfieldGachaStore(tmp_path / 'g.sqlite3')
    await sync(store, RerunClient(special=history(1, 4)))
    assert [(entry.label, entry.total) for entry in store.summary('r1').pools] == [
        ('特许寻访', 4), ('重构寻访', 3)]
    assert pool(store, rerun).since_last_six.count == 1
    assert len(store.export('r1')['records']) == 7


@pytest.mark.parametrize('missing', ['rarity', 'isFree'])
async def test_missing_pull_attributes_cannot_produce_exact_pity(tmp_path, missing):
    store = EndfieldGachaStore(tmp_path / 'g.sqlite3')
    rows = history(1, 3, six={1})
    rows[1].pop(missing)
    await sync(store, FakeClient(special=rows))
    assert pool(store).since_last_six.model_dump() == {'count':1, 'status':'lower_bound'}
    # A later known six-star establishes a new continuous segment.
    rows = history(1, 6, six={1, 5})
    rows[4].pop(missing)
    await sync(store, FakeClient(special=rows))
    summary = pool(store)
    assert summary.history[0].status == 'lower_bound'
    assert summary.since_last_six.model_dump() == {'count':1, 'status':'exact'}


async def test_weapon_pools_roles_and_public_records_are_isolated(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    weapon = [{"seqId": "501", "weaponId": "w1", "weaponName": "寒夜幽影", "weaponType": "施术单元",
               "rarity": 6, "poolId": "weapon_1", "poolName": "幽寒申领", "isNew": True, "gachaTs": "1780000000"}]
    await sync(store, FakeClient(special=history(1, 3), weapons={"weapon_1": ("幽寒申领", weapon)}))
    summary = store.summary("r1")
    assert [p.key for p in summary.pools] == [SPECIAL, "weapon:weapon_1"]
    assert pool(store, "weapon:weapon_1").history[0].obtained_at == 1_780_000_000_000
    assert store.summary("someone-else").pools == []
    page = store.records("r1", "weapon:weapon_1")
    assert page["total"] == 1 and page["records"][0]["seq_id"] == "501"
    exported = store.export("r1")
    assert exported["format"] == "game-assistant-endfield-gacha" and len(exported["records"]) == 4
    assert all(isinstance(row["seq_id"], str) for row in exported["records"])


async def test_invalid_records_fail_closed_without_writing(tmp_path):
    store = EndfieldGachaStore(tmp_path / "g.sqlite3")
    rows = history(1, 3)
    rows[1]["seqId"] = "abc"
    with pytest.raises(ValueError):
        await sync(store, FakeClient(special=rows))
    assert store.summary("r1").pools == []
    assert store.summary('r1').complete is False
    assert store.summary('r1').report['pending'] is True


async def test_routes_require_a_logged_in_role_and_serve_the_ledger(tmp_path):
    settings = Settings(db_path=str(tmp_path / "a.db"), auth_allowed_origins=["http://testserver"])
    app = FastAPI()
    app.state.settings = settings
    install_endfield_gacha_routes(app, settings)
    from game_assistant.api_security import install_api_security
    install_api_security(app, settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        assert (await client.get("/api/endfield/gacha/summary")).status_code == 409
        settings.endfield_role_id = "r1"
        store = EndfieldGachaStore(tmp_path / "a.endfield-gacha.sqlite3")
        await sync(store, FakeClient(special=history(1, 7, six={4})))
        summary = (await client.get("/api/endfield/gacha/summary")).json()
        assert summary["schema_version"] == 1 and summary["pools"][0]["six_star"] == 1
        page = (await client.get("/api/endfield/gacha/records?limit=2&offset=1")).json()
        assert page["total"] == 7 and [r["seq_id"] for r in page["records"]] == ["6", "5"]
        assert (await client.get("/api/endfield/gacha/records?limit=0")).status_code == 400
        exported = await client.get("/api/endfield/gacha/export")
        assert "attachment" in exported.headers["content-disposition"]
        assert (await client.get("/api/endfield/gacha/summary", headers={"Origin": "https://evil.invalid"})).status_code == 403


def test_legacy_unscanned_pool_does_not_claim_known_pending_false(tmp_path):
    path=tmp_path/'legacy-coverage.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE pools(role TEXT NOT NULL,pool_key TEXT NOT NULL,kind TEXT NOT NULL,label TEXT NOT NULL,last_sync_at TEXT,PRIMARY KEY(role,pool_key))')
        db.execute('INSERT INTO pools VALUES(?,?,?,?,NULL)',('r1',SPECIAL,'character','legacy'))
    store=EndfieldGachaStore(path)
    store._add('r1',SPECIAL,[dict(seq_id=1,rarity=4,is_free=False,gacha_ts=1780000000000)])
    summary=store.summary('r1')
    assert summary.complete is None and summary.pools[0].pending is None


def test_scan_pending_addition_preserves_old_named_sql_and_sqlite_backup(tmp_path):
    from contextlib import closing
    original=tmp_path/'legacy.sqlite3';working=tmp_path/'upgrade.sqlite3';backup=tmp_path/'backup.sqlite3'
    with closing(sqlite3.connect(original)) as db:
        db.execute('CREATE TABLE pools(role TEXT NOT NULL,pool_key TEXT NOT NULL,kind TEXT NOT NULL,label TEXT NOT NULL,last_sync_at TEXT,PRIMARY KEY(role,pool_key))')
        db.executemany('INSERT INTO pools VALUES(?,?,?,?,?)',[('r1',SPECIAL,'character','legacy','2026-10-14T00:00:00Z'),('r1','unscanned','character','unknown',None)])
        db.commit()
        with closing(sqlite3.connect(working)) as target:db.backup(target)
    before=original.read_bytes();store=EndfieldGachaStore(working)
    with closing(sqlite3.connect(working)) as db:
        assert db.execute('SELECT pool_key,scan_pending FROM pools ORDER BY pool_key').fetchall()==[(SPECIAL,0),('unscanned',None)]
        # These are the deployed a2ed77c constructor/sync/export named-column statements.
        db.execute('INSERT INTO pools(role,pool_key,kind,label) VALUES(?,?,?,?) ON CONFLICT(role,pool_key) DO UPDATE SET label=excluded.label',('r1',SPECIAL,'character','old-code-updated'))
        db.execute('UPDATE pools SET last_sync_at=? WHERE role=? AND pool_key=?',('2026-10-15T00:00:00Z','r1',SPECIAL))
        assert len(db.execute('SELECT pool_key,kind,label,last_sync_at FROM pools WHERE role=?',('r1',)).fetchall())==2
        db.commit()
        with closing(sqlite3.connect(backup)) as target:db.backup(target)
        rows=db.execute('SELECT * FROM pools ORDER BY pool_key').fetchall()
    reopened=EndfieldGachaStore(working)
    with closing(sqlite3.connect(backup)) as db:assert db.execute('SELECT * FROM pools ORDER BY pool_key').fetchall()==rows
    assert original.read_bytes()==before and reopened.path==working
