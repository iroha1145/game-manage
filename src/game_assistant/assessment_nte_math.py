"""Pure custom preference math. No built-in game facts or inventory ranking."""
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Literal

from pydantic import Field, model_validator

from .assessment_contracts import (Contract, EquipmentKind, ExactFraction,
                        Identifier, ScoreContribution, ScoreResult, ScoreSpec,
                        WeightProfile, decimal_input)
class InventoryError(ValueError):
    def __init__(self, code, message, status_code):
        self.code, self.status_code = code, status_code
        super().__init__(message)

MATH_VERSION = 'nte-custom-weighting-v1'


def invalid(code):
    return InventoryError(code, 'Custom scoring input is invalid.', 422)


def number(value, code='INVALID_VALUE'):
    try:
        result = decimal_input(value)
        if result < 0:
            raise ValueError
        return result
    except (ValueError, TypeError):
        raise invalid(code) from None


def normalize_ratio(value: str | Decimal, unit: Literal['ratio','percent'] | None = None) -> Decimal:
    if isinstance(value, str) and value.endswith('%'):
        if unit not in (None, 'percent'):
            raise invalid('INVALID_VALUE')
        value, unit = value[:-1], 'percent'
    if unit not in ('ratio', 'percent'):
        raise invalid('INVALID_VALUE')
    parsed = number(value)
    with localcontext() as context:
        context.prec = 128
        return parsed.scaleb(-2) if unit == 'percent' else parsed


class CatalogEntry(Contract):
    canonical_id: Identifier
    label: Identifier
    kinds: list[EquipmentKind] = Field(min_length=1, max_length=2)
    main: bool
    sub: bool
    unit: Literal['flat','ratio']

    @model_validator(mode='after')
    def roles(self):
        if not (self.main or self.sub) or len(set(self.kinds)) != len(self.kinds):
            raise ValueError('explicit unique kinds and a stat role required')
        return self


class ScoringSpec(ScoreSpec):
    catalog: list[CatalogEntry] = Field(default_factory=list, max_length=1000)
    aliases: dict[str, str] = Field(default_factory=dict, max_length=20000)

    @model_validator(mode='after')
    def catalog_contract(self):
        index = {entry.canonical_id:entry for entry in self.catalog}
        if len(index) != len(self.catalog):
            raise ValueError('unique canonical IDs required')
        if any(name not in index or not index[name].sub for name in self.eligible_substats):
            raise ValueError('eligible substat must be declared by catalog')
        if any(not alias or len(alias)>256 or target not in index or (alias in index and alias!=target) for alias,target in self.aliases.items()):
            raise ValueError('exact noncolliding aliases required')
        seen = set()
        for reference in self.mainstat_reference_values:
            entry = index.get(reference.canonical_id)
            if entry is None or not entry.main or reference.unit!=entry.unit or reference.context['kind'] not in entry.kinds:
                raise ValueError('reference catalog, role, unit and kind must match')
            key = (reference.canonical_id, tuple(sorted(reference.context.items())))
            if key in seen or not reference.context or len(reference.context)>32:
                raise ValueError('unique bounded explicit reference context required')
            seen.add(key)
            if any(not k or len(k)>256 or (isinstance(v,str) and (not v or len(v)>256)) or type(v) not in (str,int) for k,v in reference.context.items()):
                raise ValueError('bounded explicit context scalars required')
        return self


class StatInput(Contract):
    canonical_id: str | None = None
    observation_id: str | None = None
    value: str | Decimal | None = None
    unit: str | None = None
    context: dict[str, str | int] = Field(default_factory=dict)


class ScoreInput(Contract):
    kind: EquipmentKind
    quality: str | None = None
    area: str | Decimal | None = None
    substats: list[StatInput] | None = None
    substats_complete: bool | None = None
    mainstat: StatInput | None = None
    adapter_reason: str | None = None


def validate_profile(profile, spec):
    try:
        result = WeightProfile.model_validate(profile.model_dump(mode='python') if isinstance(profile,WeightProfile) else profile)
    except (ValueError, TypeError):
        raise invalid('INVALID_WEIGHT') from None
    entries = {entry.canonical_id:entry for entry in spec.catalog}
    for role,weights in [('sub',result.substat_weights),('main',result.mainstat_weights)]:
        if any(name not in entries or not getattr(entries[name],role) for name in weights):
            raise invalid('INVALID_WEIGHT')
    return result


def _fraction(value):
    return ExactFraction(numerator=str(value.numerator),denominator=str(value.denominator))


def _display(value):
    with localcontext() as context:
        context.prec = 50
        return Decimal(value.numerator) / Decimal(value.denominator)


def _unit_value(stat, entry):
    if stat.unit not in ('flat','ratio','percent_points'):
        return None,'UNKNOWN_UNIT'
    normalized = 'ratio' if stat.unit=='percent_points' else stat.unit
    if normalized != entry.unit:
        return None,'UNIT_MISMATCH'
    if stat.value is None:
        return None,'UNKNOWN_MAIN_VALUE'
    value = number(stat.value)
    return (normalize_ratio(value,'percent') if stat.unit=='percent_points' else value),None


def score_item(item: ScoreInput, profile: WeightProfile, spec: ScoringSpec) -> ScoreResult:
    if not isinstance(spec,ScoringSpec):
        raise invalid('INVALID_SPEC')
    try:
        spec = ScoringSpec.model_validate(spec.model_dump(mode='python'))
    except (ValueError,TypeError):
        raise invalid('INVALID_SPEC') from None
    profile = validate_profile(profile,spec)
    weights = sorted((Fraction(v) for name,v in profile.substat_weights.items() if name in spec.eligible_substats and v>0),reverse=True)
    denominator = sum(weights[:4],Fraction())
    def unavailable(reason, status='unscorable'):
        return ScoreResult(status=status,reason=reason,score_version=spec.version,weight_version=profile.version)
    if denominator==0:
        return unavailable('NO_POSITIVE_ELIGIBLE_WEIGHTS','unconfigured')
    if not isinstance(item,ScoreInput):
        raise invalid('INVALID_VALUE')
    try:
        item=ScoreInput.model_validate(item.model_dump(mode='python'))
    except (ValueError,TypeError):
        raise invalid('INVALID_VALUE') from None
    if item.adapter_reason in ('PROVENANCE_UNAVAILABLE','NORMALIZATION_CONFIG_MISMATCH','CORRECTION_CONFIG_MISMATCH'):
        return unavailable(item.adapter_reason)
    if item.quality not in spec.quality_factors:
        return unavailable('UNKNOWN_QUALITY')
    if item.kind=='drive':
        if item.area is None:
            return unavailable('UNKNOWN_AREA')
        area=number(item.area)
        if area<=0 or area!=area.to_integral_value():
            return unavailable('UNKNOWN_AREA')
    if item.substats_complete is not True or item.substats is None:
        return unavailable('UNKNOWN_SUBSTATS')
    if item.adapter_reason:
        return unavailable(item.adapter_reason)
    entries={entry.canonical_id:entry for entry in spec.catalog}
    resolve=lambda name:spec.aliases.get(name,name)
    distinct={}; rows={}; collapsed=set()
    for stat in item.substats:
        name=resolve(stat.canonical_id)
        entry=entries.get(name)
        if entry is None:
            return unavailable('UNKNOWN_STAT')
        if name not in spec.eligible_substats or not entry.sub or item.kind not in entry.kinds:
            return unavailable('INELIGIBLE_SUBSTAT')
        value,reason=_unit_value(stat,entry)
        if reason:
            return unavailable('UNKNOWN_STAT' if reason=='UNKNOWN_MAIN_VALUE' else reason)
        if not stat.observation_id:
            return unavailable('AMBIGUOUS_DUPLICATE_SUBSTAT')
        identity=(name,value,entry.unit)
        if stat.observation_id in rows and rows[stat.observation_id]!=identity:
            return unavailable('AMBIGUOUS_DUPLICATE_SUBSTAT')
        if name in distinct and distinct[name].observation_id!=stat.observation_id:
            return unavailable('AMBIGUOUS_DUPLICATE_SUBSTAT')
        if stat.observation_id in rows:
            collapsed.add(stat.observation_id)
        rows[stat.observation_id]=identity
        distinct[name]=stat
    quality=spec.quality_factors[item.quality]
    terms=[]
    if item.kind=='cartridge':
        main=item.mainstat
        name=resolve(main.canonical_id) if main else None
        entry=entries.get(name)
        if entry is None or not entry.main or item.kind not in entry.kinds:
            return unavailable('UNKNOWN_MAINSTAT')
        if main.value is None:
            return unavailable('UNKNOWN_MAIN_VALUE')
        current,reason=_unit_value(main,entry)
        if reason:
            return unavailable(reason)
        references=[r for r in spec.mainstat_reference_values if r.canonical_id==name]
        if not references:
            return unavailable('UNKNOWN_MAIN_REFERENCE')
        matches=[r for r in references if all(type(main.context.get(k)) is type(v) and main.context.get(k)==v for k,v in r.context.items()) and main.context.get('kind')==item.kind]
        if len(matches)!=1:
            return unavailable('REFERENCE_CONTEXT_MISMATCH')
        ref=matches[0]; weight=profile.mainstat_weights.get(name,Decimal(0))
        exact=50*Fraction(weight)*Fraction(current)/Fraction(ref.value)
        terms.append((exact,dict(contribution_id='main:'+name,weight=weight,factor=Decimal(50),unit=entry.unit,current_value=current,reference_value=ref.value)))
    multiplier=10*Fraction(area) if item.kind=='drive' else Fraction(100)
    for name in sorted(distinct):
        weight=profile.substat_weights.get(name,Decimal(0))
        exact=multiplier*Fraction(weight)*Fraction(quality)/denominator
        terms.append((exact,dict(contribution_id='sub:'+name,weight=weight,factor=quality,unit=entries[name].unit)))
    total=sum((value for value,_ in terms),Fraction())
    # Exact HALF_UP to hundredths; no Decimal context can move a half tie.
    cents=(2*total.numerator*100+total.denominator)//(2*total.denominator)
    rounded=Decimal(f'{cents//100}.{cents%100:02d}')
    contributions=[ScoreContribution(value=_display(value),exact_fraction=_fraction(value),**metadata) for value,metadata in terms]
    with localcontext() as context:
        context.prec=4096
        adjustment=rounded-sum((entry.value for entry in contributions),Decimal())
    return ScoreResult(status='scored',value=rounded,contributions=contributions,score_version=spec.version,weight_version=profile.version,
        rounding_adjustment=adjustment,rounding_adjustment_fraction=_fraction(Fraction(rounded)-total),collapsed_observation_ids=sorted(collapsed))