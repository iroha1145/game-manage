import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
import pytest
from game_assistant.assessment_nte_math import InventoryError,normalize_ratio,score_item
from tests.assessment_fixture_adapter import fixture_item,fixture_spec
GOLDEN=json.loads((Path(__file__).parent/"fixtures/assessment-nte-golden.json").read_text())

@pytest.mark.parametrize('case', GOLDEN['cases'], ids=lambda c:c['id'])
def test_adopted_goldens(case):
    result = score_item(fixture_item(case['item']), case['profile'], fixture_spec(case['spec']))
    expected = case['expected']
    assert result.status == expected['status']
    assert result.reason == expected['reason']
    assert result.value == (Decimal(expected['value']) if expected['value'] is not None else None)
    if result.status != 'scored':
        assert result.contributions == []
        return
    exact = sum((Fraction(int(c.exact_fraction.numerator), int(c.exact_fraction.denominator)) for c in result.contributions), Fraction())
    for prefix,field in [('main:', 'main_total'), ('sub:', 'sub_total')]:
        if field in expected:
            subtotal = sum((Fraction(int(c.exact_fraction.numerator),int(c.exact_fraction.denominator)) for c in result.contributions if c.contribution_id.startswith(prefix)), Fraction())
            assert subtotal == Fraction(Decimal(expected[field]))
    if 'exact_total' in expected:
        assert exact == Fraction(int(expected['exact_total']['numerator']), int(expected['exact_total']['denominator']))
    adjustment = Fraction(int(result.rounding_adjustment_fraction.numerator), int(result.rounding_adjustment_fraction.denominator))
    assert exact + adjustment == Fraction(result.value)
    with localcontext() as context:
        context.prec = 4096
        assert sum((c.value for c in result.contributions), Decimal()) + result.rounding_adjustment == result.value
    assert result.model_validate_json(result.model_dump_json()) == result
    if case['id']=='same-observation-duplicate-count-once':
        assert result.collapsed_observation_ids


@pytest.mark.parametrize('case', GOLDEN['rejected_inputs'], ids=lambda c:c['id'])
def test_rejected_goldens(case):
    baseline = GOLDEN['cases'][3]
    with pytest.raises(InventoryError) as caught:
        spec = fixture_spec(case.get('spec',baseline['spec']))
        item = fixture_item(case.get('item',baseline['item']))
        score_item(item, case.get('profile',baseline['profile']), spec)
    assert caught.value.code == case['error_code']


def test_percent_thirty_equals_ratio_point_three():
    assert normalize_ratio('30%') == normalize_ratio(Decimal('0.30'), 'ratio') == normalize_ratio(Decimal('30'),'percent') == Decimal('0.30')


@pytest.mark.parametrize('number', ['30', Decimal('0.30'), '1e1000000000', '0.'+'1'*33, 0.3])
def test_bare_number_without_unit_rejected(number):
    with pytest.raises(InventoryError):
        normalize_ratio(number)
