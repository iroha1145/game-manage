"""Synthetic contracts for the observed ship-template / hashed-roster IDs."""
from copy import deepcopy

import pytest

from game_assistant.adapters.endfield.skland_parse import parse_card
from game_assistant.endfield_reports import build_endfield_report


TEMPLATE_ID = 'chr_0001_synthetic'
ROSTER_ID = 'b502b198aae7646afc58efb076f8439d'  # MD5 of TEMPLATE_ID, UTF-8.
AVATAR = 'https://bbs.hycdn.cn/image/synthetic.png'
STAMP = '2026-10-15T12:00:00+00:00'


def resident(payload):
    return build_endfield_report(payload)['ship']['rooms'][0]['operators'][0]


def test_parser_joins_observed_hashed_roster_shape_without_rewriting_ids():
    source = {
        'chars': [{'id': ROSTER_ID, 'charData': {
            'id': ROSTER_ID, 'name': '合成干员', 'avatarSqUrl': AVATAR}}],
        'spaceShip': {'rooms': [{'id': 'synthetic-room', 'chars': [{
            'charId': TEMPLATE_ID, 'physicalStrength': 0, 'favorability': 0}]}]},
    }
    original = deepcopy(source)
    payload = parse_card(source, fetched_at=STAMP)
    parsed = payload['report']['ship']['rooms'][0]['operators'][0]
    assert parsed['id'] == TEMPLATE_ID
    assert parsed['name'] == '合成干员' and parsed['avatar_url'] == AVATAR
    assert parsed['mood_raw'] == parsed['trust_raw'] == 0
    assert payload['operators'][0]['id'] == payload['operators'][0]['char_id'] == ROSTER_ID
    assert payload['ship'][0]['operators'][0]['charId'] == TEMPLATE_ID
    assert source == original
    # Existing normalized snapshots can rebuild the same link without a refetch.
    legacy = deepcopy(payload)
    legacy.pop('report')
    assert build_endfield_report(legacy, fetched_at=STAMP) == payload['report']


@pytest.mark.parametrize('key', ['id', 'char_id'])
def test_hashed_join_uses_either_exact_roster_key(key):
    payload = {'operators': [{key: ROSTER_ID, 'name': '合成干员', 'avatar_url': AVATAR}],
               'ship': [{'operators': [{'charId': TEMPLATE_ID}]}]}
    original = deepcopy(payload)
    linked = resident(payload)
    assert linked['name'] == '合成干员' and linked['avatar_url'] == AVATAR
    assert linked['id'] == TEMPLATE_ID and payload == original


def test_direct_roster_identity_takes_precedence_over_its_hash():
    payload = {'operators': [
        {'id': TEMPLATE_ID, 'name': '原ID精确匹配', 'avatar_url': AVATAR},
        {'id': ROSTER_ID, 'name': '哈希匹配', 'avatar_url': 'https://bbs.hycdn.cn/hash.png'},
    ], 'ship': [{'operators': [{'charId': TEMPLATE_ID}]}]}
    linked = resident(payload)
    assert linked['name'] == '原ID精确匹配' and linked['avatar_url'] == AVATAR


def test_observed_resident_name_retains_precedence_after_hash_lookup():
    payload = {'operators': [{'id': ROSTER_ID, 'name': '干员名称', 'avatar_url': AVATAR}],
               'ship': [{'operators': [{'charId': TEMPLATE_ID, 'name': '驻守名称'}]}]}
    linked = resident(payload)
    assert linked['name'] == '驻守名称' and linked['avatar_url'] == AVATAR


@pytest.mark.parametrize('identity', [
    'chr_0002_synthetic', 'chr_0001_synthetic_extra', 'chr_0001_SYNTHETIC',
    ' chr_0001_synthetic', 'chr_0001_synthetic ', '0001_synthetic',
    'chr_001_synthetic', 'chr_00001_synthetic', 'chr_0001_合成', 'legacy-instance',
])
def test_unknown_or_noncanonical_template_does_not_borrow_an_operator(identity):
    payload = {'operators': [{'id': ROSTER_ID, 'name': '不能借用'}],
               'ship': [{'operators': [{'charId': identity}]}]}
    linked = resident(payload)
    assert linked['id'] == identity
    assert linked['name'] is None and linked['avatar_url'] is None


def test_non_template_identity_does_not_get_hashed_even_when_digest_exists():
    payload = {'operators': [{'id': 'c98ba09b4eff7e2b13966c426b6faa94', 'name': '不应匹配'}],
               'ship': [{'operators': [{'charId': 'legacy-instance'}]}]}
    assert resident(payload)['name'] is None


def test_hash_lookup_remains_scoped_to_ship_residents():
    payload = {'operators': [{'id': ROSTER_ID, 'name': '合成干员'}],
               'regions': [{'settlements': [{'officer_char_ids': [TEMPLATE_ID]}]}],
               'ship': [{'operators': [{'charId': TEMPLATE_ID}]}]}
    report = build_endfield_report(payload)
    assert report['ship']['rooms'][0]['operators'][0]['name'] == '合成干员'
    assert report['regions']['items'][0]['settlements'][0]['officers'][0]['name'] is None
