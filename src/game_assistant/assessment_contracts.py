"""Narrow pure single-item scoring contracts, extracted from local GPL project. No inventory or account storage."""
from decimal import Decimal
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, BeforeValidator, PlainSerializer, model_validator

EquipmentKind = Literal['drive', 'cartridge']


def decimal_input(value):
    if isinstance(value, str):
        if len(value) > 64 or re.fullmatch(r'-?[0-9]+(?:\.[0-9]{1,32})?', value, flags=re.ASCII) is None:
            raise ValueError('bounded fixed-point Decimal required')
        value = Decimal(value)
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError('finite Decimal string required')
    if abs(value.as_tuple().exponent) > 64 or len(value.as_tuple().digits) > 64:
        raise ValueError('bounded fixed-point Decimal required')
    text = format(value, 'f')
    if len(text) > 64 or re.fullmatch(r'-?[0-9]+(?:\.[0-9]{1,32})?', text, flags=re.ASCII) is None:
        raise ValueError('bounded fixed-point Decimal required')
    return value


FiniteDecimal = Annotated[Decimal, BeforeValidator(decimal_input), PlainSerializer(lambda v: format(v, 'f'), return_type=str, when_used='json')]

def decimal_output(value):
    # Score outputs are generated internally and retain 50-digit reconciliation.
    # Unlike custom input, they must survive serialization without truncation.
    if isinstance(value, str):
        if len(value) > 4096 or re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?', value, flags=re.ASCII) is None:
            raise ValueError('finite bounded output Decimal required')
        value = Decimal(value)
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError('finite bounded output Decimal required')
    sign, digits, exponent = value.as_tuple()
    if abs(exponent) > 4096 or len(digits) > 4096:
        raise ValueError('finite bounded output Decimal required')
    # Predict fixed-point JSON length without allocating a potentially enormous
    # expansion. Include sign, decimal point and leading zero before fractional
    # values. Decimal formats zero with a nonnegative exponent as a single zero.
    if exponent >= 0:
        rendered_length = 1 if value.is_zero() else len(digits) + exponent
    elif len(digits) + exponent > 0:
        rendered_length = len(digits) + 1
    else:
        rendered_length = 2 - exponent
    if rendered_length + sign > 4096:
        raise ValueError('finite bounded output Decimal required')
    return value

ResultDecimal = Annotated[Decimal, BeforeValidator(decimal_output), PlainSerializer(lambda v: format(v, 'f'), return_type=str, when_used='json')]
Identifier = Annotated[str, Field(min_length=1, max_length=256)]
# Generated score names add at most "main:" to an accepted canonical ID.
# This is an output-only allowance; catalog and other identifiers stay bounded.
ContributionIdentifier = Annotated[str, Field(min_length=1, max_length=261)]
class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ExactFraction(Contract):
    numerator: str
    denominator: str


class ScoreContribution(Contract):
    contribution_id: ContributionIdentifier
    value: ResultDecimal
    exact_fraction: ExactFraction | None = None
    weight: FiniteDecimal | None = None
    factor: FiniteDecimal | None = None
    unit: str | None = None
    reference_value: FiniteDecimal | None = None
    current_value: ResultDecimal | None = None


class ScoreResult(Contract):
    status: Literal['scored', 'unscorable', 'unconfigured']
    value: ResultDecimal | None = None
    contributions: list[ScoreContribution] = Field(default_factory=list)
    reason: str | None = None
    score_version: Identifier
    weight_version: Identifier
    rounding_adjustment: ResultDecimal | None = None
    rounding_adjustment_fraction: ExactFraction | None = None
    collapsed_observation_ids: list[Identifier] = Field(default_factory=list)

    @model_validator(mode='after')
    def score_status(self):
        if self.status == 'scored' and self.value is None:
            raise ValueError('scored requires a real value, including zero')
        if self.status != 'scored' and (self.value is not None or self.contributions or not self.reason):
            raise ValueError('unscorable/unconfigured requires null value, no contributions and reason')
        return self


class WeightProfile(Contract):
    character_id: Identifier
    version: Identifier
    source: Identifier
    substat_weights: dict[str, FiniteDecimal]
    mainstat_weights: dict[str, FiniteDecimal]

    @model_validator(mode='after')
    def domain(self):
        if any(not 0 <= v <= 100 for v in [*self.substat_weights.values(), *self.mainstat_weights.values()]):
            raise ValueError('weight must be in [0,100]')
        return self


class MainstatReference(Contract):
    canonical_id: Identifier
    value: FiniteDecimal
    unit: Literal['flat', 'ratio']
    context: dict[str, str | int]

    @model_validator(mode='after')
    def positive(self):
        if self.value <= 0 or self.context.get('kind') not in ('drive', 'cartridge'):
            raise ValueError('positive reference and explicit equipment context required')
        return self


class ScoreSpec(Contract):
    version: Identifier
    quality_factors: dict[str, FiniteDecimal] = Field(default_factory=dict)
    eligible_substats: list[Identifier] = Field(default_factory=list)
    mainstat_reference_values: list[MainstatReference] = Field(default_factory=list)

    @model_validator(mode='after')
    def custom_spec(self):
        if len(set(self.eligible_substats)) != len(self.eligible_substats):
            raise ValueError('unique eligible IDs required')
        if any(v < 0 for v in self.quality_factors.values()):
            raise ValueError('nonnegative factors required')
        return self
