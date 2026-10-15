from copy import deepcopy

import pytest

from game_assistant.adapters.endfield.skland_parse import parse_card, parse_operator
from game_assistant.endfield_reports import build_endfield_report, build_gacha_report


STAMP = '2026-10-15T12:00:00+00:00'


def test_observed_time_and_known_daily_tasks_do_not_infer_unobserved_completion():
    card = parse_card({'base': {'roleId': 'r1'}, 'currentTs': 1792065540,
                       'dungeon': {'curStamina': 0, 'maxStamina': 240},
                       'dailyMission': {'dailyActivation': 0, 'maxDailyActivation': 100},
                       'weeklyMission': {'score': 10},
                       'bpSystem': {'curLevel': 1, 'maxLevel': 60}}, fetched_at=STAMP)
    report = card['report']
    assert report['schema_version'] == 1
    assert report['observed_at'] != report['fetched_at'] == STAMP
    assert report['overview']['stamina']['percent'] == 0
    assert report['overview']['stamina']['remaining'] == 240
    assert [(item['id'], item['remaining']) for item in report['overview']['todos']] == [('daily', 100)]
    assert report['overview']['progress'][1]['state'] == 'unknown'
    absent = parse_card({}, fetched_at=STAMP)['report']
    assert absent['observed_at'] is None
    assert absent['overview']['stamina']['current'] is None
    assert not absent['overview']['todos']
    assert absent['training']['summary']['listed_count'] is None
    assert absent['ship']['summary']['room_count'] is None
    empty = parse_card({'chars': [], 'domain': [], 'spaceShip': {'rooms': []}}, fetched_at=STAMP)['report']
    assert empty['training']['summary']['listed_count'] == 0
    assert empty['regions']['summary']['region_count'] == 0
    assert empty['ship']['summary']['room_count'] == 0


def test_training_keeps_zero_phase_and_uses_known_level_denominator_stably():
    payload = {'base': {'char_count': 4}, 'operators': [
        {'id': 'b', 'name': 'B', 'level': 40, 'rarity': 5, 'evolve_phase': 0},
        {'id': 'a', 'name': 'A', 'level': 40, 'rarity': 6, 'evolve_phase': 2},
        {'id': 'c', 'name': 'C', 'level': None, 'rarity': None, 'evolve_phase': None},
        {'id': 'd', 'name': 'D', 'level': 0, 'rarity': 4, 'evolve_phase': 0}]}
    original = deepcopy(payload)
    report = build_endfield_report(payload)
    assert payload == original
    assert [item['id'] for item in report['training']['items']] == ['a', 'b', 'd', 'c']
    summary = report['training']['summary']
    assert summary['known_levels'] == 3 and summary['average_level'] == 26.7
    assert summary['phase_counts'] == {'2': 1, '0': 2}
    assert summary['rarity_counts'] == {'6': 1, '5': 1, '4': 1}


def test_regions_use_roster_names_and_only_compute_gaps_when_totals_known():
    payload = parse_card({'chars': [{'id': 'instance', 'charData': {'id': 'char1', 'name': '佩丽卡'}}],
                         'domain': [{'domainId': 'region1', 'moneyMgr': {'count': 0, 'total': 100},
                                     'settlements': [{'id': 's1', 'remainMoney': 5, 'moneyMax': 20,
                                                      'officerCharIds': ['char1', 'missing']}],
                                     'levels': [{'levelId': 'area1', 'name': '地区一',
                                                 'puzzleCount': {'count': 2, 'total': 3},
                                                 'equipTrchestCount': {'count': 0, 'total': 1}}],
                                     'collections': [{'levelId': 'area1', 'puzzleCount': 2},
                                                     {'levelId': 'area2', 'equipTrchestCount': 3}]}]}, fetched_at=STAMP)
    region = payload['report']['regions']['items'][0]
    assert region['money']['remaining'] == 100
    assert region['settlements'][0]['coupon']['remaining'] == 15
    assert [item['name'] for item in region['settlements'][0]['officers']] == ['佩丽卡', None]
    assert len(region['areas']) == 2
    first = {item['key']: item for item in region['areas'][0]['collections']}
    assert first['puzzles']['remaining'] == 1 and first['equipment_chests']['remaining'] == 1
    assert first['chests']['remaining'] is None
    second = {item['key']: item for item in region['areas'][1]['collections']}
    assert second['equipment_chests']['current'] == 3
    assert second['equipment_chests']['percent'] is None


def test_ship_keeps_observed_raw_values_without_unverified_percent_conversion():
    card = parse_card({'chars': [{'id': 'char1', 'charData': {'name': '佩丽卡'}}],
                       'spaceShip': {'rooms': [{'id': 'room1', 'chars': [
                           {'charId': 'char1', 'physicalStrength': 0, 'favorability': 1500},
                           {'charId': 'unknown'}]}]}}, fetched_at=STAMP)
    ship = card['report']['ship']
    assert ship['summary'] == {'room_count': 1, 'staffed_rooms': 1, 'operator_slots': 2}
    residents = ship['rooms'][0]['operators']
    assert residents[0]['name'] == '佩丽卡'
    assert residents[0]['mood_raw'] == 0 and residents[0]['trust_raw'] == 1500
    assert residents[1]['mood_raw'] is None and residents[1]['name'] is None
    assert 'percent' not in residents[0]


def test_old_card_rebuilds_reports_without_trusting_cached_derived_data():
    old = {'base': {'role_id': 'new-role'}, 'stamina': {'current': 3, 'maximum': 5},
           'progress': [{'name': '每日活跃', 'cur': 1, 'total': 2}],
           'operators': [], 'ship': [],
           'report': {'overview': {'base': {'role_id': 'old-role'}}}}
    report = build_endfield_report(old, fetched_at=STAMP)
    assert report['overview']['base']['role_id'] == 'new-role'
    assert report['overview']['todos'][0]['id'] == 'daily'
    assert report['training']['available'] is None  # Older [] did not prove a successful empty read.
    assert report['observed_at'] is None


def test_absent_residents_and_settlements_are_unknown_and_partial_area_counts_merge():
    card = parse_card({'spaceShip': {'rooms': [{'id': 'r'}]},
                       'domain': [{'domainId': 'd', 'levels': [{'levelId': 'a'}],
                                   'collections': [{'levelId': 'a', 'trchestCount': 4}]}]}, fetched_at=STAMP)
    assert card['report']['ship']['summary']['operator_slots'] is None
    assert card['report']['regions']['summary']['settlement_count'] is None
    chests = card['report']['regions']['items'][0]['areas'][0]['collections'][0]
    assert chests['current'] == 4 and chests['remaining'] is None
    assert build_gacha_report({})['pending'] is None


def test_operator_detail_additions_preserve_zero_and_equipment_slots():
    operator = parse_operator({'id': 'i1', 'evolvePhase': 0, 'potentialLevel': 0,
                               'charData': {'id': 'c1', 'rarity': {'value': 0, 'key': 'fallback'}},
                               'bodyEquip': {'equipData': {'name': '护甲'}}})
    assert operator['char_id'] == 'c1' and operator['evolve_phase'] == 0
    assert operator['rarity'] == 0 and operator['potential'] == 0
    assert operator['equipment'][0]['slot_name'] == '护甲'


def test_gacha_averages_only_exact_observed_intervals_and_keeps_gap_qualifiers():
    payload = {'role_id': 'r1', 'total': 120, 'complete': False, 'pools': [
        {'key': 'special', 'label': '特许', 'total': 100, 'six_star': 2, 'five_star': 10, 'free': 10,
         'gaps': 1, 'pending': True, 'since_last_six': {'count': 30, 'status': 'lower_bound'},
         'history': [{'name': 'A', 'pulls': 20, 'status': 'exact', 'obtained_at': 2},
                     {'name': 'B', 'pulls': 5, 'status': 'lower_bound', 'obtained_at': 1}]},
        {'key': 'weapon', 'label': '武器', 'total': 20, 'six_star': 1, 'five_star': 2, 'free': 0,
         'gaps': 0, 'pending': False, 'history': [{'name': 'C', 'pulls': 10, 'status': 'exact', 'obtained_at': 3}]}]}
    original = deepcopy(payload)
    report = build_gacha_report(payload)
    assert payload == original
    assert report['six_star'] == 3 and report['five_star'] == 12 and report['free'] == 10
    assert report['gaps'] == 1 and report['pending'] is True
    assert report['known_exact_intervals'] == 2 and report['average_exact_pulls'] == 15
    assert [item['name'] for item in report['history']] == ['C', 'A', 'B']
    assert report['pools'][0]['since_last_six']['status'] == 'lower_bound'
    assert build_gacha_report({})['total'] is None
    assert build_gacha_report({'total': 0, 'pools': []})['six_star'] == 0
    assert build_gacha_report({'total': 1, 'pools': [{'six_star': None}]})['six_star'] is None


@pytest.mark.parametrize('complete,expected', [(False, True), (True, False), (None, None)])
@pytest.mark.parametrize('pools', [[], [{'total': 2, 'pending': False}]])
def test_gacha_coverage_accounts_for_empty_or_unvisited_pools(complete, expected, pools):
    report = build_gacha_report({'total': sum(pool['total'] for pool in pools), 'complete': complete, 'pools': pools})
    assert report['complete'] is complete
    assert report['pending'] is expected


@pytest.mark.parametrize('current,total', [(None, 10), (0, None), (0, 0), (True, 10), (-1, 10)])
def test_unknown_or_invalid_measurement_never_becomes_complete(current, total):
    report = build_endfield_report({'progress': [{'id': 'daily', 'cur': current, 'total': total}]})
    assert report['overview']['progress'][0]['state'] == 'unknown'
    assert report['overview']['todos'] == []


def test_honor_report_preserves_full_list_and_observed_variants_without_inventing_totals():
    source = {'achieve': {'count': 0, 'achieveMedals': [
        {'achievementData': {'id': str(i), 'name': '勋章' + str(i), 'initIcon': 'init',
                             'reforge2Icon': 'two', 'reforge3Icon': 'three', 'platedIcon': 'plated'},
         'level': 3, 'isPlated': i == 0, 'obtainTs': 1792029600} for i in range(12)]}}
    original = deepcopy(source)
    report = parse_card(source, fetched_at=STAMP)['report']['honor']
    assert report['available'] is True
    assert report['summary'] == {'declared_count': 0, 'listed_count': 12}
    assert len(report['items']) == 12
    assert report['items'][0]['icon_url'] == 'plated'
    assert report['items'][1]['icon_url'] == 'three'
    assert report['items'][0]['obtained_at'].startswith('2026-')
    assert source == original


def test_honor_distinguishes_successful_empty_from_absent_and_legacy_empty():
    empty = parse_card({'achieve': {'count': 0, 'achieveMedals': []}}, fetched_at=STAMP)['report']['honor']
    assert empty['available'] is True and empty['summary']['listed_count'] == 0
    absent = parse_card({}, fetched_at=STAMP)['report']['honor']
    assert absent['available'] is False and absent['summary']['listed_count'] is None
    legacy = build_endfield_report({'achievements': {'count': 10, 'medals': []}})['honor']
    assert legacy['available'] is None and legacy['summary']['listed_count'] is None
    assert legacy['summary']['declared_count'] == 10


@pytest.mark.parametrize('level,plated,expected', [(0, False, 'init'), (2, False, 'two'),
    (3, False, 'three'), (0, True, 'plated'), (None, None, 'init')])
def test_honor_icon_selection_uses_only_observed_level_and_plating(level, plated, expected):
    medal = {'achievementData': {'initIcon': 'init', 'reforge2Icon': 'two',
                                'reforge3Icon': 'three', 'platedIcon': 'plated'},
             'level': level, 'isPlated': plated, 'obtainTs': 'invalid'}
    item = build_endfield_report({'achievements': {'medals': [medal]}})['honor']['items'][0]
    assert item['icon_url'] == expected
    assert item['obtained_at'] is None
    assert item['is_plated'] == plated


def test_collection_only_areas_keep_distinct_labels_without_guessing_unknown_ids():
    report = build_endfield_report({'regions': [{'collections': [
        {'level_id': 'map01_lv001', 'chest_count': 0},
        {'level_id': 'map02_lv001', 'name': '上游新名称'},
        {'level_id': 'future_area'},
    ]}]})
    areas = report['regions']['items'][0]['areas']
    assert [area['name'] for area in areas] == ['枢纽区', '上游新名称', 'future_area']
    assert areas[0]['collections'][0]['current'] == 0
    assert areas[0]['collections'][0]['total'] is None


def test_collection_name_wins_over_static_fallback_but_not_explicit_level_name():
    regions = [{'levels': [{'id': 'map01_lv001'}, {'id': 'map02_lv001', 'name': '关卡上游名称'}],
                'collections': [{'level_id': 'map01_lv001', 'name': '收集上游新名称', 'chest_count': 0},
                                {'level_id': 'map02_lv001', 'name': '次要名称'}]}]
    areas = build_endfield_report({'regions': regions})['regions']['items'][0]['areas']
    assert [area['name'] for area in areas] == ['收集上游新名称', '关卡上游名称']
    assert areas[0]['collections'][0]['current'] == 0
