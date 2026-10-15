"""Minimal factual excerpts from the anonymous 2026-10-14 version notices."""
from game_assistant.sources.public_content import parse_post_events, merge_events, _same_event


def official(body, game='wuthering_waves', version='3.7', **extra):
    return dict(id='1554535385333796864' if game == 'wuthering_waves' else '494294',
        title=version+'版本内容说明', body=body, decision='accepted', source='community',
        source_name='库街区官方公告' if game == 'wuthering_waves' else '塔吉多官方公告',
        url='https://example.test/public-notice', published_at='2026-09-30T04:00:00+08:00', **extra)


def test_authoritative_wuwa_version_preserves_both_announced_web_activities():
    post = official('[朝月鱼涌]网页活动\n活动时间：2026年10月15日10:00～2026年11月1日09:59\n'
                    '[索拉里斯回归邀约]网页活动\n活动时间：3.7版本更新后～2026年11月11日23:59')
    rows = parse_post_events(post, 'wuthering_waves', '3.7')
    assert [r['name'] for r in rows] == ['朝月鱼涌', '索拉里斯回归邀约']
    assert all(r['category'] == '网页活动' for r in rows)
    assert rows[0]['start_at'] == '2026-10-15T10:00:00+08:00'
    assert rows[0]['end_at'] == '2026-11-01T09:59:00+08:00'
    assert rows[1]['start_at'] is None and rows[1]['start_precision'] == 'relative'


def test_authoritative_nte_web_activity_keeps_category_and_survives_source_merge():
    post = official('● 「黑羽的邀请函」网页活动开启\n活动时间：9月24日版本更新后 - 11月5日05:59',
                    'nte', '1.4')
    rows = parse_post_events(post, 'nte', '1.4')
    assert [r['name'] for r in rows] == ['黑羽的邀请函']
    assert rows[0]['category'] == '网页活动'
    assert rows[0]['start_at'] is None and rows[0]['start_date'] == '2026-09-24'
    merged = merge_events([dict(name='游戏内活动',version='1.4')], rows, '1.4')
    assert [r['name'] for r in merged] == ['游戏内活动','黑羽的邀请函']


def test_explicitly_version_linked_official_web_supplement_can_enrich_the_calendar():
    post = official('[网页补充]网页活动\n活动时间：2026年10月15日10:00～2026年11月1日09:59')
    post.update(title='3.7版本网页活动公告', decision='excluded', reason='promotion',
                source='bilibili', source_name='B站官方动态')
    assert [e['name'] for e in parse_post_events(post,'wuthering_waves','3.7')] == ['网页补充']


def test_untrusted_or_unlinked_web_and_offline_promotions_remain_excluded():
    body = '[营销]网页活动\n活动时间：2026年10月15日10:00～2026年11月1日09:59'
    untrusted = official(body)
    untrusted['source_name'] = '玩家投稿'
    assert parse_post_events(untrusted,'wuthering_waves','3.7') == []
    unlinked = official(body)
    unlinked['title'] = '独立网页营销活动'
    assert parse_post_events(unlinked,'wuthering_waves','3.7') == []
    offline = official(body.replace('网页活动','线下活动'))
    assert parse_post_events(offline,'wuthering_waves','3.7') == []


def test_explicit_advertised_future_pools_remain_unknown_without_turning_weapon_intros_into_pools():
    post = official('5星武器「仅介绍的武器」\n'
        '※可通过[余心所向九死未悔]角色活动唤取获得。\n'
        '※可通过「沉冥」武器活动唤取获得。')
    rows = parse_post_events(post,'wuthering_waves','3.7')
    assert {(r['name'],r['category']) for r in rows} == {('余心所向九死未悔','角色活动唤取'),('沉冥','武器活动唤取')}
    assert all(r['start_at'] is None and r['end_at'] is None for r in rows)
    assert all(r['start_precision'] == r['end_precision'] == 'unknown' for r in rows)
    assert all(r['source_post_id'] == '1554535385333796864' for r in rows)


def test_pool_identity_is_deduplicated_and_official_dated_supplement_resolves_placeholder():
    post = official('※可通过「沉冥」武器活动唤取获得。\n※可通过「沉冥」武器活动唤取获得。')
    rows = parse_post_events(post,'wuthering_waves','3.7')
    assert len(rows) == 1
    dated = parse_post_events(official('「沉冥」武器活动唤取\n活动时间：2026年10月22日10:00 ~ 2026年11月11日09:59'),
                              'wuthering_waves','3.7')[0]
    assert _same_event(rows[0], dated)
    merged = merge_events(rows,[dated],'3.7')
    assert len(merged) == 1 and merged[0]['start_at'] == '2026-10-22T10:00:00+08:00'
    assert merged[0]['supplement_sources']
