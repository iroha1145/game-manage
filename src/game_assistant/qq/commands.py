"""Small explicit self-query grammar and allowlisted text summaries."""
from dataclasses import dataclass
import re

GAMES = {'ww':'wuthering_waves','鸣潮':'wuthering_waves','wuthering_waves':'wuthering_waves',
         'yh':'nte','异环':'nte','nte':'nte','终末地':'endfield','endfield':'endfield'}
GAME_NAMES = {'wuthering_waves':'鸣潮','nte':'异环','endfield':'终末地'}
HELP = ('帮助：@机器人发送「我的」或「总览」查看三游戏；/ww（鸣潮）、/yh（异环）、/endfield（终末地）查看单游戏。\n'
        '共用指令：游戏 角色、游戏 角色 精确名称、游戏 体力、游戏 探索、'
        '游戏 挑战、游戏 进度、游戏 抽卡。\n'
        '公共资讯：游戏 公告、游戏 近期活动（未来168小时）、游戏 活动（进行中）、游戏 日历（本版本已知完整范围，覆盖待核验）；无前缀查询按本人授权游戏分别展示版本。'
        '鸣潮专项：数据坞、活动进度、资源；异环专项：房产、车辆、队伍、档案。'
        '终末地专项：理智、练度、地区、帝江号、光荣之路、寻访战报；干员 精确名称查看配装。'
        '刷新 游戏仅排队刷新；我的账号查看授权；看板查看网站入口。\n'
        '绑定：先在网站生成绑定码，再发送「绑定 实际绑定码」即完成。'
        '私人查询仅限本人已绑定的默认账号；未知数据不会补成零。'
        '角色详情按本人缓存中的精确名称筛选；长列表直接显示一张长图，无需翻页。时间均为北京时间到分钟。缺失数据需在网站采集，不自动登录。')

VERBS = {'查询':'summary','query':'summary','总览':'summary','概览':'summary','summary':'summary',
         '角色':'roles','干员':'roles','roles':'roles','体力':'stamina','stamina':'stamina',
         '探索':'exploration','exploration':'exploration','挑战':'combat','战斗':'combat','combat':'combat',
         '进度':'progress','progress':'progress','抽卡':'gacha','寻访':'gacha','gacha':'gacha',
         '活动':'events','近期活动':'recent_events','events':'events','recent_events':'recent_events','日历':'calendar','calendar':'calendar','公告':'news','资讯':'news','news':'news',
         '刷新':'refresh','refresh':'refresh'}
VERBS.update({'帮助':'help','help':'help','数据坞':'calabash','calabash':'calabash','活动进度':'activities','activities':'activities',
              '资源':'resources','resources':'resources','房产':'realestate','realestate':'realestate',
              '车辆':'vehicles','vehicles':'vehicles','队伍':'teams','teams':'teams','档案':'record','record':'record'})
VERBS.update({'理智':'stamina','练度':'training','全员练度':'training','training':'training',
              '地区':'regions','地区建设':'regions','regions':'regions','帝江号':'ship','ship':'ship','寻访战报':'gacha',
              '光荣之路':'honor','勋章':'honor','奖章':'honor','honor':'honor'})
PAGED_COMMANDS = frozenset(('overview','summary','status','roles','exploration','combat','progress','gacha','calendar','events','recent_events','news',
                            'activities','resources','realestate','vehicles','teams','record','training','regions','ship','honor'))
MAX_PAGE = 100


@dataclass(frozen=True)
class Command:
    command: str
    game: str | None = None
    code: str | None = None
    role_name: str | None = None
    page: int = 1


def parse_command(content):
    if not isinstance(content, str) or len(content)>512:
        return Command('help')
    raw = re.sub(r'<@!?\d+>', '', content).strip().lstrip('/').strip()
    if any(ord(c)<32 and c not in ('\t','\n','\r') for c in raw):
        return Command('help')
    parts = raw.split()
    if len(parts)==2 and parts[0] in ('绑定','bind') and re.fullmatch(r'[A-Za-z0-9_-]{4,128}',parts[1]):
        return Command('binding',code=parts[1])
    if raw in ('帮助','help','?',''):
        return Command('help')
    if raw in ('我的账号','状态','status'):
        return Command('status')
    if raw in ('我的','总览','我的总览','overview','my'):
        return Command('overview')
    if len(parts)==2 and parts[0] in ('我的','总览','我的总览','overview','my','我的账号','状态','status'):
        if re.fullmatch(r'[0-9]+',parts[1]) and 1<=int(parts[1])<=MAX_PAGE:
            return Command('status' if parts[0] in ('我的账号','状态','status') else 'overview',page=int(parts[1]))
    if raw in ('看板','dashboard'):
        return Command('dashboard')
    if raw in GAMES:
        return Command('summary',GAMES[raw])
    if raw in VERBS and VERBS[raw] in ('events','recent_events','calendar'):
        return Command(VERBS[raw])
    # Keep established compact Chinese aliases, including 鸣潮角色.
    if parts:
        for alias in ('鸣潮','异环','终末地'):
            if parts[0].startswith(alias) and parts[0][len(alias):] in VERBS:
                parts=[alias,parts[0][len(alias):],*parts[1:]]
                break
    if len(parts)<2:return Command('help')
    if parts[0] in GAMES and parts[1] in VERBS:
        game,verb=GAMES[parts[0]],VERBS[parts[1]]
    elif parts[1] in GAMES and parts[0] in VERBS:
        game,verb=GAMES[parts[1]],VERBS[parts[0]]
    else:return Command('help')
    if verb in ('training','regions','ship','honor') and game!='endfield':return Command('help')
    rest=parts[2:]
    page=1
    if rest and re.fullmatch(r'[0-9]+',rest[-1]):
        if verb not in PAGED_COMMANDS or not 1<=int(rest[-1])<=MAX_PAGE:return Command('help')
        page=int(rest.pop())
    if not rest:return Command(verb,game,page=page)
    if verb=='roles' and len(rest)==1 and 1<=len(rest[0])<=64 and rest[0].isprintable():
        return Command(verb,game,role_name=rest[0],page=page)
    return Command('help')


LINK = re.compile(r'(?:https?://|www\.)[^\s<>]+', re.I)
DOMAIN = re.compile(r'(?<![\w@])(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>]*)?', re.I)


def mask_links(text):
    """Unapproved URLs and bare domains never reach QQ as links."""
    return DOMAIN.sub('[链接未启用]', LINK.sub('[链接未启用]', text))


def safe_text(text, *, urls_approved=False):
    # Always mask long numerical identifiers, including identifiers embedded in nicknames.
    text = re.sub(r'(?<!\d)\d{7,}(?!\d)', '***', str(text))
    if not urls_approved:
        text = mask_links(text)
    # Prevent platform mention tags / control characters copied from upstream data.
    text = re.sub(r'<@[^>]*>', '', text)
    return ''.join(c for c in text if c=='\n' or ord(c)>=32)[:1800]


def value(item):
    return '未知' if item is None else str(item)


def render_result(label, result, capability):
    lines=[label]
    if result.state not in ('ok','success'):
        sources = getattr(result, 'poll_status', {}).get('source_statuses', {})
        available = (result.payload is not None and getattr(result, 'stale', None) is False
                     and any(source.get('state') in ('error', 'auth_expired') for source in sources.values()))
        lines.append('暂无成功快照' if result.payload is None else
                     '部分来源不可用，显示可用来源数据' if available else
                     '当前查询失败或待刷新，显示旧快照')
    elif getattr(result, 'stale', False):
        lines.append('缓存已过期，等待刷新')
    payload=result.payload
    if payload is None:
        lines.append('暂无数据')
    elif capability=='account' and isinstance(payload,dict):
        base=payload.get('base')
        if isinstance(base,dict):
            lines.extend(('昵称：'+value(base.get('name')), '等级：'+value(base.get('level'))))
            stamina=payload.get('stamina')
            if isinstance(stamina,dict):lines.append('体力：'+value(stamina.get('current'))+'/'+value(stamina.get('maximum')))
        else:lines.extend(('昵称：'+value(payload.get('nickname')), '等级：'+value(payload.get('level'))))
    elif capability=='stamina' and isinstance(payload,dict):
        lines.append('体力：'+value(payload.get('current'))+'/'+value(payload.get('maximum')))
    elif capability=='gacha' and isinstance(payload,dict):
        # No guessed pity/history: only explicitly recorded totals are rendered.
        for key,title in (('total','记录数'),('total_count','记录数'),('history_complete','历史完整性')):
            if key in payload:
                lines.append(title+'：'+value(payload[key]))
        if len(lines)<=2:
            lines.append('寻访缓存可用；完整账本请在网站查看')
    elif capability=='record' and isinstance(payload,dict):
        lines.append('森空岛档案缓存可用；详细档案请在网站查看')
    else:
        rows=payload if isinstance(payload,list) else payload.get('roles',payload.get('events',[])) if isinstance(payload,dict) else []
        if isinstance(rows,list):
            for row in rows[:6]:
                if not isinstance(row,dict):continue
                title=row.get('title') or row.get('name')
                if not title:continue
                line=str(title)
                if capability=='roles':line+=' · 等级 '+value(row.get('level'))
                elif capability=='events':line+=' · 截止 '+value(row.get('end_at'))
                lines.append(line)
            if not rows:lines.append('当前列表为空')
    lines.append('更新时间：'+value(result.fetched_at))
    if result.complete is False:lines.append('历史或数据完整性：不完整')
    elif result.complete is None:lines.append('完整性：未知')
    return safe_text('\n'.join(lines))
