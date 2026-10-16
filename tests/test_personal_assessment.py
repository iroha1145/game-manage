import pytest
from game_assistant.assessment import AssessmentModel, Configuration, assess, compare


def wuwa_model(weights=None, version='v1'):
    return AssessmentModel.model_validate(dict(game='wuthering_waves',character_id='c1',version=version,
        source='user_configured',wuwa_weights=weights if weights is not None else {'attack_flat':'0.1','crit_rate':'100'}))


def config(stats=None, character='c1'):
    return Configuration.model_validate(dict(game='wuthering_waves',character_id=character,name='A',source='user_configured',
        items=[dict(id='echo1',stats_complete=True,stats=stats if stats is not None else [dict(canonical_id='attack_flat',value='100',unit='flat'),dict(canonical_id='crit_rate',value='10',unit='percent_points')])]))


def test_wuwa_independent_units_contributions_and_three_states():
    result = assess(config(),wuwa_model())
    assert result['value']=='20.00' and [p['value'] for p in result['contributions']]==['10','10']
    assert assess(config(),wuwa_model({}))['status']=='unconfigured'
    assert assess(config([dict(canonical_id='attack_flat',value='100',unit='ratio')]),wuwa_model())['status']=='unscorable'
    assert assess(config([dict(canonical_id='attack_flat',value='0',unit='flat'),dict(canonical_id='crit_rate',value='0',unit='ratio')]),wuwa_model())['value']=='0.00'
    incomplete=config([dict(canonical_id='attack_flat',value='100',unit='flat')]).model_dump(mode='json')
    incomplete['items'][0]['stats_complete']=None
    assert assess(Configuration.model_validate(incomplete),wuwa_model())['status']=='unscorable'
    assert assess(config([dict(canonical_id='attack_flat',value='100',unit='flat')]),wuwa_model())['value']=='10.00'


def test_same_character_compare_rescores_model_and_zero_baseline():
    a=config(); b=config([dict(canonical_id='attack_flat',value='200',unit='flat'),dict(canonical_id='crit_rate',value='20',unit='percent_points')])
    result=compare(a,b,wuwa_model(version='v2'))
    assert result['percent_delta']=='100.00' and result['model_version']=='v2'
    with pytest.raises(ValueError): compare(a,config(character='other'),wuwa_model())
    zero=config([dict(canonical_id='attack_flat',value='0',unit='flat'),dict(canonical_id='crit_rate',value='0',unit='ratio')])
    assert compare(zero,b,wuwa_model())['percent_delta'] is None


def test_nte_configured_single_item_keeps_exact_math_and_unknown_quality():
    model=AssessmentModel.model_validate(dict(game='nte',character_id='c1',version='personal-v1',source='user_configured',
        nte_profile=dict(character_id='c1',version='weights-v1',source='user_configured',substat_weights={'attack':'1','crit':'3'},mainstat_weights={}),
        nte_spec=dict(version='spec-v1',quality_factors={'custom':'0.8'},eligible_substats=['attack','crit'],
            catalog=[dict(canonical_id=x,label=x,kinds=['drive'],main=False,sub=True,unit='flat') for x in ('attack','crit')],mainstat_reference_values=[])))
    c=Configuration.model_validate(dict(game='nte',character_id='c1',name='custom',source='user_configured',items=[dict(id='i1',nte=dict(kind='drive',quality='custom',area='4',substats_complete=True,substats=[dict(canonical_id='attack',observation_id='a',value='999',unit='flat')]))]))
    # 10*4*0.8*1/(1+3)=8; observed value 999 doesn't affect presence weighting.
    result=assess(c,model)
    assert result['value']=='8.00' and result['contributions'][0]['exact_fraction']=={'numerator':'8','denominator':'1'}
    broken=c.model_dump(mode='json');broken['items'][0]['nte']['quality']=None
    assert assess(Configuration.model_validate(broken),model)['reason']=='UNKNOWN_QUALITY'


def test_changed_selected_model_recalculates_both_configurations():
    a=config();b=config([dict(canonical_id='attack_flat',value='200',unit='flat'),dict(canonical_id='crit_rate',value='10',unit='percent_points')])
    first=compare(a,b,wuwa_model())
    second=compare(a,b,wuwa_model({'attack_flat':'1','crit_rate':'0'},version='v2'))
    assert first['percent_delta']=='50.00' and second['percent_delta']=='100.00'
    assert first['a']['model_fingerprint']!=second['a']['model_fingerprint']
    assert second['a']['model_fingerprint']==second['b']['model_fingerprint']


def test_explicit_zero_weights_and_invalid_fixed_point_are_distinct():
    assert assess(config(),wuwa_model({'attack_flat':'0','crit_rate':'0'}))['value']=='0.00'
    assert assess(config([dict(canonical_id='attack_flat',value='1e999999999',unit='flat'),dict(canonical_id='crit_rate',value='0',unit='ratio')]),wuwa_model())['status']=='unscorable'


def test_main_sub_observations_complete_absence_and_duplicate_guard():
    c=config([dict(canonical_id='attack_flat',value='100',unit='flat',role='main',observation_id='m'),
              dict(canonical_id='attack_flat',value='20',unit='flat',role='sub',observation_id='s')])
    assert assess(c,wuwa_model())['value']=='12.00'
    rows=c.model_dump(mode='json'); rows['items'][0]['stats'].append(rows['items'][0]['stats'][1].copy())
    assert assess(Configuration.model_validate(rows),wuwa_model())['value']=='12.00'
    rows['items'][0]['stats'][2]['value']='30'
    assert assess(Configuration.model_validate(rows),wuwa_model())['reason']=='CONFLICTING_OBSERVATION'


def test_compare_uses_exact_values_when_display_scores_round_to_zero():
    a=config([dict(canonical_id='attack_flat',value='0.004',unit='flat')])
    b=config([dict(canonical_id='attack_flat',value='0.006',unit='flat')])
    result=compare(a,b,wuwa_model({'attack_flat':'1'}))
    assert result['a']['value']=='0.00' and result['b']['value']=='0.01'
    assert result['percent_delta']=='50.00' and result['reason'] is None
    assert result['exact_delta']=={'numerator':'1','denominator':'500'}


def test_item_subtotals_survive_unknown_set_with_partial_flag():
    raw=config().model_dump(mode='json');raw['items'].append(dict(id='unknown',stats_complete=None,stats=[]))
    result=assess(Configuration.model_validate(raw),wuwa_model())
    assert result['value'] is None and result['status']=='unscorable'
    assert result['partial'] is True and result['partial_known_total']=='20.00'
    assert result['item_results'][0]['value']=='20.00' and result['item_results'][1]['status']=='unscorable'
    unknown=config().model_dump(mode='json');unknown['items'][0]['stats_complete']=None
    empty=assess(Configuration.model_validate(unknown),wuwa_model())
    assert empty['partial'] is None and empty['partial_known_total'] is None
