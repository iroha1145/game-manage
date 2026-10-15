"""TEST ONLY: invented FixtureScale catalog and MAP -> typed reference LIST.

Never imported by production. Missing fixture references still retain the known
fixture main ID so UNKNOWN_MAIN_REFERENCE differs from UNKNOWN_MAINSTAT.
"""
from copy import deepcopy

from game_assistant.assessment_nte_math import ScoreInput, ScoringSpec
from game_assistant.assessment_nte_math import InventoryError


def fixture_spec(data):
    raw = deepcopy(data)
    raw['catalog'] = [dict(canonical_id=name, label=name, kinds=['drive', 'cartridge'],
        main=name == 'fixture_main', sub=name != 'fixture_main',
        unit='ratio' if name in ('fixture_main', 'fixture_atk_percent') else 'flat')
        for name in [*data['eligible_substats'], 'fixture_main']]
    raw['mainstat_reference_values'] = [dict(canonical_id=name, value=ref['value'], unit=ref['unit'],
        context={'kind':'cartridge', 'scope':ref['context']})
        for name,ref in data['mainstat_reference_values'].items()]
    try:
        return ScoringSpec.model_validate(raw)
    except ValueError:
        raise InventoryError('INVALID_SPEC','Synthetic fixture definition is invalid.',422) from None


def fixture_item(data):
    raw = deepcopy(data)
    if isinstance(raw.get('area'), int):
        raw['area'] = str(raw['area'])
    if raw.get('mainstat') and 'context' in raw['mainstat']:
        raw['mainstat']['context'] = {'kind':raw['kind'], 'scope':raw['mainstat']['context']}
    return ScoreInput.model_validate(raw)
