"""Small explicit self-query grammar and QQ reply text sanitizing."""
from dataclasses import dataclass
import re

GAMES = {'ww':'wuthering_waves','鸣潮':'wuthering_waves','wuthering_waves':'wuthering_waves',
         'yh':'nte','异环':'nte','nte':'nte','终末地':'endfield','endfield':'endfield'}
GAME_NAMES = {'wuthering_waves':'鸣潮','nte':'异环','endfield':'终末地'}

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
PAGED_COMMANDS = frozenset(('help','stamina','calabash','overview','summary','status','roles','exploration','combat','progress','gacha','calendar','events','recent_events','news',
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
    if parts and parts[0] in VERBS and VERBS[parts[0]] in ('help','events','recent_events','calendar'):
        verb=VERBS[parts[0]]
        if len(parts)==1:return Command(verb)
        if len(parts)==2 and re.fullmatch(r'[0-9]+',parts[1]):
            if verb in PAGED_COMMANDS and 1<=int(parts[1])<=MAX_PAGE:
                return Command(verb,page=int(parts[1]))
            return Command('help')
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
# ASCII lookbehind: \w would also treat Chinese text as part of the name, so 官网example.com stayed a link.
DOMAIN = re.compile(r'(?<![A-Za-z0-9_@])(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>]*)?', re.I)


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
