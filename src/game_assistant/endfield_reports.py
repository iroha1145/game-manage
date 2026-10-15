"""Pure Endfield report projections shared by the website and QQ.

Inputs are normalized, credential-free payloads, including older snapshots. A
missing observation is never interpreted as zero, completion, or a prediction.
No game-specific mood/trust conversion is assumed here.
"""
from copy import deepcopy
from datetime import datetime, timezone
from math import isfinite


def _object(value):
    return value if isinstance(value, dict) else {}


def _items(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _number(value):
    if isinstance(value, bool) or value is None or value == '':
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return (int(number) if number.is_integer() else number) if isfinite(number) and number >= 0 else None


def _metric(current, total):
    current, total = _number(current), _number(total)
    known = current is not None and total is not None and total > 0
    return {'current': current, 'total': total,
            'remaining': max(0, total - current) if known else None,
            'percent': round(current / total * 100, 1) if known else None}


def _available(payload, field):
    explicit = _object(payload.get('availability')).get(field)
    # Old parsers produced [] for both absent and empty source arrays. Empty old
    # snapshots cannot establish that a player owns nothing or has no rooms.
    if isinstance(explicit, bool):
        return explicit
    return True if _items(payload.get(field)) else None


def _operator_index(operators):
    result = {}
    for operator in operators:
        for key in ('id', 'char_id'):
            if operator.get(key) is not None:
                result[str(operator[key])] = operator
    return result


def _resident(raw, operators):
    raw = _object(raw)
    identity = raw.get('charId', raw.get('char_id', raw.get('id')))
    identity = str(identity) if identity is not None else ''
    operator = operators.get(identity, {})
    char_data = _object(raw.get('charData'))
    return {'id': identity, 'name': raw.get('name') or char_data.get('name') or operator.get('name'),
            'avatar_url': operator.get('avatar_url') or char_data.get('avatarSqUrl'),
            'mood_raw': _number(raw.get('physicalStrength')),
            'trust_raw': _number(raw.get('favorability'))}


COLLECTIONS = (
    ('chests', '宝箱', 'chest_count'),
    ('puzzles', '醚质', 'puzzle_count'),
    ('blackboxes', '协议采录桩', 'blackbox_count'),
    ('equipment_chests', '装备制造模板', 'equipment_chest_count'),
    ('pieces', '维修灵感点', 'piece_count'),
)

# Exact region IDs documented by the reviewed dashboard capture (2026-10-14).
# Current upstream labels always win; unfamiliar IDs remain visible as IDs.
AREA_NAMES = {
    'map01_lv001': '枢纽区', 'map01_lv002': '谷地通道', 'map01_lv003': '阿伯莉采石场',
    'map01_lv005': '源石研究园', 'map01_lv006': '矿脉源区', 'map01_lv007': '供能高地',
    'map02_lv001': '景玉谷', 'map02_lv002': '武陵城', 'map02_lv003': '清波寨',
}


def _area_name(name, identity):
    if isinstance(name, str) and name:
        return name
    if isinstance(identity, (str, int)) and not isinstance(identity, bool):
        identity = str(identity)
        return AREA_NAMES.get(identity) or identity
    return None


def _honor(payload):
    achievements = _object(payload.get('achievements'))
    medals = _items(achievements.get('medals'))
    explicit = _object(payload.get('availability')).get('honor')
    available = explicit if isinstance(explicit, bool) else True if medals else None
    items = []
    for medal in medals:
        data = _object(medal.get('achievementData'))
        level = _number(medal.get('level'))
        plated = medal.get('isPlated') if isinstance(medal.get('isPlated'), bool) else None
        icon = data.get('initIcon')
        if level is not None and level >= 2 and data.get('reforge2Icon'):
            icon = data['reforge2Icon']
        if level is not None and level >= 3 and data.get('reforge3Icon'):
            icon = data['reforge3Icon']
        if plated is True and data.get('platedIcon'):
            icon = data['platedIcon']
        timestamp = _number(medal.get('obtainTs'))
        obtained_at = None
        if timestamp:
            try:
                obtained_at = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            except (OverflowError, ValueError, OSError):
                pass
        items.append({'id': data.get('id'), 'name': data.get('name'), 'level': level,
                      'is_plated': plated, 'obtained_at': obtained_at,
                      'icon_url': icon if isinstance(icon, str) else None})
    return {'available': available, 'items': items,
            'summary': {'declared_count': _number(achievements.get('count')),
                        'listed_count': len(items) if available is True else None}}


def _regions(payload, operators):
    result = []
    for region in _items(payload.get('regions')):
        settlements = []
        for settlement in _items(region.get('settlements')):
            ids = settlement.get('officer_char_ids')
            officers = [_resident({'charId': identity}, operators) for identity in ids
                        if isinstance(identity, (str, int)) and not isinstance(identity, bool)] if isinstance(ids, list) else []
            settlements.append({**deepcopy(settlement),
                                'coupon': _metric(settlement.get('money'), settlement.get('money_max')),
                                'officers': officers, 'officers_available': isinstance(ids, list)})
        areas, by_id, named_ids = [], {}, set()
        for level in _items(region.get('levels')):
            area = {'id': level.get('id'), 'name': _area_name(level.get('name'), level.get('id')),
                          'collections': [{'key': key, 'label': label,
                                           **_metric(_object(level.get(key)).get('count'),
                                                     _object(level.get(key)).get('total'))}
                                          for key, label, _ in COLLECTIONS]}
            areas.append(area)
            if level.get('id') is not None:
                by_id[str(level['id'])] = area
                if isinstance(level.get('name'), str) and level['name']:
                    named_ids.add(str(level['id']))
        for collection in _items(region.get('collections')):
            existing = by_id.get(str(collection.get('level_id')))
            if existing:
                if str(collection.get('level_id')) not in named_ids and isinstance(collection.get('name'), str) and collection['name']:
                    existing['name'] = collection['name']
                    named_ids.add(str(collection['level_id']))
                for metric, (_, _, raw_key) in zip(existing['collections'], COLLECTIONS):
                    if metric['current'] is None:
                        metric.update(_metric(collection.get(raw_key), metric['total']))
                continue
            areas.append({'id': collection.get('level_id'), 'name': _area_name(collection.get('name'), collection.get('level_id')),
                          'collections': [{'key': key, 'label': label,
                                           **_metric(collection.get(raw_key), None)}
                                          for key, label, raw_key in COLLECTIONS]})
        money = _object(region.get('money'))
        result.append({**deepcopy(region), 'money': _metric(money.get('count'), money.get('total')),
                       'settlements': settlements, 'areas': areas})
    available = _available(payload, 'regions')
    settlements_available = all(
        item.get('settlements_available') is True or
        ('settlements_available' not in item and bool(item['settlements'])) for item in result)
    return {'items': result, 'available': available,
            'summary': {'region_count': len(result) if available is True else None,
                        'settlement_count': sum(len(item['settlements']) for item in result)
                        if available is True and settlements_available else None}}


def build_endfield_report(payload, *, fetched_at=None):
    """Project a normalized card without mutating it or trusting an old report."""
    payload = _object(payload)
    base, stamina = _object(payload.get('base')), _object(payload.get('stamina'))
    metric = _metric(stamina.get('current'), stamina.get('maximum'))
    progress = []
    aliases = {'每日活跃': 'daily', '每周任务': 'weekly', '通行证': 'battle_pass'}
    for item in _items(payload.get('progress')):
        pair = _metric(item.get('cur'), item.get('total'))
        remaining = pair['remaining']
        progress.append({**deepcopy(item), 'id': item.get('id') or aliases.get(item.get('name')),
                         'cur': pair['current'], 'total': pair['total'],
                         'remaining': remaining, 'percent': pair['percent'],
                         'state': 'unknown' if remaining is None else 'complete' if remaining == 0 else 'incomplete'})
    operators = deepcopy(_items(payload.get('operators')))
    operators.sort(key=lambda item: (-(_number(item.get('level')) if _number(item.get('level')) is not None else -1),
                                    -(_number(item.get('rarity')) or 0), str(item.get('name') or ''), str(item.get('id') or '')))
    index = _operator_index(operators)
    levels = [_number(item.get('level')) for item in operators]
    levels = [level for level in levels if level is not None]
    rarities, phases = {}, {}
    for operator in operators:
        for field, counts in (('rarity', rarities), ('evolve_phase', phases)):
            value = _number(operator.get(field))
            if value is not None:
                counts[str(value)] = counts.get(str(value), 0) + 1
    rooms = [{**deepcopy(room),
              'operators_available': room.get('operators_available') if isinstance(room.get('operators_available'), bool)
                                     else True if _items(room.get('operators')) else None,
              'operators': [_resident(item, index) for item in _items(room.get('operators'))]}
             for room in _items(payload.get('ship'))]
    operators_available, ship_available = _available(payload, 'operators'), _available(payload, 'ship')
    staff_available = ship_available is True and all(room['operators_available'] is True for room in rooms)
    return {'schema_version': 1, 'observed_at': payload.get('observed_at'), 'fetched_at': fetched_at,
            'overview': {'base': deepcopy(base),
                         'stamina': {**deepcopy(stamina), 'current': metric['current'], 'maximum': metric['total'],
                                     'remaining': metric['remaining'], 'percent': metric['percent']},
                         'progress': progress,
                         'todos': [deepcopy(item) for item in progress
                                   if item['id'] in ('daily', 'weekly') and item['state'] == 'incomplete']},
            'training': {'items': operators, 'available': operators_available,
                         'summary': {'listed_count': len(operators) if operators_available is True else None,
                                     'declared_count': _number(base.get('char_count')), 'known_levels': len(levels),
                                     'average_level': round(sum(levels) / len(levels), 1) if levels else None,
                                     'max_level': max(levels) if levels else None,
                                     'rarity_counts': rarities, 'phase_counts': phases}},
            'regions': _regions(payload, index),
            'honor': _honor(payload),
            'ship': {'rooms': rooms, 'available': ship_available,
                     'summary': {'room_count': len(rooms) if ship_available is True else None,
                                 'staffed_rooms': sum(bool(room['operators']) for room in rooms) if staff_available else None,
                                 'operator_slots': sum(len(room['operators']) for room in rooms) if staff_available else None}}}


def build_gacha_report(summary):
    """Summarize recorded pulls only; exact intervals exclude gaps/free ambiguity.

    average_exact_pulls describes the available, capped six-star history. It is
    deliberately not a lifetime luck score, pity guarantee, or forecast.
    """
    if hasattr(summary, 'model_dump'):
        summary = summary.model_dump(mode='json', exclude={'report'})
    summary = _object(summary)
    pools = deepcopy(_items(summary.get('pools')))
    history = [{**deepcopy(item), 'pool_key': pool.get('key'), 'pool_label': pool.get('label')}
               for pool in pools for item in _items(pool.get('history'))]
    history.sort(key=lambda item: (-(_number(item.get('obtained_at')) or 0), str(item.get('pool_key') or '')))
    exact = [_number(item.get('pulls')) for item in history if item.get('status') == 'exact']
    exact = [value for value in exact if value is not None]
    def total(field):
        values = [_number(pool.get(field)) for pool in pools]
        return sum(values) if values and all(value is not None for value in values) else 0 if summary.get('total') == 0 else None
    return {'schema_version': 1, 'role_id': summary.get('role_id'), 'total': _number(summary.get('total')),
            'six_star': total('six_star'), 'five_star': total('five_star'), 'free': total('free'),
            'complete': summary.get('complete') if isinstance(summary.get('complete'), bool) else None,
            'gaps': total('gaps'), 'pending': True if summary.get('complete') is False or any(pool.get('pending') is True for pool in pools)
            else None if 'complete' in summary and summary['complete'] is None
            else False if (pools and all(pool.get('pending') is False for pool in pools)) or summary.get('total') == 0 else None,
            'known_exact_intervals': len(exact),
            'average_exact_pulls': round(sum(exact) / len(exact), 1) if exact else None,
            'pools': pools, 'history': history}
