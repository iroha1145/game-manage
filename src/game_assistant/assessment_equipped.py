"""Adapter-friendly equipped inputs. No inferred identity, area or item quality."""
import re
from .assessment import Configuration
from .wuwa_role_detail import role_detail_data

WUWA_NAMES={'攻击':'attack','攻击力':'attack','生命':'health','生命值':'health','防御':'defense','防御力':'defense','暴击':'crit_rate','暴击率':'crit_rate','暴击伤害':'crit_damage','共鸣效率':'energy_regen','普攻伤害加成':'basic_damage','重击伤害加成':'heavy_damage','共鸣技能伤害加成':'skill_damage','共鸣解放伤害加成':'liberation_damage','气动伤害加成':'aero_damage','冷凝伤害加成':'glacio_damage','热熔伤害加成':'fusion_damage','导电伤害加成':'electro_damage','衍射伤害加成':'spectro_damage','湮灭伤害加成':'havoc_damage','治疗效果加成':'healing_bonus'}


def equipped_configuration(game,character,payload,observed_at=None):
    items=[]
    if game=='nte':
        role=next((r for r in payload.get('entries',[]) if str(r.get('id'))==character),None) if isinstance(payload,dict) else None
        if role:
            suit=role.get('suit') or {}
            for group in ('core','pie'):
                for index,item in enumerate(suit.get(group,[])):
                    source_id=str(item['id']) if item.get('id') is not None else None
                    items.append(dict(id=f'{group}:{index}:'+str(source_id or 'unknown'),source_id=source_id,source_group=group,
                        stats=[dict(canonical_id=p.get('id'),value=p.get('value'),unit=None) for p in item.get('properties',[])]))
    elif (payload:=role_detail_data(payload,character)) is not None:
        for index,item in enumerate((payload.get('phantom_data') or {}).get('equip_phantom_list',[])):
            stats=[]
            for group in ('main_props','sub_props'):
                props=item.get(group,[])
                props=[props] if isinstance(props,dict) else props if isinstance(props,list) else []
                for stat_index,p in enumerate(props):
                    name=p.get('attribute_name') or p.get('name')
                    raw=p.get('attribute_value') if 'attribute_value' in p else p.get('value')
                    raw=str(raw).strip() if raw is not None else None
                    ratio=raw is not None and raw.endswith('%')
                    canonical=WUWA_NAMES.get(name)
                    if canonical in ('attack','health','defense'): canonical+='_'+('ratio' if ratio else 'flat')
                    unit='percent_points' if ratio else 'flat' if canonical in ('attack_flat','health_flat','defense_flat') else None
                    value=raw[:-1] if ratio else raw
                    if value is not None and not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?',value): value=None
                    stats.append(dict(canonical_id=canonical,value=value,unit=unit,role='main' if group=='main_props' else 'sub',observation_id=f'{group}:{stat_index}'))
            phantom=item.get('phantom_prop') or {}
            # Source resource ID alone does not identify a full-inventory item.
            source_id=str(phantom['id']) if phantom.get('id') is not None else None
            items.append(dict(id=f'echo:{index}:'+str(source_id or 'unknown'),source_id=source_id,kind='echo',stats=stats))
    return Configuration.model_validate(dict(game=game,character_id=character,name='当前装备',source='equipped_snapshot',observed_at=observed_at,items=items))
