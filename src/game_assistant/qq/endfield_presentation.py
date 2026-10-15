"""Endfield's six reports, projected from shared domain facts into safe QQ cards.

This module never reads credentials, contacts upstream services or joins game
identities. Only existing scoped snapshots and the public image cache enter it.
"""
from game_assistant.endfield_reports import build_endfield_report, build_gacha_report

from . import presentation as view

SLOTS = {'bodyEquip': '护甲', 'armEquip': '护手', 'firstAccessory': '配件一', 'secondAccessory': '配件二'}


def _image(cache, kind, item):
    # Game instance IDs and official-site catalog keys are separate namespaces.
    # Exact public names provide a fallback, never fuzzy aliases or a guessed
    # gender for the default Endministrator name.
    ref = view.image_ref(cache, 'endfield', kind, url=item.get('avatar_url') or item.get('icon_url'))
    if ref:
        return ref
    for identity in (item.get('char_id'), item.get('id'), item.get('name')):
        if identity is not None:
            ref = view.image_ref(cache, 'endfield', kind, identity)
            if ref:
                return ref
    return None


def _metric(label, data, current='current', maximum='total'):
    return view.metric_field(label, data.get(current), data.get(maximum))


def _footer(snapshot, report=None):
    footer = '更新时间（抓取）：' + view.format_time(snapshot.fetched_at)
    if report and report.get('observed_at'):
        footer += ' · 观测时间：' + view.format_time(report['observed_at'])
    return footer + ' · 北京时间'


def _notice(snapshot):
    return [view.metadata(snapshot)[0]['value'], '缺失字段保留未知；图片是缓存观测，不代表游戏实时状态。']


def _section(title, *, fields=None, rows=None, layout='stats'):
    return {'title': title, 'layout': layout, 'fields': fields or [], 'rows': rows or []}


def _missing(snapshot, key, label):
    if view.obj(view.obj(snapshot.payload).get('availability')).get(key) is not True:
        return label + '尚未采集；请在网站采集后查询。'
    return '本次成功快照的' + label + '列表为空。'


def overview_document(snapshot, asset_cache=None, *, focus=None):
    report = build_endfield_report(view.obj(snapshot.payload), fetched_at=snapshot.fetched_at)
    overview = report['overview']; base = overview['base']; stamina = overview['stamina']
    fields = [_metric('理智', stamina, maximum='maximum'), view.time_field('恢复满时间', stamina.get('expected_full_at'))]
    if focus != 'progress':
        fields += [view.field('账号等级', base.get('level')), view.field('探索等级', base.get('world_level'))]
    sections = [_section('森空岛档案 · ' + view.text(base.get('name')), fields=fields)]
    if focus != 'stamina':
        tasks = []
        for item in overview['progress']:
            values = [_metric('进度', item, current='cur'), view.field('剩余', item.get('remaining'))]
            tasks.append({'title': view.text(item.get('name')), 'fields': values})
        sections.append(_section('日常与通行证', rows=tasks, layout='rows'))
        todos = overview['todos']
        sections.append(_section('已知待办', fields=[view.field(view.text(item.get('name')), '还差 ' + view.text(item.get('remaining')))
                                                   for item in todos] or [view.field('状态', '已知日常暂无未完成项；未采集任务不作判断')]))
    if focus is None:
        training = report['training']['summary']; regions = report['regions']['summary']; ship = report['ship']['summary']
        sections.append(_section('干员与建设', fields=[view.field('已采集干员', training.get('listed_count')),
            view.field('平均等级（已知）', training.get('average_level')), view.field('地区', regions.get('region_count')),
            view.field('据点', regions.get('settlement_count')), view.field('舱室', ship.get('room_count')),
            view.field('有驻守的舱室', ship.get('staffed_rooms'))]))
    title = '终末地 · 理智' if focus == 'stamina' else '终末地 · 日常进度' if focus == 'progress' else '终末地 · 今日总览'
    return view.document('summary', 'endfield', title, sections=sections, notices=_notice(snapshot),
                         subtitle='森空岛档案 · 本人默认角色', footer=_footer(snapshot, report))


def training_document(snapshot, asset_cache=None):
    report = build_endfield_report(view.obj(snapshot.payload), fetched_at=snapshot.fetched_at)
    training = report['training']; summary = training['summary']; entries = training['items']
    values = [view.field('已采集干员', summary.get('listed_count')), view.field('账号声明干员数', summary.get('declared_count')),
              view.field('等级已知', summary.get('known_levels')), view.field('平均等级（已知）', summary.get('average_level'))]
    items = []
    for item in entries:
        row = {'title': view.text(item.get('name'),96), 'subtitle': '稀有度 ' + view.text(item.get('rarity')),
               'fields': [view.field('等级', item.get('level')), view.field('精英阶段', item.get('evolve_phase')),
                          view.field('潜能', item.get('potential'))]}
        items.append(view.with_image(row, _image(asset_cache, 'role', item)))
    notices = _notice(snapshot)
    if not items: notices.append(_missing(snapshot, 'operators', '干员'))
    return view.document('list', 'endfield', '终末地 · 全员练度', sections=[_section('练度统计', fields=values),
        _section('全部干员 · 等级降序', rows=items, layout='grid')], notices=notices,
        subtitle='森空岛档案 · 等级、精英阶段与潜能固定展示', footer=_footer(snapshot, report))


def operator_document(snapshot, name, asset_cache=None, *, detail=None):
    report = build_endfield_report(view.obj(snapshot.payload), fetched_at=snapshot.fetched_at)
    matches = [item for item in report['training']['items'] if item.get('name') == name]
    if len(matches) != 1:
        explanation = ('缓存存在同名角色，无法确定唯一详情；请在网站核对角色。' if matches else
                       '本人角色缓存中未找到该角色；请核对精确名称或在网站采集。')
        return view.message('endfield', '终末地 · 干员详情', explanation)
    item = matches[0]
    equipment_source=item
    detail_fields=[]
    detail_notice='未找到独立详情缓存，当前配装取自档案快照。'
    if detail is not None:
        cached=view.obj(detail.payload)
        same_id=bool(item.get('id')) and cached.get('id')==item['id']
        if same_id:
            # Basic level/potential stay anchored to the account observation.
            # Only equipment fields come from this separately-timed detail.
            equipment_source={**item,**{key:cached[key] for key in ('weapon','equipment','skills') if key in cached}}
            observed=view.format_time(detail.fetched_at);account_time=view.format_time(snapshot.fetched_at)
            older=observed!='未知' and account_time!='未知' and observed<account_time
            state=('最近读取失败，显示旧详情' if detail.state not in ('ok','success') else
                   '已观测详情；早于当前档案' if older else '已观测详情；非实时状态')
            detail_fields=[view.time_field('档案抓取时间',snapshot.fetched_at),view.time_field('配装抓取时间',detail.fetched_at),
                           view.field('配装状态',state)]
            detail_notice='基础练度来自档案；武器、装备与技能来自同一干员的独立详情快照。'
        elif detail.payload is None:
            detail_fields=[view.field('配装状态','最近读取失败，未取得独立详情'),view.time_field('配装抓取时间',detail.fetched_at)]
            detail_notice='独立详情尚无成功观测；当前配装仍取自档案快照。'
        else:
            detail_notice='独立详情与所选干员标识不匹配，已忽略；当前配装取自档案快照。'
    weapon = view.obj(equipment_source.get('weapon')); gem = view.obj(weapon.get('gem'))
    fields = [view.field(label, item.get(key)) for key, label in (
        ('level', '等级'), ('rarity', '稀有度'), ('evolve_phase', '精英阶段'), ('potential', '潜能'),
        ('profession', '职业'), ('property', '属性'))]
    sections = [view.with_image(_section('干员资料', fields=fields, layout='detail'), _image(asset_cache, 'role', item))]
    if detail_fields:sections.append(_section('配装观测来源',fields=detail_fields))
    if weapon:
        sections.append(view.with_image(_section('武器 · ' + view.text(weapon.get('name')), layout='equipment', fields=[
            view.field('等级', weapon.get('level')), view.field('精炼', weapon.get('refine_level')),
            view.field('突破', weapon.get('breakthrough_level')), view.field('稀有度', weapon.get('rarity'))]),
            _image(asset_cache, 'weapon', weapon)))
    else: sections.append(_section('武器', fields=[view.field('状态', '未采集')]))
    if gem:
        sections.append(view.with_image(_section('基质 · ' + view.text(gem.get('name')), layout='equipment',
            rows=[{'title': view.text(term.get('name')), 'fields': [view.field('原始数值', term.get('cost'))]}
                  for term in view.rows(gem.get('terms'))]), _image(asset_cache, 'gem', gem)))
    else: sections.append(_section('基质', fields=[view.field('状态', '未采集')]))
    equipment = view.rows(equipment_source.get('equipment')); gear = []
    for key, label in SLOTS.items():
        found = [entry for entry in equipment if entry.get('slot') == key]
        if not found:
            gear.append({'title': label, 'subtitle': '未采集', 'fields': []}); continue
        for entry in found:
            gear.append(view.with_image({'title': view.text(entry.get('name')), 'subtitle': label,
                'fields': [view.field('等级', entry.get('level')), view.field('稀有度', entry.get('rarity'))]},
                _image(asset_cache, 'equipment', entry)))
    sections.append(_section('四件装备', rows=gear, layout='equipment'))
    skills = view.rows(equipment_source.get('skills'))
    sections.append(_section('技能', layout='skills', rows=[view.with_image({'title': view.text(skill.get('name')),
        'fields': [view.field('等级', skill.get('level'))]}, _image(asset_cache, 'skill', skill)) for skill in skills],
        fields=[] if skills else [view.field('状态', '未采集')]))
    card = view.document('detail', 'endfield', '终末地 · ' + view.text(name), sections=sections,
        notices=_notice(snapshot) + ['配装仅限已采集字段；未采集与未装备不能互相代替。',detail_notice],
        subtitle='森空岛档案 · 干员与已观测配装', footer=_footer(snapshot, report))
    return view.with_image(card, _image(asset_cache, 'role', item))


def regions_document(snapshot, asset_cache=None):
    report = build_endfield_report(view.obj(snapshot.payload), fetched_at=snapshot.fetched_at)
    regions = report['regions']; sections = [_section('地区建设概况', fields=[
        view.field('地区', regions['summary'].get('region_count')), view.field('据点', regions['summary'].get('settlement_count'))])]
    for region in regions['items']:
        fields = [view.field('地区等级', region.get('level')), _metric('总调度券', view.obj(region.get('money')))]
        settlement_rows = []
        for settlement in view.rows(region.get('settlements')):
            officers = view.rows(settlement.get('officers'))
            names = '、'.join(view.text(officer.get('name') or officer.get('id')) for officer in officers)
            values = [view.field('据点等级', settlement.get('level')), _metric('基地调度券', view.obj(settlement.get('coupon'))),
                      view.field('派驻干员', names or ('无派驻' if settlement.get('officers_available') is True else '未知'))]
            settlement_rows.append({'title': view.text(settlement.get('name')), 'fields': values})
        sections.append(_section(view.text(region.get('name')) + ' · 据点', fields=fields, rows=settlement_rows, layout='rows'))
        areas = []
        for area in view.rows(region.get('areas')):
            values = []
            for collection in view.rows(area.get('collections')):
                value = _metric(view.text(collection.get('label')), collection)
                if collection.get('remaining') is not None:
                    value['value'] += ' · 缺 ' + view.text(collection['remaining'])
                values.append(value)
            areas.append({'title': view.text(area.get('name') or area.get('id')), 'fields': values})
        if areas: sections.append(_section(view.text(region.get('name')) + ' · 收集', rows=areas, layout='rows'))
    notices = _notice(snapshot)
    if not regions['items']: notices.append(_missing(snapshot, 'regions', '地区'))
    return view.document('list', 'endfield', '终末地 · 地区建设', sections=sections, notices=notices,
        subtitle='森空岛档案 · 调度券、派驻与收集差额', footer=_footer(snapshot, report))


def ship_document(snapshot, asset_cache=None):
    report = build_endfield_report(view.obj(snapshot.payload), fetched_at=snapshot.fetched_at)
    ship = report['ship']; summary = ship['summary']
    sections = [_section('帝江号概况', fields=[view.field('舱室', summary.get('room_count')),
        view.field('有驻守的舱室', summary.get('staffed_rooms')), view.field('已采集驻守人次', summary.get('operator_slots'))])]
    for room in ship['rooms']:
        operators = view.rows(room.get('operators'))
        items = [view.with_image({'title': view.text(item.get('name') or item.get('id')), 'fields': [
            view.field('心情原始值', item.get('mood_raw')), view.field('信赖原始值', item.get('trust_raw'))]},
            _image(asset_cache, 'role', item)) for item in operators]
        sections.append(_section(view.text(room.get('name')), fields=[view.field('舱室等级', room.get('level'))] +
            ([] if operators else [view.field('驻守', '无驻守' if room.get('operators_available') is True else '未采集')]), rows=items, layout='rows'))
    notices = _notice(snapshot) + ['心情与信赖保留原始观测口径；换算规则未验证，不显示百分比或实时预测。']
    if not ship['rooms']: notices.append(_missing(snapshot, 'ship', '舱室'))
    return view.document('list', 'endfield', '终末地 · 帝江号', sections=sections, notices=notices,
        subtitle='森空岛档案 · 舱室与驻守', footer=_footer(snapshot, report))


def _boundary(count, status):
    if status not in ('exact', 'lower_bound') or count is None: return '未知'
    return ('至少 ' if status == 'lower_bound' else '') + view.text(count)


def gacha_document(snapshot, asset_cache=None, *, compact=False):
    report = build_gacha_report(view.obj(snapshot.payload))
    fields = [view.field(label, report.get(key)) for key, label in (
        ('total', '已记录抽数'), ('six_star', '6 星'), ('five_star', '5 星'), ('free', '免费抽'),
        ('gaps', '已知缺口'), ('average_exact_pulls', '已展示准确区间均抽'))]
    fields += [view.field('准确区间样本数', report.get('known_exact_intervals'))]
    fields += [view.field('同步状态', '无待续传记录' if report.get('complete') is True else
                         '仍有待续传记录' if report.get('complete') is False else '未知')]
    sections = [_section('鹰角寻访 · 本人账本', fields=fields + view.metadata(snapshot)[:2])]
    for pool in report['pools']:
        values = [view.field('已记录抽数', pool.get('total')), view.field('6 星', pool.get('six_star')),
                  view.field('5 星', pool.get('five_star')), view.field('免费抽', pool.get('free'))]
        pity = view.obj(pool.get('since_last_six'))
        values += [view.field('距上次 6 星（记录边界）', _boundary(pity.get('count'), pity.get('status'))),
                   view.field('已知缺口', pool.get('gaps')), view.field('待同步', pool.get('pending'))]
        entries = []
        if not compact:
            for item in view.rows(pool.get('history')):
                entries.append(view.with_image({'title': view.text(item.get('name')), 'fields': [
                    view.field('该次 6 星抽数', _boundary(item.get('pulls'), item.get('status'))),
                    view.field('记录边界', {'exact': '记录内准确', 'lower_bound': '下限'}.get(item.get('status'), '未知')),
                    view.time_field('获取时间', item.get('obtained_at'))]}, _image(asset_cache,
                        'weapon' if pool.get('kind') == 'weapon' else 'role', item)))
        sections.append(_section(view.text(pool.get('label') or pool.get('key')), fields=values, rows=entries, layout='rows'))
    notices = [view.metadata(snapshot)[0]['value'], '只代表已记录历史；同步完成不证明全生涯历史完整。记录边界保留准确、下限或未知。',
               '均抽仅取当前展示的准确出货区间；免费抽与缺口不当作确定垫抽，不预测下次出货。']
    if not report['pools']:
        notices.append('本次账本记录为空。' if report.get('total') == 0 else '暂无已采集寻访记录；请在网站同步本人记录。')
    return view.document('list', 'endfield', '终末地 · 寻访战报', sections=sections, notices=notices,
        subtitle='鹰角寻访授权 · 与森空岛档案独立', footer=_footer(snapshot))
