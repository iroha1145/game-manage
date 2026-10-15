"""Offline contracts for static ship observations, medal categories and loadout."""
from copy import deepcopy

import pytest

from game_assistant.adapters.endfield.skland_parse import parse_card, parse_operator
from game_assistant.endfield_reports import build_endfield_report


STAMP = '2026-10-15T12:00:00+00:00'


def ship_resident(mood=None, trust=None):
    payload = {'ship': [{'operators': [{'charId': 'char', 'physicalStrength': mood, 'favorability': trust}]}]}
    return build_endfield_report(payload)['ship']['rooms'][0]['operators'][0]


@pytest.mark.parametrize('raw,percent,level', [
    (0, 0, '友好'), ('0', 0, '友好'), (3, 1, '友好'), (57, 19, '友好'), (69, 23, '友好'),
    (299, 99, '友好'), (299.999, 99, '友好'), (300, 100, '亲近'), (312, 101, '亲近'),
    (336, 103, '亲近'), (996, 158, '亲近'), ('1064', 163, '亲近'), (1499, 199, '亲近'),
    (1500, 200, '信任'), (1501, 200, '信任'),
])
def test_trust_thresholds_and_exact_integer_percentage_boundaries(raw, percent, level):
    resident = ship_resident(trust=raw)
    assert resident['trust_raw'] == float(raw)
    assert resident['trust_percent'] == percent
    assert resident['trust_level_name'] == level


@pytest.mark.parametrize('raw,percent', [(0, 0), ('0', 0), (6610.129, 66.10129),
    ('4355.929', 43.55929), (5, 0.05), (10000, 100)])
def test_mood_retains_exact_ratio_for_shared_display_rounding(raw, percent):
    resident = ship_resident(mood=raw)
    assert resident['mood_raw'] == float(raw)
    assert resident['mood_percent'] == pytest.approx(percent)


@pytest.mark.parametrize('invalid', [None, '', True, False, -1, '-3', float('nan'), float('inf'),
                                   float('-inf'), 'NaN', 'Infinity', 'unknown', {}, [], 10**400,
                                   '0x10', '0b11', '0o17', '1_0', '３００', '1.2.3', '+'])
def test_invalid_observations_stay_unknown(invalid):
    resident = ship_resident(mood=invalid, trust=invalid)
    assert resident['mood_raw'] is None and resident['trust_raw'] is None
    assert resident['mood_percent'] is None and resident['trust_percent'] is None
    assert resident['trust_level_name'] is None


@pytest.mark.parametrize('raw,expected', [(' +3e2 ', 300), ('3E+2', 300), ('300.', 300),
    ('.5', .5), ('-.0', 0), (' \t+57\n', 57), ('1e-1', .1)])
def test_ship_numeric_strings_share_decimal_grammar_with_browser(raw, expected):
    resident = ship_resident(mood=raw, trust=raw)
    assert resident['mood_raw'] == expected and resident['trust_raw'] == expected
    assert resident['mood_percent'] == expected / 100


def test_out_of_range_mood_keeps_raw_value_without_presenting_a_valid_percent():
    resident = ship_resident(mood=10000.1)
    assert resident['mood_raw'] == 10000.1 and resident['mood_percent'] is None


def test_parser_and_legacy_rebuild_keep_original_times_values_and_input_unchanged():
    source = {'currentTs': 1792065540, 'chars': [{'id': 'char', 'charData': {'name': '佩丽卡'}}],
              'spaceShip': {'rooms': [{'id': 'room', 'type': 0, 'chars': [
                  {'charId': 'char', 'physicalStrength': 6610.129, 'favorability': 1064}]}]}}
    original = deepcopy(source)
    parsed = parse_card(source, fetched_at=STAMP)
    legacy = deepcopy(parsed)
    legacy['report'] = {'schema_version': 1, 'ship': {'rooms': [{'operators': [
        {'id': 'char', 'mood_raw': 9999, 'mood_percent': 99.99, 'trust_percent': 200}]}]}}
    legacy_original = deepcopy(legacy)
    rebuilt = build_endfield_report(legacy, fetched_at=STAMP)
    assert rebuilt == parsed['report']
    assert legacy == legacy_original and source == original
    assert rebuilt['fetched_at'] == STAMP
    assert rebuilt['observed_at'] == parsed['observed_at'] != STAMP
    assert parsed['ship'][0]['operators'][0]['physicalStrength'] == 6610.129
    assert rebuilt['ship']['rooms'][0]['operators'][0]['name'] == '佩丽卡'
    model = rebuilt['ship']['conversion_model']
    assert model == {'id': 'endfield-plugin-spaceship-v3.5.0', 'kind': 'static_observation',
                     'source_url': 'https://github.com/Entropy-Increase-Team/endfield-plugin/blob/main/API.md#L6089-L6123'}
    model['kind'] = 'changed-by-caller'
    assert build_endfield_report(legacy)['ship']['conversion_model']['kind'] == 'static_observation'


@pytest.mark.parametrize('category,expected', [(' 探索 ', '探索'), ('光荣之路', '光荣之路'),
    (None, None), ('', None), (' \n ', None), (0, None), (True, None), ({'name': '探索'}, None), ([], None)])
def test_honor_category_uses_only_observed_nonempty_string(category, expected):
    payload = {'achievements': {'medals': [{'achievementData': {'id': 'medal', 'cateName': category}}]}}
    original = deepcopy(payload)
    assert build_endfield_report(payload)['honor']['items'][0]['category'] == expected
    assert payload == original


@pytest.mark.parametrize('wrapped', [False, True])
def test_tactical_item_direct_and_nested_share_safe_contract(wrapped):
    data = {'id': 'unverified-id', 'name': ' 战术道具 ', 'rarity': {'value': 0, 'key': 6},
            'iconUrl': 'https://bbs.hycdn.cn/image/tactical.png',
            'activeEffect': ' 效果 {0} ', 'passiveEffect': ' 常驻描述 ',
            'activeEffectParams': [99], 'unexpected': {'private': 'synthetic'}}
    char = {'id': 'instance', 'charData': {'id': 'char'},
            'tacticalItem': {'tacticalItemData': data, 'name': 'wrapper-name'} if wrapped else data}
    original = deepcopy(char)
    tactical = parse_operator(char)['tactical_item']
    assert tactical == {'name': '战术道具', 'rarity': 0, 'icon_url': 'https://bbs.hycdn.cn/image/tactical.png',
                        'active_effect': '效果 {0}', 'passive_effect': '常驻描述'}
    assert parse_card({'chars': [char]}, fetched_at=STAMP)['report']['training']['items'][0]['tactical_item'] == tactical
    assert char == original


@pytest.mark.parametrize('raw', [None, {}, [], 'invalid', True, 0, {'tacticalItemData': {}},
    {'name': {}, 'rarity': {'value': []}, 'iconUrl': 'javascript:alert(1)',
     'activeEffect': ['unknown'], 'passiveEffect': True}, {'rarity': 10**400}, {'rarity': float('inf')}])
def test_absent_or_malformed_tactical_item_does_not_fabricate_loadout(raw):
    operator = parse_operator({'id': 'usable', 'level': 0, 'tacticalItem': raw})
    assert operator['id'] == 'usable' and operator['level'] == 0
    assert operator['tactical_item'] is None


@pytest.mark.parametrize('url', ['http://bbs.hycdn.cn/item.png', 'https://example.com/item.png',
    'https://bbs.hycdn.cn/item.svg', 'https://bbs.hycdn.cn/item.png?token=synthetic',
    'https://bbs.hycdn.cn/item.png#secret', 'https://user:pass@bbs.hycdn.cn/item.png',
    'https://bbs.hycdn.cn:8080/item.png', '//bbs.hycdn.cn/item.png', 'data:image/png;base64,AAA',
    'https://bbs.hycdn.cn/../item.png', 'https://bbs.hycdn.cn/%2e%2e/item.png',
    'https://bbs.hycdn.cn/%0aitem.png', 'https://bbs.hycdn.cn/item.png\n', {'url': 'https://bbs.hycdn.cn/item.png'}])
def test_tactical_item_rejects_unsafe_images_without_losing_known_text(url):
    tactical = parse_operator({'tacticalItem': {'name': '已知道具', 'iconUrl': url}})['tactical_item']
    assert tactical['name'] == '已知道具' and tactical['icon_url'] is None


def test_tactical_item_icon_alias_and_enum_label_are_supported_without_effect_coercion():
    tactical = parse_operator({'tacticalItem': {'rarity': {'value': '6'},
        'icon_url': 'https://web.hycdn.cn/item.webp', 'activeEffect': {'text': '不猜结构'}}})['tactical_item']
    assert tactical == {'name': None, 'rarity': '6', 'icon_url': 'https://web.hycdn.cn/item.webp',
                        'active_effect': None, 'passive_effect': None}
