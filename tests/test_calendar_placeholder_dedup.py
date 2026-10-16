"""A date-free version teaser is evidence, not a second activity or a phase."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from game_assistant.sources.public_content import calendar_from_posts, merge_events
from tests.test_public_content import notice


def test_cached_maintenance_teaser_and_later_version_dates_are_one_activity_with_both_sources():
    teaser = notice('3.7版本更新维护预告\n[团团勇者大乱斗]休闲活动\n[天工寻物]限时战斗活动\n[朝月鱼涌]网页活动',
                    id='1251098255067971586', published='2026-09-23T00:00:00+00:00')
    full = notice('3.7版本内容说明\n更新维护时间：2026年9月30日04:00\n'
        '[团团勇者大乱斗]休闲活动\n活动时间：3.7版本更新后 ~ 2026年11月11日11:59\n'
        '[天工寻物]限时战斗活动\n活动时间：2026年10月8日04:00 ~ 2026年10月26日03:59\n'
        '[朝月鱼涌]网页活动\n活动时间：2026年10月15日10:00 ~ 2026年11月1日09:59\n'
        '※可通过「沉冥」武器活动唤取获得。',
        id='1253680342191046665', published='2026-09-30T00:00:00+00:00')
    result = calendar_from_posts([teaser, full], 'wuthering_waves', datetime(2026,10,15,tzinfo=timezone.utc))
    rows = result['events']
    assert len(rows) == 4
    for name in ['团团勇者大乱斗','天工寻物','朝月鱼涌']:
        row = next(r for r in rows if r['name'] == name)
        assert row['end_at'] is not None
        assert row['source_post_id'] == '1253680342191046665'
        assert any(s['source_post_id'] == '1251098255067971586' and s['end_at'] is None
                   for s in row['supplement_sources'])
    pool = next(r for r in rows if r['name'] == '沉冥')
    assert pool['start_at'] is None and pool['end_at'] is None


def entry(name='同名活动', **extra):
    return dict(name=name, category='休闲活动', version='3.7', source='bilibili', source_name='B站官方动态',
        source_title='3.7版本内容说明', source_post_id='1', source_url='https://t.bilibili.com/1',
        start_at='2026-10-01T10:00:00+08:00', end_at='2026-10-10T10:00:00+08:00', **extra)


def placeholder(**extra):
    row = entry()
    row.update(start_at=None,end_at=None,start_precision='unknown',end_precision='unknown',time_text='',
               source_name='库街区官方公告',source_post_id='2',source_url='https://www.kurobbs.com/forum/post/2')
    row.update(extra)
    return row


def test_legacy_snapshot_placeholder_merges_only_with_one_matching_dated_event_without_mutating_input():
    dated, pending = entry(), placeholder()
    original = deepcopy([dated,pending])
    rows = merge_events([dated],[pending],'3.7')
    assert len(rows) == 1 and rows[0]['end_at'] == dated['end_at']
    assert rows[0]['supplement_sources'][0]['source_post_id'] == '2'
    assert [dated,pending] == original


@pytest.mark.parametrize('changes', [
    dict(category='网页活动'), dict(version='3.8',source_title='3.8版本内容说明'),
    dict(server='国际服'), dict(game='nte'), dict(phase='第二期'),
    dict(time_text='2026年10月30日 ~ 2026年10月1日'), dict(source_name='玩家投稿'),
])
def test_other_scope_explicit_phase_malformed_dates_and_untrusted_unknowns_are_not_merged(changes):
    # Empty primary avoids the current-version selection filter; this tests identity, not scope selection.
    rows = merge_events([], [entry(),placeholder(**changes)], None)
    assert len(rows) == 2


@pytest.mark.parametrize('second', [
    dict(start_at='2026-10-20T10:00:00+08:00',end_at='2026-10-30T10:00:00+08:00'),
    dict(start_at='2026-10-01T10:00:00+08:00',end_at='2026-10-11T10:00:00+08:00'),
])
def test_multiple_dated_phases_or_conflicting_candidates_keep_the_ambiguous_placeholder(second):
    other = {**entry(), **second, 'source_post_id':'3'}
    rows = merge_events([entry(),other],[placeholder()],'3.7')
    assert len(rows) == 3
    assert rows[0]['end_at'] == '2026-10-10T10:00:00+08:00'
    assert rows[1]['end_at'] == second['end_at']
    assert rows[2]['end_at'] is None


def test_undated_pool_from_both_bilibili_and_tajiduo_is_listed_once():
    # Tajiduo rows are stored with aliases=[] when a heading has no S-level name;
    # an empty list must fall back to the row's own name like a missing key does.
    import json
    from game_assistant.adapters.neverness.adapter import _parse_notice_events
    title = '《异环》1.4版本「祷歌为谁而诵」更新公告'
    text = ('● 全新限定S级角色「测试角色」\n开放时间：9月24日版本更新后-10月15日05:59\n'
            '● 「后续棋盘」限定棋盘\n开放时间：后续另行公告\n'
            '● 「像素溢出」限时活动\n活动时间：10月12日05:00-10月19日04:59')
    tajiduo = json.loads(json.dumps([event.model_dump(mode='json') for event in _parse_notice_events(
        {'postId': 494294, 'subject': title, 'createTime': 1790139834502}, {'content': text.replace('\n', '<br>')}, '1.4')]))
    bilibili = calendar_from_posts([dict(id='b1', title=title, body=title + '\n' + text, decision='accepted',
        published_at='2026-09-23T03:03:54+00:00', source='bilibili', source_name='B站官方动态',
        url='https://t.bilibili.com/b1')], 'nte', datetime(2026, 10, 16, 4, tzinfo=timezone.utc))['events']
    names = [row['name'] for row in merge_events(bilibili, tajiduo, '1.4')]
    assert names.count('测试角色') == 1 and names.count('后续棋盘') == 1
