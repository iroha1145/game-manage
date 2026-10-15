"""Optional operator acquisition times use the observed ownTs path only."""
from copy import deepcopy

import pytest

from game_assistant.adapters.endfield.skland_parse import parse_card, parse_operator
from game_assistant.endfield_reports import build_endfield_report


ACQUIRED = '2023-11-14T22:13:20+00:00'
FETCHED = '2026-10-15T12:00:00+00:00'


@pytest.mark.parametrize('raw', [1_700_000_000, '1700000000', 1_700_000_000.0,
                               1_700_000_000_000, '1700000000000'])
def test_operator_obtained_at_uses_existing_utc_seconds_and_milliseconds_contract(raw):
    source = {'id': 'instance', 'charData': {'id': 'character'}, 'ownTs': raw, 'level': 0}
    original = deepcopy(source)
    operator = parse_operator(source)
    assert operator['obtained_at'] == ACQUIRED
    assert operator['level'] == 0
    assert source == original
    card = parse_card({'chars': [source]}, fetched_at=FETCHED)
    assert card['operators'][0]['obtained_at'] == ACQUIRED
    assert card['report']['training']['items'][0]['obtained_at'] == ACQUIRED
    assert card['report']['fetched_at'] == FETCHED


@pytest.mark.parametrize('raw', [None, '', ' ', 0, '0', -1, '-1', True, False,
    {}, [], (), 'unknown', 'NaN', 'Infinity', '0x10', '1700000000.5',
    1_700_000_000.5, float('nan'), float('inf'), float('-inf'), 10**400,
    '9' * 5000, 253_402_300_800_000])
def test_malformed_optional_own_ts_stays_unknown_without_losing_the_card(raw):
    source = {'id': 'instance', 'ownTs': raw, 'level': 0}
    operator = parse_operator(source)
    assert operator['obtained_at'] is None
    assert operator['id'] == 'instance' and operator['level'] == 0
    card = parse_card({'chars': [source]}, fetched_at=FETCHED)
    assert card['operators'][0]['obtained_at'] is None
    assert card['report']['training']['items'][0]['obtained_at'] is None
    assert card['report']['fetched_at'] == FETCHED


def test_missing_own_ts_does_not_infer_from_other_paths_or_snapshot_times():
    source = {'id': 'instance', 'charData': {'ownTs': '1700000000'},
              'obtainTs': '1700000000', 'fetched_at': ACQUIRED}
    assert parse_operator(source)['obtained_at'] is None
    parsed = parse_card({'currentTs': 1_792_065_540, 'chars': [source]}, fetched_at=FETCHED)
    assert parsed['observed_at'] is not None
    assert parsed['report']['training']['items'][0]['obtained_at'] is None


def test_legacy_normalized_reports_keep_observed_acquisition_time_without_backfill():
    payload = {'observed_at': FETCHED, 'operators': [
        {'id': 'known', 'obtained_at': ACQUIRED}, {'id': 'legacy'},
        {'id': 'unknown', 'obtained_at': None},
    ]}
    original = deepcopy(payload)
    items = build_endfield_report(payload, fetched_at=FETCHED)['training']['items']
    assert items[0]['obtained_at'] == ACQUIRED
    assert items[1].get('obtained_at') is None
    assert items[2]['obtained_at'] is None
    assert payload == original
