"""Explicit projections of six existing cached capabilities; no remote I/O.

Activities retain only named collection/progress fields. Scores, ratings, ranks
and arbitrary evolving source dictionaries never cross the display boundary.
"""
import math
import re

from .commands import safe_text

TITLES = {('wuthering_waves','calabash'):'数据坞', ('wuthering_waves','activities'):'玩法进度',
          ('wuthering_waves','resources'):'资源报表', ('nte','realestate'):'房产',
          ('nte','vehicles'):'载具', ('nte','teams'):'官方配队缓存'}
FORBIDDEN = re.compile(r'score|rank|rating|评分|评级|排名|伤害估算',re.I)


def _text(value, limit=72):
    if value is None or not isinstance(value,(str,int,float,bool)):
        return '未知'
    if isinstance(value,float) and not math.isfinite(value):
        return '未知'
    if type(value) is bool:
        value = '是' if value else '否'
    elif type(value) is int and abs(value)>=1000000:
        value = format(value,',')  # quantities are not numeric user identifiers
    clean = safe_text(str(value)).replace('\n',' ').strip() or '未知'
    return clean if len(clean)<=limit else clean[:limit-1]+'…'


def _obj(value):
    return value if isinstance(value,dict) else {}


def _rows(value):
    return [row for row in value if isinstance(row,dict)] if isinstance(value,list) else []


def _field(label,value):
    return dict(label=_text(label,32),value=_text(value))


def _pair(current,maximum):
    return _text(current)+' / '+_text(maximum)


def _append(out,title,fields,subtitle=''):
    """Keep each row short enough for the common pagination/image budget."""
    for start in range(0,max(1,len(fields)),3):
        row=dict(title=_text(title),fields=fields[start:start+3])
        if start:
            row['subtitle']='续'
        elif subtitle:
            row['subtitle']=_text(subtitle)
        out.append(row)


def _activities(data,out):
    for raw in _obj(data.get('sections')).values():
        source=_obj(raw)
        if not source:
            continue
        fields=[]
        for key,label in (('unlock','已解锁'),('is_unlock','已解锁'),('level','等级'),
                          ('level_name','等级名称'),('exp','经验'),('next_exp','下一级经验'),
                          ('card_total_num','卡牌总数')):
            if key in source:
                fields.append(_field(label,source[key]))
        for key,label in (('badge_num','徽章'),('card_num','卡牌'),('item_num','已收集'),
                          ('animal_num','动物'),('map_num','地图'),('toy_num','玩具'),
                          ('reward_num','已获奖励')):
            if key in source or 'max_'+key in source:
                fields.append(_field(label,_pair(source.get(key),source.get('max_'+key))))
        _append(out,source.get('title') or '未命名玩法',fields or [_field('数据','未知；缓存暂无已支持字段')])


def _resources(data,fields,out):
    current=_obj(data.get('current')); report=_obj(current.get('data'))
    fields.extend([_field('统计口径','期间获取量，非钱包余额'),
                   _field('报告类型',{'week':'周','month':'月','version':'版本'}.get(current.get('kind'),'未知')),
                   _field('周期',current.get('period')),
                   _field('报告状态','旧报告' if current.get('state')=='stale' else '可用' if current.get('state')=='ok' else '未知'),
                   _field('报告更新时间',current.get('fetched_at')),
                   _field('贝币获取',report.get('total_coin')),_field('星声获取',report.get('total_star'))])
    for key,label in (('coin_list','贝币来源'),('star_list','星声来源'),('item_list','资源类别')):
        for entry in _rows(report.get(key)):
            title=label+' · '+_text(entry.get('type'))
            _append(out,title,[_field('数量',entry.get('num'))])
            if key=='item_list':
                for detail in _rows(entry.get('detail')):
                    _append(out,title+' · '+_text(detail.get('type')),[_field('数量',detail.get('num'))])


def _estate(data,fields,out):
    fields.extend([_field('已拥有',data.get('owned_count')),_field('总数',data.get('total'))])
    for entry in _rows(data.get('entries')):
        title=_text(entry.get('name'))
        residents=entry.get('resident_ids'); furniture=entry.get('furniture')
        _append(out,title,[_field('拥有状态',entry.get('owned')),
            _field('缓存住户数',len(residents) if isinstance(residents,list) else None),
            _field('缓存家具条目',len(furniture) if isinstance(furniture,list) else None)])
        for item in _rows(furniture):
            _append(out,_text(item.get('name')),[_field('拥有状态',item.get('owned'))],subtitle='房产：'+title)


def _vehicles(data,fields,out):
    fields.extend([_field('已拥有',data.get('owned_count')),_field('总数',data.get('total')),
                   _field('展示车辆',data.get('show_name'))])
    for entry in _rows(data.get('entries')):
        title=_text(entry.get('name'))
        _append(out,title,[_field('拥有状态',entry.get('owned'))])
        for key,label in (('base','基础属性'),('advanced','进阶属性')):
            selected=[]
            for item in _rows(entry.get(key)):
                if not isinstance(item.get('name'),str) or FORBIDDEN.search(item['name']):
                    continue
                selected.append(_field(item['name'],_pair(item.get('value'),item.get('maximum'))
                    if key=='advanced' else item.get('value')))
            if selected:
                _append(out,title+' · '+label,selected)
        for model in _rows(entry.get('models')):
            _append(out,title+' · 外观',[_field('类型',model.get('type'))])


def extra_section(game,capability,payload):
    """Return fields/rows for pagination, or None for an unrelated capability."""
    title=TITLES.get((game,capability))
    if title is None:
        return None
    data=_obj(payload); fields=[];out=[]
    if capability=='calabash':
        fields=[_field(label,data.get(key)) for key,label in (
            ('level','等级'),('base_catch','基础捕获率'),('catch_quality','捕获品质'),
            ('cur_exp','当前经验'),('max_count','收集数'))]
    elif capability=='activities':
        _activities(data,out)
    elif capability=='resources':
        _resources(data,fields,out)
    elif capability=='realestate':
        _estate(data,fields,out)
    elif capability=='vehicles':
        _vehicles(data,fields,out)
    elif capability=='teams':
        fields=[_field('来源','官方缓存资料；未生成推荐')]
        for entry in _rows(data.get('entries')):
            _append(out,entry.get('name'),[_field('说明',entry.get('description'))],subtitle='官方缓存')
        if not out:
            fields.append(_field('数据','暂无已采集官方配队条目；未知'))
    if not fields and not out:
        fields=[_field('数据','暂无已采集字段；未知')]
    return dict(title=title,fields=fields,rows=out)
