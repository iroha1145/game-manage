"""Versioned display-only QQ cards; PNG and text consume identical safe data."""
import re
import math
import unicodedata
from datetime import date

from .commands import mask_links

CARD_KINDS = frozenset(('overview', 'summary', 'list', 'detail', 'help', 'status'))
CARD_GAMES = frozenset(('all', 'wuthering_waves', 'nte', 'endfield'))
MAX_TEXT = 1800
MAX_LONG_TEXT = 24000
IMAGE_REF = re.compile(r'qqasset_[0-9a-f]{64}')
LAYOUTS = frozenset(('stats','grid','rows','detail','equipment','skills'))
V3_LAYOUTS = LAYOUTS | {'help','timeline','gacha'}


def _date(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise ValueError('qq_card_invalid_timeline')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('qq_card_invalid_timeline') from None


def _timeline(value, *, axis=False):
    keys=('start','end','today','timezone') if axis else ('start','end','precision','continues_before','continues_after')
    _object(value,keys)
    if set(value)!=set(keys):raise ValueError('qq_card_invalid_timeline')
    start,end=_date(value['start']),_date(value['end'])
    if start>=end:raise ValueError('qq_card_invalid_timeline')
    if axis:
        today=_date(value['today'])
        if not start<=today<end or (end-start).days>62 or value['timezone']!='Asia/Shanghai':
            raise ValueError('qq_card_invalid_timeline')
    elif value['precision'] not in ('minute','day') or any(type(value[key]) is not bool for key in ('continues_before','continues_after')):
        raise ValueError('qq_card_invalid_timeline')
    return dict(value)


def _gacha(value):
    keys=('draws','guarantee','lucky_type','color','lucky_text')
    _object(value,keys)
    if set(value)!=set(keys):raise ValueError('qq_card_invalid_gacha')
    for key in ('draws','guarantee','lucky_type'):
        number=value[key]
        if number is not None and (type(number) is not int or not 0<=number<=10**9):
            raise ValueError('qq_card_invalid_gacha')
    expected={1:'green',2:'green',0:'yellow',3:'yellow',4:'red'}.get(value['lucky_type'],'unknown')
    if value['color']!=expected or (value['lucky_type']==0 and value['lucky_text']):
        raise ValueError('qq_card_invalid_gacha')
    return dict(value,lucky_text=_text(value['lucky_text'],96))


def _image(source,target):
    if 'image' not in source:
        return
    value = source['image']
    if not isinstance(value,str) or not IMAGE_REF.fullmatch(value):
        raise ValueError('qq_card_invalid_image_reference')
    target['image'] = value


def _object(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError('qq_card_invalid_object')


def _text(value, limit, *, required=False):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError('qq_card_invalid_text')
    # Display text never becomes a URL, mention or bidirectional control payload.
    value = re.sub(r'<@[^>]*>', '', value)
    value = re.sub(r'(?<!\d)\d{7,}(?!\d)', '***', value)
    value = mask_links(value)
    value = ' '.join(''.join(c if c.isspace() else '' if unicodedata.category(c).startswith('C') else c for c in value).split())
    if len(value) > limit or (required and not value):
        raise ValueError('qq_card_invalid_text')
    return value


def _items(value, maximum):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError('qq_card_invalid_collection')
    return value


def _fields(value, maximum, version=1):
    fields = []
    for item in _items(value, maximum):
        _object(item, ('label', 'value','metric') if version>=2 else ('label','value'))
        field = dict(label=_text(item.get('label'), 40, required=True),
                     value=_text(item.get('value'), 180, required=True))
        if 'metric' in item:
            metric = item['metric']
            _object(metric,('current','maximum'))
            if set(metric)!={'current','maximum'}:
                raise ValueError('qq_card_invalid_metric')
            for number in metric.values():
                if number is not None and (type(number) not in (int,float) or not 0<=number<=10**12 or not math.isfinite(number)):
                    raise ValueError('qq_card_invalid_metric')
            field['metric'] = dict(metric)
        fields.append(field)
    return fields


def _serialize(card):
    lines = [card['title']]
    if card['subtitle']:
        lines.append(card['subtitle'])
    if 'timeline' in card:
        lines.append(f"日期轴：{card['timeline']['start']} 至 {card['timeline']['end']}（结束日不含） · 北京时间")
    for section in card['sections']:
        if section['title']:
            lines.append('\n' + section['title'])
        lines.extend(f"{field['label']}：{field['value']}" for field in section['fields'])
        for row in section['rows']:
            lines.append(row['title'] + (' · ' + row['subtitle'] if row['subtitle'] else ''))
            lines.extend(f"{field['label']}：{field['value']}" for field in row['fields'])
            if 'gacha' in row:
                item=row['gacha']
                lines.append('该次出货抽数：'+('未知' if item['draws'] is None else str(item['draws'])))
                if item['lucky_text']:lines.append('来源评价：'+item['lucky_text'])
            for equipment in row.get('equipment',[]):
                lines.append('装备：'+equipment['title']+(' · '+equipment['subtitle'] if equipment['subtitle'] else ''))
    lines.extend(card['notices'])
    if card['footer']:
        lines.append(card['footer'])
    if 'page' in card:
        lines.append(f"第 {card['page']['current']} / {card['page']['total']} 页")
    return '\n'.join(lines)


def validate_card_document(card):
    """Return a fresh canonical JSON object or reject, never silently truncate."""
    if not isinstance(card,dict):
        raise ValueError('qq_card_invalid_object')
    if type(card.get('version')) is not int or card['version'] not in (1,2,3):
        raise ValueError('qq_card_invalid_version')
    version = card['version']
    allowed=('version','kind','game','title','subtitle','sections','notices','footer','page')
    if version>=2:allowed+=('image',)
    if version==3:allowed+=('timeline',)
    _object(card,allowed)
    if (not isinstance(card.get('kind'),str) or not isinstance(card.get('game'),str)
            or card['kind'] not in (CARD_KINDS | {'calendar'} if version==3 else CARD_KINDS) or card['game'] not in CARD_GAMES):
        raise ValueError('qq_card_invalid_kind_or_game')
    normalized = dict(version=version, kind=card['kind'], game=card['game'],
        title=_text(card.get('title'),96,required=True), subtitle=_text(card.get('subtitle',''),180),
        sections=[], notices=[_text(n,180,required=True) for n in _items(card.get('notices',[]),6)],
        footer=_text(card.get('footer',''),180))
    if version>=2:
        _image(card,normalized)
    if 'timeline' in card:
        normalized['timeline']=_timeline(card['timeline'],axis=True)
    if card['kind']=='calendar' and 'timeline' not in card:
        raise ValueError('qq_card_invalid_timeline')
    row_count = field_count = 0
    for section in _items(card.get('sections',[]),36 if version>=2 else 8):
        allowed=('title','fields','rows')
        if version>=2:allowed+=('image','layout')
        if version==3:allowed+=('game','category','tone')
        _object(section,allowed)
        target = dict(title=_text(section.get('title',''),96), fields=_fields(section.get('fields',[]),48 if version>=2 else 12,version),rows=[])
        field_count += len(target['fields'])
        if version>=2:
            _image(section,target)
            layout = section.get('layout','rows')
            if not isinstance(layout,str) or layout not in (V3_LAYOUTS if version==3 else LAYOUTS):
                raise ValueError('qq_card_invalid_layout')
            target['layout'] = layout
        if version==3:
            if 'tone' in section:
                if not isinstance(section['tone'],str) or section['tone'] not in ('green','yellow','red','unknown'):
                    raise ValueError('qq_card_invalid_tone')
                target['tone']=section['tone']
            if 'game' in section:
                if not isinstance(section['game'],str) or section['game'] not in CARD_GAMES-{'all'}:
                    raise ValueError('qq_card_invalid_kind_or_game')
                target['game']=section['game']
            if 'category' in section:target['category']=_text(section['category'],40,required=True)
            if target['layout']=='timeline' and 'timeline' not in normalized:
                raise ValueError('qq_card_invalid_timeline')
        for row in _items(section.get('rows',[]),256 if version>=2 else 12):
            allowed=('title','subtitle','fields')
            if version>=2:allowed+=('image',)
            if version==3:allowed+=('timeline','gacha','equipment')
            _object(row,allowed)
            item = dict(title=_text(row.get('title'),96,required=True),
                subtitle=_text(row.get('subtitle',''),180),fields=_fields(row.get('fields',[]),8,version))
            if version>=2:
                _image(row,item)
            if 'timeline' in row:
                if target['layout']!='timeline':raise ValueError('qq_card_invalid_timeline')
                item['timeline']=_timeline(row['timeline'])
            if 'gacha' in row:
                if target['layout']!='gacha':raise ValueError('qq_card_invalid_gacha')
                item['gacha']=_gacha(row['gacha'])
            if 'equipment' in row:
                if target['layout']!='equipment':raise ValueError('qq_card_invalid_equipment')
                item['equipment']=[]
                for equipment in _items(row['equipment'],6):
                    _object(equipment,('title','subtitle','image'))
                    slot=dict(title=_text(equipment.get('title'),96,required=True),subtitle=_text(equipment.get('subtitle',''),96))
                    _image(equipment,slot)
                    item['equipment'].append(slot)
                field_count+=len(item['equipment'])*2
            target['rows'].append(item)
            field_count += len(item['fields'])
            row_count += 1
        normalized['sections'].append(target)
    if row_count > (256 if version>=2 else 16) or (version>=2 and field_count>360):
        raise ValueError('qq_card_too_many_rows')
    if 'page' in card:
        page = card['page']
        _object(page, ('current','total'))
        if any(type(page.get(k)) is not int for k in ('current','total')) or not 1 <= page['current'] <= page['total'] <= 999:
            raise ValueError('qq_card_invalid_page')
        normalized['page'] = dict(current=page['current'],total=page['total'])
    if len(_serialize(normalized)) > (MAX_LONG_TEXT if version>=2 else MAX_TEXT):
        raise ValueError('qq_card_text_limit')
    return normalized


def card_to_text(card):
    card = validate_card_document(card)
    full = _serialize(card)
    if len(full)<=MAX_TEXT:
        return full
    pools=next((section['rows'] for section in card['sections'] if section.get('category')=='ef_gacha_pools'),None)
    if card['game']=='endfield' and card['kind']=='list' and pools is not None:
        return _endfield_gacha_summary(card,pools)
    honor=next((section for section in card['sections'] if section.get('category')=='ef_honor_groups'),None)
    if card['game']=='endfield' and honor is not None:
        lines=[card['title'],'文字摘要 · 分类统计优先；勋章明细见图片或网站']
        for section in card['sections']:
            if section.get('category') in ('ef_honor','ef_honor_groups'):
                lines.append(section['title'])
                lines.extend(f"{item['label']}：{item['value']}" for item in section['fields'])
        lines+=card['notices']+([card['footer']] if card['footer'] else [])
        if len('\n'.join(lines))<=MAX_TEXT:return '\n'.join(lines)
    challenge=[section for section in card['sections'] if section.get('category')=='ef_challenge']
    if card['game']=='endfield' and card['kind']=='list' and challenge:
        # Challenge timestamps describe separate observations. Keep all three
        # statuses before choosing any detailed record for a transport fallback.
        lines=[card['title'],'文字摘要 · 三类状态优先；关卡明细见图片或网站']
        for section in challenge:
            lines.append(section['title'])
            lines.extend(f"{item['label']}：{item['value']}" for item in section['fields'])
        lines+=card['notices']+([card['footer']] if card['footer'] else [])
        if len('\n'.join(lines))<=MAX_TEXT:return '\n'.join(lines)
    # The long image is complete; fallback is explicitly a summary. Preserve
    # every source notice and timestamp, and shorten only whole display lines.
    head=[card['title'],card['subtitle'],'文字摘要 · 完整内容见图片或网站']
    tail=card['notices']+([card['footer']] if card['footer'] else [])
    if 'page' in card:tail.append(f"第 {card['page']['current']} / {card['page']['total']} 页")
    row_count=sum(len(section['rows']) for section in card['sections'])
    tail.insert(0,f'图片包含 {row_count} 个缓存条目；文字已省略部分内容。')
    remaining=MAX_TEXT-len('\n'.join(head+tail))-1
    body=[]
    for section in card['sections']:
        lines=[section['title']]+[f"{f['label']}：{f['value']}" for f in section['fields']]
        for row in section['rows']:
            lines.append(row['title']+' · '+' / '.join(f"{f['label']} {f['value']}" for f in row['fields']))
        for line in lines:
            if len(line)+1>remaining:
                return '\n'.join(head+body+tail)
            body.append(line);remaining-=len(line)+1
    return '\n'.join(head+body+tail)


def _endfield_gacha_summary(card,pools):
    """Prefer every pool's statistics to one pool's historical rows."""
    head=[card['title'],'文字摘要 · 各池统计优先；逐条明细见图片或网站']
    overview=next((section['fields'] for section in card['sections'] if section.get('category')=='ef_gacha'),[])
    values={field['label']:field['value'] for field in overview}
    head.append('已记录 '+values.get('已记录抽数','未知')+' 抽 · 6★ '+values.get('6 星','未知')+
                ' · 5★ '+values.get('5 星','未知')+' · 报告区间均抽 '+values.get('报告准确区间均抽','未知')+
                '（样本 '+values.get('准确区间样本数','未知')+'）')
    tail=card['notices']+([card['footer']] if card['footer'] else [])
    body=[]
    for row in pools:
        values={field['label']:field['value'] for field in row['fields']}
        body.append(row['title']+'：记录 '+values.get('已记录抽数','未知')+' · '+values.get('稀有度','未知')+
                    ' · 免费 '+values.get('免费抽','未知')+' · 距6★ '+values.get('距上次 6 星','未知')+
                    ' · '+values.get('扫描与缺口','未知')+'\n6★ '+values.get('6 星覆盖','未知')+
                    ' · 扫描 '+values.get('本池成功扫描','未知'))
    if len('\n'.join(head+body+tail))<=MAX_TEXT:
        return '\n'.join(head+body+tail)
    # Extremely many/long pool names still obey the transport limit. Never
    # pretend omitted pools are included, nor discard the source-state tail.
    selected=[]
    for line in body:
        notice=f'文字统计 {len(selected)+1} / {len(pools)} 池；其余卡池见图片或网站。'
        if len('\n'.join(head+selected+[line,notice]+tail))>MAX_TEXT:break
        selected.append(line)
    return '\n'.join(head+selected+[f'文字统计 {len(selected)} / {len(pools)} 池；其余卡池见图片或网站。']+tail)


def image_references(card):
    """Opaque references only, used to invalidate a render when public art arrives."""
    refs=set()
    if 'image' in card:refs.add(card['image'])
    for section in card['sections']:
        if 'image' in section:refs.add(section['image'])
        refs.update(row['image'] for row in section['rows'] if 'image' in row)
        for row in section['rows']:
            refs.update(item['image'] for item in row.get('equipment',[]) if 'image' in item)
    return tuple(sorted(refs))
