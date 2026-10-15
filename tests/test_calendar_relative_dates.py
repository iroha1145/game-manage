"""Relative openings use their own official maintenance batch, at day precision."""
from datetime import datetime, timezone

from game_assistant.sources.public_content import calendar_from_posts, parse_post_events
from tests.test_public_content import notice

NOW = datetime(2026, 10, 15, 8, tzinfo=timezone.utc)


def test_version_and_midpatch_maintenance_bind_distinct_relative_openings():
    base = notice('1.4版本更新公告\n更新维护时间：2026年9月24日06:00 - 11:00\n'
                  '● 「版本活动」限时活动\n活动时间：1.4版本更新后 - 11月5日05:59',
                  published='2026-09-23T06:00:00+00:00')
    middle = notice('10月15日停服维护公告\n维护时间：2026年10月15日06:00 - 11:00\n'
                    '● 「中期活动」限时活动\n活动时间：维护完成后 - 11月5日05:59',
                    id='2', published='2026-10-14T04:00:00+00:00')
    events = calendar_from_posts([base, middle], 'nte', NOW)['events']
    by_name = {e['name']: e for e in events}
    assert by_name['版本活动']['start_date'] == '2026-09-24'
    assert by_name['中期活动']['start_date'] == '2026-10-15'
    for name, post_id in [('版本活动', '1'), ('中期活动', '2')]:
        event = by_name[name]
        assert event['start_at'] is None
        assert event['start_precision'] == 'relative'
        assert event['start_estimated'] is True
        assert event['start_source']['post_id'] == post_id


def test_version_pool_uses_matching_version_maintenance_and_keeps_both_sources():
    base = notice('3.7版本内容说明\n更新维护时间：2026年9月30日04:00 ~ 11:00\n'
                  '[活动]限时活动\n活动时间：3.7版本更新后 ~ 2026年11月11日03:59',
                  published='2026-09-30T02:00:00+00:00')
    pool = notice('3.7版本角色唤取\n「当期卡池」角色活动唤取\n'
                  '活动时间：3.7版本更新后 ~ 2026年10月22日09:59',
                  id='2', published='2026-09-30T03:00:00+00:00')
    row = next(e for e in calendar_from_posts([pool, base], 'wuthering_waves', NOW)['events']
               if e['name'] == '当期卡池')
    assert row['start_date'] == '2026-09-30'
    assert row['source_post_id'] == '2'
    assert row['start_source']['post_id'] == '1'
    assert row['start_at'] is None


def test_unlinked_relative_opening_never_borrows_other_notice_or_next_version_day():
    base = notice('3.7版本内容说明\n更新维护时间：2026年9月30日04:00\n'
                  '[日期基准]活动\n活动时间：2026年10月1日10:00 ~ 2026年11月1日10:00',
                  published='2026-09-30T02:00:00+00:00')
    future = notice('3.8版本内容说明\n更新维护时间：2026年11月12日04:00\n'
                    '[未来]活动\n活动时间：3.8版本更新后 ~ 2026年12月1日10:00',
                    id='2', published='2026-10-14T04:00:00+00:00')
    unrelated = notice('[归属未明]活动\n活动时间：维护后 ~ 2026年11月1日10:00',
                       id='3', published='2026-10-14T04:00:00+00:00')
    row = next(e for e in calendar_from_posts([base, future, unrelated], 'wuthering_waves', NOW)['events']
               if e['name'] == '归属未明')
    assert row.get('start_date') is None and row.get('start_source') is None
    other = parse_post_events({**base, 'game_id': 'nte'}, 'wuthering_waves', '3.7')
    assert not other or all(e.get('start_source') is None for e in other)


def test_single_relative_date_is_an_opening_and_permanent_has_no_fake_deadline():
    post = notice('3.7版本内容说明\n更新维护时间：2026年9月30日04:00 ~ 11:00\n'
                  '[故梦寻契]留影收集活动\n开放时间：3.7版本更新后永久开放\n'
                  '[中期开放]活动\n开放时间：2026年10月15日维护更新后',
                  published='2026-09-30T02:00:00+00:00')
    rows = {e['name']: e for e in parse_post_events(post, 'wuthering_waves', '3.7')}
    permanent = rows['故梦寻契']
    assert permanent['start_date'] == '2026-09-30'
    assert permanent['permanent'] is True and permanent['end_precision'] == 'permanent'
    assert permanent['end_at'] is None and permanent.get('end_date') is None
    opening = rows['中期开放']
    assert opening['start_date'] == '2026-10-15' and opening['end_at'] is None
    assert opening.get('end_date') is None and opening.get('start_at') is None


def test_untrusted_or_conflicting_maintenance_never_resolves_unknown_start():
    for extra in [{'source_name': '玩家投稿'}, {'game_id': 'nte'}]:
        post = notice('3.7版本内容说明\n维护时间：2026年9月30日04:00\n'
                      '[待定]活动\n活动时间：3.7版本更新后 ~ 2026年11月1日10:00',
                      published='2026-09-30T02:00:00+00:00')
        post.update(extra)
        rows = parse_post_events(post, 'wuthering_waves', '3.7')
        assert not rows or all(e.get('start_date') is None for e in rows)
    mismatch = notice('3.8版本内容说明\n维护时间：2026年11月12日04:00\n'
                      '[待定]活动\n活动时间：3.7版本更新后 ~ 2026年12月1日10:00',
                      published='2026-10-14T04:00:00+00:00')
    assert parse_post_events(mismatch, 'wuthering_waves', '3.7')[0].get('start_date') is None


def test_maintenance_end_day_can_cross_midnight_but_start_alone_is_insufficient():
    for maintenance, expected in [
        ('2026年9月30日23:00 ~ 2026年10月1日03:00', '2026-10-01'),
        ('2026年9月30日23:00 ~ 03:00', '2026-10-01'),
        ('2026年9月30日04:00', None),
    ]:
        post = notice('3.7版本内容说明\n更新维护时间：'+maintenance+'\n'
                      '[开放]活动\n活动时间：3.7版本更新后 ~ 2026年11月1日10:00',
                      published='2026-09-30T02:00:00+00:00')
        row = parse_post_events(post, 'wuthering_waves', '3.7')[0]
        assert row.get('start_date') == expected
        assert row['start_at'] is None
    explicit = notice('3.7版本内容说明\n更新维护时间：2026年9月30日23:00 ~ 2026年10月1日03:00\n'
                      '[开放]活动\n活动时间：9月30日维护后 ~ 2026年11月1日10:00',
                      published='2026-09-30T02:00:00+00:00')
    assert parse_post_events(explicit, 'wuthering_waves', '3.7')[0]['start_date'] == '2026-10-01'


def test_newer_announced_pool_placeholder_gets_dates_from_explicit_shared_pool_notice():
    base = notice('3.7版本内容说明\n更新维护时间：2026年9月30日04:00 ~ 11:00\n'
                  '[版本活动]活动\n活动时间：3.7版本更新后 ~ 2026年11月11日03:59\n'
                  '※可通过「但愿长圆如此夜」角色活动唤取获得。\n'
                  '※可通过「玉阙玄华」武器活动唤取获得。\n'
                  '※可通过「沉冥」武器活动唤取获得。',
                  published='2026-09-30T02:00:00+00:00')
    pools = notice('3.7版本唤取第一期\n'
                   '「但愿长圆如此夜」、「曙暮一线之间」角色活动唤取，「玉阙玄华」、「昙切」武器活动唤取限时开启！\n'
                   '活动时间：3.7版本更新后 ~ 2026年10月22日09:59',
                   id='2', published='2026-09-29T03:00:00+00:00')
    rows = {e['name']:e for e in calendar_from_posts([base, pools], 'wuthering_waves', NOW)['events']}
    for name in ('但愿长圆如此夜', '玉阙玄华'):
        assert rows[name]['start_date'] == '2026-09-30'
        assert rows[name]['end_at'] == '2026-10-22T09:59:00+08:00'
        assert rows[name]['date_source']['source_post_id'] == '2'
    assert rows['沉冥']['start_at'] is None and rows['沉冥']['end_at'] is None


def test_nte_event_model_retains_maintenance_evidence_and_permanent_boundary():
    from game_assistant.adapters.neverness.data_models import NteCalendarEvent
    post = notice('1.4版本更新公告\n更新维护时间：2026年9月24日06:00 - 11:00\n'
                  '● 「常驻玩法」限时活动\n开放时间：1.4版本更新后永久开放',
                  published='2026-09-23T06:00:00+00:00')
    row = NteCalendarEvent(**{**parse_post_events(post, 'nte', '1.4')[0], 'source':'community'})
    serialized = row.model_dump(mode='json')
    assert serialized['start_source']['post_id'] == '1'
    assert serialized['start_estimated'] is True and serialized['permanent'] is True
    assert serialized['end_precision'] == 'permanent'


def test_qq_calendar_projection_retains_relative_day_and_permanent_evidence():
    from game_assistant.qq.render_snapshot import calendar_snapshot
    from types import SimpleNamespace
    event = dict(name='故梦寻契', start_date='2026-09-30', start_at=None,
                 start_precision='relative', permanent=True, end_precision='permanent',
                 start_estimated=True, start_source=dict(post_id='1', title='维护公告', time_text='04:00~11:00'))
    snap = SimpleNamespace(payload=[event], fetched_at=NOW.isoformat(), state='ok', complete=None)
    row = calendar_snapshot({'wuthering_waves':snap}, NOW)['display_data']['snapshots']['wuthering_waves']['events']['payload'][0]
    assert row['permanent'] is True and row['start_estimated'] is True
    assert row['start_source']['post_id'] == '1'


def test_relative_and_permanent_dates_do_not_leak_across_unrecognized_section_headers():
    wuwa = notice('3.7版本内容说明\n更新维护时间：2026年9月30日04:00 ~ 11:00\n'
                   '[索拉里斯回归邀约]网页活动\n活动时间：3.7版本更新后 ~ 2026年11月11日23:59\n'
                   '【全新常驻玩法】：\n「心影映花」\n玩法描述\n开放时间：3.7版本更新后永久开放',
                   published='2026-09-30T02:00:00+00:00')
    rows = parse_post_events(wuwa, 'wuthering_waves', '3.7')
    assert len(rows) == 1 and not rows[0].get('permanent')
    assert rows[0]['end_at'] == '2026-11-11T23:59:00+08:00'
    nte = notice('1.4版本更新公告\n更新维护时间：2026年9月24日06:00 - 11:00\n'
                  '● 「像素溢出」限时活动\n活动时间：10月12日05:00-10月19日04:59\n'
                  '玩法说明\n七、其他内容\n● 都市大亨「噗卡计划」\n开启时间：1.4版本更新后',
                  published='2026-09-23T06:00:00+00:00')
    rows = parse_post_events(nte, 'nte', '1.4')
    assert len(rows) == 1 and rows[0]['start_date'] == '2026-10-12'
