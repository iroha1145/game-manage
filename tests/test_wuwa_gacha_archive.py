import json
import pytest
from game_assistant.wuwa_gacha import GachaStore
from game_assistant.snapshots import SnapshotStore


@pytest.fixture
def ledger(tmp_path):
    snapshots = SnapshotStore(str(tmp_path / 'db'))
    return GachaStore(snapshots._conn, snapshots._lock)


def row(i, rarity=3, pool='1', **extra):
    return dict(id=str(i), cardPoolType=pool, resourceId='r', name='未知物品',
                qualityLevel=rarity, time=f'2026-01-01 12:00:{i:02d}', **extra)


def doc(rows, **extra):
    return dict(info=dict(uid='100', server_id='S'), list=rows, **extra)


def commit(g, document, **options):
    p = g.preview(document, '100', 'S', session='v1', **options)
    return g.commit_preview(p['preview_id'], '100', 'S', session='v1')


def test_preview_read_only_bound_one_use_and_atomic_conflict(ledger):
    p = ledger.preview(doc([row(1), row(1)]), '100', 'S', session='v1')
    assert ledger.read('100', 'S')['total'] == 0
    assert p['received'] == 1
    with pytest.raises(ValueError):
        ledger.commit_preview(p['preview_id'], '100', 'S', session='v2')
    assert ledger.commit_preview(p['preview_id'], '100', 'S', session='v1')['inserted'] == 1
    with pytest.raises(ValueError):
        ledger.commit_preview(p['preview_id'], '100', 'S', session='v1')
    with pytest.raises(ValueError):
        commit(ledger, doc([row(2), row(1, 5)]))
    assert ledger.read('100', 'S')['total'] == 1


def test_simultaneous_real_multiplicity_and_failed_empty_preserve(ledger):
    r = row(1); r.pop('id')
    commit(ledger, doc([r, r]))
    assert ledger.read('100', 'S')['total'] == 2
    commit(ledger, doc([r, r]), failed_pools=['2'])
    commit(ledger, doc([]))
    assert ledger.read('100', 'S')['total'] == 2
    assert ledger.read('100', 'S')['coverage']['failed_pools'] == ['2']


def test_mcgf_summary_top_level_only_unknowns_and_no_filler(ledger):
    item = dict(cardPoolType=99, name='未知五星', time='2026-01-01 12:00:00',
                resourceId=999, resourceType='角色', draw_total=120)
    document = dict(data=dict(uid='100', card_analysis_json=dict(pool=dict(
        five_cards=[item], versions=dict(v1=dict(five_cards=[item]))))))
    commit(ledger, document, source='mcgf')
    a = ledger.read('100', 'S')
    assert a['total'] == 0 and a['gold_total'] == 0
    assert a['aggregates']['total'] == 1
    assert a['aggregates']['items'][0]['period_count'] == 120
    assert a['aggregates']['items'][0]['pool'] == '99'
    assert 'UNKNOWN_POOL' in a['aggregates']['items'][0]['diagnostics']
    commit(ledger, document, source='mcgf')
    assert ledger.read('100', 'S')['aggregates']['total'] == 1


def test_xhh_marker_is_summary_not_gold_and_unknown_mapping(ledger):
    document = dict(user_info=dict(uid='100'), gacha_record=[dict(pool_type='限定', records=[
        dict(name='未知名称', timestamp=1767268800, diff=91, idx=1),
        dict(name='', timestamp=1767268801, diff=7, idx=9223372036854775807)])])
    commit(ledger, document, source='xhh')
    a = ledger.read('100', 'S')['aggregates']
    assert a['total'] == 2 and a['five_star_total'] == 1
    assert a['items'][1]['kind'] == 'current_count'
    assert a['items'][0]['resource_id'] is None
    assert 'UNKNOWN_RESOURCE' in a['items'][0]['diagnostics']
    assert ledger.read('100', 'S')['total'] == 0
    with pytest.raises(ValueError):
        commit(ledger, dict(document, user_info=dict(uid='101')), source='xhh')


def test_pity_requires_rules_and_continuous_latest_segment(ledger):
    commit(ledger, doc([row(1, 5), row(2), row(3)]), latest_confirmed=True, continuity_confirmed=True)
    assert ledger.read('100', 'S')['pools'][0]['pity']['status'] == 'unknown'
    ledger.set_rule('100', 'S', dict(pool='1', hard_pity=80, reset_rarity='5', version='personal-v1',
                                   sharing='independent', basis='user_configured'))
    p = ledger.read('100', 'S')['pools'][0]['pity']
    assert p['status'] == 'exact' and p['count'] == 2 and p['hard_pity_remaining'] == 78
    assert p['up_guarantee'] == 'unknown' and p['rule_basis'] == 'user_configured'
    commit(ledger, doc([row(5)]), latest_confirmed=True, continuity_confirmed=True)
    p = ledger.read('100', 'S')['pools'][0]['pity']
    assert p['status'] == 'lower_bound' and p['count'] == 1
    commit(ledger, doc([row(6)]), latest_confirmed=True, continuity_confirmed=True, warnings=['SOURCE_GAP'])
    assert ledger.read('100', 'S')['pools'][0]['pity']['status'] == 'unknown'


def test_segmented_backup_cannot_upgrade_coverage_and_restore(ledger, tmp_path):
    commit(ledger, doc([row(1,5),row(2),row(3)]), latest_confirmed=True, continuity_confirmed=True)
    archive = ledger.export('100', 'S', offset=0, limit=2)
    assert archive['coverage'][0]['latest_confirmed'] is False
    assert 'ARCHIVE_SEGMENTED' in archive['coverage'][0]['warnings']
    snapshot = SnapshotStore(str(tmp_path/'restore'))
    restored = GachaStore(snapshot._conn, snapshot._lock)
    commit(restored, archive, latest_confirmed=True, continuity_confirmed=True)
    assert restored.read('100','S')['coverage']['segments'][0]['latest_confirmed'] is False


def test_legacy_conflict_is_atomic(ledger):
    ledger.import_records(doc([row(1)]),'100','S')
    with pytest.raises(ValueError):
        ledger.import_records(doc([row(2),row(1,5)]),'100','S')
    assert ledger.read('100','S')['total'] == 1


def test_preview_expiry_identity_and_intervening_conflict(ledger):
    p=ledger.preview(doc([row(1)]),'100','S',session='v1')
    for account,server in [('101','S'),('100','other')]:
        with pytest.raises(ValueError):ledger.commit_preview(p['preview_id'],account,server,session='v1')
    ledger._previews[p['preview_id']]['expires']=0
    with pytest.raises(ValueError):ledger.commit_preview(p['preview_id'],'100','S',session='v1')
    p=ledger.preview(doc([row(1),row(2)]),'100','S',session='v1')
    ledger.import_records(doc([row(2,5)]),'100','S')
    with pytest.raises(ValueError):ledger.commit_preview(p['preview_id'],'100','S',session='v1')
    assert ledger.read('100','S')['total']==1


def test_rule_validation_same_second_order_gap_and_partial_archive(ledger,tmp_path):
    with pytest.raises(ValueError):ledger.set_rule('100','S',dict(pool='1',hard_pity=80,basis='official'))
    rule=dict(pool='1',hard_pity=80,reset_rarity='5',version='user-test',sharing='independent',basis='user_configured')
    ledger.set_rule('100','S',rule)
    commit(ledger,doc([row(1,5),dict(row(2),time='2026-01-01 12:00:01')]),
        latest_confirmed=True,continuity_confirmed=True)
    assert 'same_timestamp_order_unknown' in ledger.read('100','S')['pools'][0]['pity']['missing_requirements']
    commit(ledger,doc([row(4,history_gap_before=True)]),latest_confirmed=True,continuity_confirmed=True,failed_pools=['2'])
    archive=ledger.export('100','S')
    snapshot=SnapshotStore(str(tmp_path/'restore'))
    restored=GachaStore(snapshot._conn,snapshot._lock)
    commit(restored,archive,latest_confirmed=True,continuity_confirmed=True)
    assert restored.read('100','S')['rules']==[rule]
    assert restored.read('100','S')['pools'][0]['pity']['status']=='unknown'
    assert {'SOURCE_GAP','SOURCE_PARTIAL'}<=set(restored.read('100','S')['coverage']['segments'][-1]['warnings'])


def test_aggregate_conflict_source_errors_and_paging_full_totals(ledger):
    item=dict(cardPoolType=1,name='五星',time='2026-01-01',draw_total=90)
    document=dict(data=dict(uid='100',card_analysis_json=dict(pool=dict(five_cards=[item]))))
    commit(ledger,document,source='mcgf')
    commit(ledger,document,source='mcgf')
    assert len(ledger._archive_data('100','S')['batches'])==1
    conflict=dict(data=dict(uid='100',card_analysis_json=dict(pool=dict(five_cards=[dict(item,draw_total=91)]))))
    with pytest.raises(ValueError):commit(ledger,conflict,source='mcgf')
    with pytest.raises(ValueError):commit(ledger,dict(status='error',result={}),source='xhh')
    assert ledger.read('100','S')['aggregates']['items'][0]['period_count']==90
    records=[dict(id=str(i),pool='1',resource_id='r',rarity=3,time=f'2026-01-01T12:{i//60:02d}:{i%60:02d}') for i in range(600)]
    commit(ledger,doc(records))
    result=ledger.read('100','S',50,550)
    assert result['total']==600 and result['pools'][0]['total']==600 and len(result['items'])==50
    assert result['coverage']['complete'] is False


def test_pre_upgrade_anonymous_key_stays_idempotent(ledger):
    import hashlib
    from game_assistant.wuwa_gacha import normalize_records
    incoming=row(1);incoming.pop('id')
    normalized=normalize_records(doc([incoming]),'100','S')[0]
    raw=json.dumps(normalized,sort_keys=True,ensure_ascii=False)
    key=hashlib.sha256(raw.encode()).hexdigest()+':1'
    with ledger.conn:
        ledger.conn.execute('INSERT INTO wuwa_gacha VALUES(?,?,?,?,?,?,?)',('100','S','1',key,raw,normalized['time'],normalized['rarity']))
    assert commit(ledger,doc([incoming]))['inserted']==0


def test_aggregate_only_backup_pages_restore_every_summary(ledger,tmp_path):
    rows=[dict(cardPoolType=99,name=f'五星 {i}',time=f'2026-01-{i+1:02d}',draw_total=i+1) for i in range(5)]
    commit(ledger,dict(data=dict(uid='100',card_analysis_json=dict(pool=dict(five_cards=rows)))),source='mcgf')
    snapshot=SnapshotStore(str(tmp_path/'aggregate-restore'))
    restored=GachaStore(snapshot._conn,snapshot._lock)
    offset=0
    while offset is not None:
        archive=ledger.export('100','S',offset=offset,limit=2)
        assert len(archive['aggregate_items'])<=2
        commit(restored,archive)
        offset=archive['export_page']['next_offset']
    assert restored.read('100','S')['aggregates']['total']==5
    assert restored.read('100','S')['total']==0


def test_own_archive_top_warning_and_gap_cannot_restore_exact_pity(ledger,tmp_path):
    commit(ledger,doc([row(1,5),row(2)]),latest_confirmed=True,continuity_confirmed=True)
    ledger.set_rule('100','S',dict(pool='1',hard_pity=80,reset_rarity='5',version='personal',sharing='independent',basis='user_configured'))
    assert ledger.read('100','S')['pools'][0]['pity']['status']=='exact'
    archive=ledger.export('100','S')
    archive['warnings']=['SECRET-CREDENTIAL=https://example.invalid']
    archive['list'][0]['history_gap_before']=True
    snapshot=SnapshotStore(str(tmp_path/'warning-restore'))
    restored=GachaStore(snapshot._conn,snapshot._lock)
    commit(restored,archive)
    segment=restored.read('100','S')['coverage']['segments'][0]
    assert {'SOURCE_WARNING','SOURCE_GAP'}<=set(segment['warnings'])
    assert 'SECRET' not in json.dumps(restored.export('100','S'))
    assert restored.read('100','S')['pools'][0]['pity']['status']=='unknown'


def test_two_connection_conflict_check_holds_write_transaction(ledger,tmp_path):
    import sqlite3,threading
    path=str(tmp_path/'parallel')
    first=GachaStore(sqlite3.connect(path,check_same_thread=False),threading.Lock())
    second=GachaStore(sqlite3.connect(path,check_same_thread=False),threading.Lock())
    p=first.preview(doc([row(1)]),'100','S')
    q=second.preview(doc([row(1,5)]),'100','S')
    check=first._check_conflicts
    start=threading.Event();done=threading.Event();errors=[]
    def competing():
        start.wait()
        try:second.commit_preview(q['preview_id'],'100','S')
        except ValueError:errors.append('conflict')
        finally:done.set()
    worker=threading.Thread(target=competing);worker.start()
    def checked(*args):
        assert first.conn.in_transaction
        start.set()
        return check(*args)
    first._check_conflicts=checked
    try:
        first.commit_preview(p['preview_id'],'100','S')
        assert done.wait(3)
        assert errors==['conflict']
        assert first.read('100','S')['items'][0]['rarity']=='3'
    finally:
        start.set();worker.join(4);first.conn.close();second.conn.close()


def fresh():
    import sqlite3,threading
    return GachaStore(sqlite3.connect(':memory:',check_same_thread=False),threading.Lock())


def anonymous(second, **changes):
    r=dict(row(second),**changes); r.pop('id'); return r


def stored(store):
    return (store.conn.execute('SELECT pool,draw_id,payload FROM wuwa_gacha ORDER BY pool,draw_id').fetchall(),
            sorted(item['summary_id'] for item in store._archive_data('100','S')['aggregates']))


def pages(store, limit):
    result,offset=[],0
    while offset is not None:
        result.append(store.export('100','S',offset=offset,limit=limit))
        offset=result[-1]['export_page']['next_offset']
    return result


def test_export_never_splits_identical_anonymous_rows(ledger):
    # Re-import numbers identical anonymous rows by their order in the file, so a page holding
    # one of two such rows listed the stored key hash:2 and could not be restored.
    commit(ledger,doc([anonymous(1),anonymous(1)]))
    for offset in (0,1):
        page=ledger.export('100','S',offset=offset,limit=1)
        assert (page['export_page']['offset'],len(page['list']),page['export_page']['next_offset'])==(0,2,None)
        restored=fresh(); commit(restored,page)
        assert stored(restored)==stored(ledger)


def test_paged_export_restores_every_row_when_a_page_ends_inside_a_group(ledger):
    second8=dict(time='2026-01-01 12:00:08')
    records=[row(9),*[anonymous(8)]*3,dict(row(7),**second8),*[anonymous(8,cardPoolType='2')]*2,row(6),
             *[anonymous(5,name='另一物品')]*2,row(5),row(4)]
    commit(ledger,doc(records))
    summaries=[dict(cardPoolType=99,name=f'五星 {i}',time=f'2026-01-{i+1:02d}',draw_total=i+1) for i in range(5)]
    commit(ledger,dict(data=dict(uid='100',card_analysis_json=dict(pool=dict(five_cards=summaries)))),source='mcgf')
    original=stored(ledger)
    assert len(original[0])==12 and len(original[1])==5
    for limit in range(1,13):
        restored=fresh(); chain=pages(ledger,limit)
        for page in chain:
            commit(fresh(),page)
            commit(restored,page)
        assert stored(restored)==original
        assert sum(len(p['list']) for p in chain)==12 and sum(len(p['aggregate_items']) for p in chain)==5
    for offset in range(12):
        commit(fresh(),ledger.export('100','S',offset=offset,limit=1))
    assert any(len(page['list'])>1 for page in pages(ledger,1))


def test_size_halving_keeps_identical_anonymous_rows_on_one_page(ledger):
    # Groups of seven: no halved limit (20000, 10000, ..., 1) is a multiple of seven.
    wide=dict(name='n'*512,resourceId='r'*512,resourceType='t'*512)
    commit(ledger,doc([anonymous(0,time=f'2026-01-01T00:{g//60:02d}:{g%60:02d}',**wide) for g in range(200) for _ in range(7)]))
    chain=pages(ledger,20000)
    restored=fresh()
    for page in chain:
        commit(fresh(),page)
        commit(restored,page)
    assert stored(restored)==stored(ledger)
    assert len(chain)>1 and chain[0]['export_page']['limit']%7==0
