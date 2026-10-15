"""Personal preference scoring: explicit configuration, never damage/ranking."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction
from typing import Literal
from pydantic import Field, model_validator
from .assessment_contracts import Contract, Identifier, FiniteDecimal, WeightProfile
from .assessment_nte_math import ScoringSpec, ScoreInput, StatInput, score_item, number
import hashlib

Game = Literal['nte','wuthering_waves']
# Units define canonical semantics; there are no default character weights.
WUWA_STATS = {'attack_flat':'flat','attack_ratio':'ratio','health_flat':'flat','health_ratio':'ratio',
    'defense_flat':'flat','defense_ratio':'ratio','crit_rate':'ratio','crit_damage':'ratio',
    'energy_regen':'ratio','basic_damage':'ratio','heavy_damage':'ratio','skill_damage':'ratio',
    'liberation_damage':'ratio','aero_damage':'ratio','glacio_damage':'ratio','fusion_damage':'ratio',
    'electro_damage':'ratio','spectro_damage':'ratio','havoc_damage':'ratio','healing_bonus':'ratio'}


class AssessmentStat(StatInput):
    role: Literal['main','sub'] | None = None


class EquippedInput(Contract):
    id: Identifier
    source_id: str | None = None
    source_group: str | None = None
    kind: Literal['drive','cartridge','echo'] | None = None
    stats: list[AssessmentStat] = Field(default_factory=list,max_length=100)
    stats_complete: bool | None = None
    nte: ScoreInput | None = None


class Configuration(Contract):
    game: Game
    character_id: Identifier
    name: str = Field(min_length=1,max_length=80)
    source: Literal['user_configured','equipped_snapshot']
    observed_at: str | None = None
    items: list[EquippedInput] = Field(default_factory=list,max_length=32)

    @model_validator(mode='after')
    def game_inputs(self):
        if self.game=='wuthering_waves' and any(i.nte is not None or i.kind in ('drive','cartridge') for i in self.items): raise ValueError('game input mismatch')
        if self.game=='nte' and any(i.kind=='echo' or (i.nte and i.kind and i.nte.kind!=i.kind) for i in self.items): raise ValueError('game input mismatch')
        return self


class AssessmentModel(Contract):
    game: Game
    character_id: Identifier
    version: Identifier
    source: Literal['user_configured']
    wuwa_weights: dict[str,FiniteDecimal] = Field(default_factory=dict,max_length=100)
    nte_profile: WeightProfile | None = None
    nte_spec: ScoringSpec | None = None

    @model_validator(mode='after')
    def valid(self):
        if any(k not in WUWA_STATS or not 0<=v<=100 for k,v in self.wuwa_weights.items()):
            raise ValueError('explicit canonical stat and weight 0..100 required')
        if self.game=='nte' and self.wuwa_weights: raise ValueError('game formula mismatch')
        if self.game=='wuthering_waves' and (self.nte_profile or self.nte_spec): raise ValueError('game formula mismatch')
        if self.nte_profile and self.nte_profile.character_id!=self.character_id: raise ValueError('character mismatch')
        if self.nte_profile and self.nte_profile.source!='user_configured': raise ValueError('explicit user configured provenance required')
        return self


def _rounded(value):
    # All preference values are nonnegative; exact HALF_UP mirrors NTE math.
    cents=(2*value.numerator*100+value.denominator)//(2*value.denominator)
    return f'{cents//100}.{cents%100:02d}'


def _text(value):
    with localcontext() as ctx:
        ctx.prec=50
        return format(Decimal(value.numerator)/Decimal(value.denominator),'f')


def _assess_core(configuration: Configuration, model: AssessmentModel):
    if (configuration.game,configuration.character_id)!=(model.game,model.character_id): raise ValueError('character/model mismatch')
    base=dict(model_version=model.version,source=model.source,
        model_fingerprint=hashlib.sha256(model.model_dump_json().encode()).hexdigest(),
        weight_version=model.nte_profile.version if model.nte_profile else model.version,
        formula='nte-custom-weighting-v1' if model.game=='nte' else 'wuwa-custom-weighted-values-v1',
        formula_text='D=最高四项正副词条权重之和；驱动副项=10×面积×品质因子×权重/D；卡带副项=100×品质因子×权重/D；卡带主项=50×权重×当前/参考' if model.game=='nte' else 'Σ(已知词条规范值×用户权重)；百分数除以100，平值不换算；每件加总。',
        status='unscorable',value=None,reason=None,contributions=[])
    def unavailable(reason,status='unscorable'): return {**base,'reason':reason,'status':status}
    if model.game=='nte' and (model.nte_profile is None or model.nte_spec is None): return unavailable('NO_MODEL','unconfigured')
    if model.game=='wuthering_waves' and not model.wuwa_weights: return unavailable('NO_WEIGHTS','unconfigured')
    if not configuration.items: return unavailable('NO_EQUIPMENT')
    if len({item.id for item in configuration.items})!=len(configuration.items): return unavailable('DUPLICATE_ITEM')
    terms=[]; contributions=[]
    for item in configuration.items:
        if model.game=='nte':
            if item.nte is None: return unavailable('MISSING_EXPLICIT_NTE_INPUT')
            result=score_item(item.nte,model.nte_profile,model.nte_spec)
            if result.status!='scored': return unavailable(result.reason,result.status)
            for contribution in result.contributions:
                exact=contribution.exact_fraction
                terms.append(Fraction(int(exact.numerator),int(exact.denominator)))
                contributions.append({'item_id':item.id,**contribution.model_dump(mode='json')})
        else:
            if item.stats_complete is not True: return unavailable('UNKNOWN_STAT_COMPLETENESS')
            seen=set()
            observations={};by_stat={}
            for stat in item.stats:
                name=stat.canonical_id
                if name not in WUWA_STATS: return unavailable('UNKNOWN_STAT')
                seen.add(name)
                expected=WUWA_STATS[name]
                if stat.value is None: return unavailable('UNKNOWN_VALUE')
                if stat.unit not in ('flat','ratio','percent_points') or ('ratio' if stat.unit=='percent_points' else stat.unit)!=expected: return unavailable('UNIT_MISMATCH')
                try:
                    value=number(stat.value)
                except (ValueError,ArithmeticError): return unavailable('INVALID_VALUE')
                canonical=Fraction(value)/(100 if stat.unit=='percent_points' else 1)
                identity=(name,canonical,expected,stat.role)
                if stat.observation_id in observations:
                    if observations[stat.observation_id]!=identity:return unavailable('CONFLICTING_OBSERVATION')
                    continue
                if name in by_stat and (not stat.observation_id or any(not s.observation_id for s in by_stat[name])):return unavailable('AMBIGUOUS_DUPLICATE_STAT')
                if name in by_stat and (stat.role is None or any(s.role is None or stat.role==s.role for s in by_stat[name])):return unavailable('AMBIGUOUS_DUPLICATE_STAT')
                if stat.observation_id:observations[stat.observation_id]=identity
                by_stat.setdefault(name,[]).append(stat)
                weight=model.wuwa_weights.get(name,Decimal(0)); term=canonical*Fraction(weight)
                terms.append(term)
                contributions.append(dict(item_id=item.id,contribution_id=name,value=_text(term),weight=str(weight),unit=expected,
                    current_value=_text(canonical),exact_fraction=dict(numerator=str(term.numerator),denominator=str(term.denominator))))
            # Confirmed complete source lists prove absent canonical stats are zero.
            if not seen: return unavailable('NO_STAT_VALUES')
    total=sum(terms,Fraction())
    return {**base,'status':'scored','value':_rounded(total),'contributions':contributions,
            'exact_fraction':dict(numerator=str(total.numerator),denominator=str(total.denominator)),
            'rounding_adjustment':_text(Fraction(_rounded(total))-total)}


def assess(configuration: Configuration,model: AssessmentModel):
    result=_assess_core(configuration,model)
    items=[];known=Fraction()
    for item in configuration.items:
        single=Configuration.model_validate({**configuration.model_dump(mode='python'),'items':[item]})
        score=_assess_core(single,model)
        items.append({'item_id':item.id,**score})
        if score['status']=='scored':known+=Fraction(int(score['exact_fraction']['numerator']),int(score['exact_fraction']['denominator']))
    has_known=any(i['status']=='scored' for i in items)
    partial=(True if has_known else None) if result['status']=='unscorable' else False if result['status']=='scored' else None
    return {**result,'item_results':items,'partial':partial,'partial_known_total':_rounded(known) if partial else None}


def compare(a,b,model):
    left,right=assess(a,model),assess(b,model)
    result=dict(a=left,b=right,model_version=model.version,percent_delta=None,delta=None,reason=None)
    if left['status']!='scored' or right['status']!='scored': result['reason']='BOTH_CONFIGURATIONS_REQUIRE_SCORE'; return result
    def exact(score):
        value=score['exact_fraction'];return Fraction(int(value['numerator']),int(value['denominator']))
    baseline,other=exact(left),exact(right)
    with localcontext() as ctx:
        ctx.prec=128
        difference=other-baseline
        result['delta']=format((Decimal(difference.numerator)/Decimal(difference.denominator)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'f')
        result['exact_delta']=dict(numerator=str(difference.numerator),denominator=str(difference.denominator))
        if baseline==0: result['reason']='ZERO_BASELINE'
        else:
            percent=difference*100/baseline
            result['percent_delta']=format((Decimal(percent.numerator)/Decimal(percent.denominator)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'f')
    return result
