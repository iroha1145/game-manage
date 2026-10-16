"""Whitelisted display projections for the same Vue website components.

Account scopes/authorization versions remain solely in the renderer envelope.
No raw cached account payload, credentials, source HTML, or user paths reach DOM.
"""
from .assets import safe_public_url
from .commands import GAME_NAMES, mask_links
from .browser_rendering import validate_snapshot
from .rendering import RenderingUnavailable
from ..accounts.models import QueryResult
import re
import unicodedata
from urllib.parse import urlsplit,unquote

CALENDAR = frozenset('name category start_at end_at start_date end_date start_precision end_precision start_text end_text time_text source_name source_title source_post_id source_url source_stale fetched_at version version_metadata phase phases cross_version'.split())
CALENDAR |= frozenset('permanent start_estimated start_basis start_date_precision start_source date_source post_id title url published_at'.split())
VERSION = frozenset('id game server status start_at end_at start_date end_date start_precision end_precision start_text end_text fetched_at source_stale coverage diagnostics sources start_source end_source post_id title url source_name published_at'.split())
ROLE = frozenset('schema_version entries id name role_id role_name role_icon_url level breach chain star_level attribute weapon_type_name is_main_role quality element awaken_level mix_level affinity_exp icon_url weapon properties skills city_skills value attributes equipment slot quality_name role role_skin skin_name skin_icon active_branch_id role_attribute_list attribute_name attribute_value weapon_data weapon_icon weapon_name weapon_star_level weapon_effect_name effect_description reson_level main_prop_list skill_list skill active_branch skill_branches type description chain_list unlocked order phantom_data cost equip_phantom_list phantom_prop skill_description quality main_props sub_props fetter_detail first_description second_description triple_description num equip_phantom_attribute_list equip_phantom_add_prop_list is_addition chain_unlock_num total_skill_level'.split())
ROLE |= frozenset('group_type awaken_effects suit description_two description_four conditions activation_count core pie main_properties area substats_complete breakthrough_level buff_name buff_description lbd items title desc assessment score status reason model_version weight_version source formula contributions'.split())
ROLE |= frozenset('formula_text model_fingerprint contribution_id weight unit current_value reference_value factor exact_fraction numerator denominator rounding_adjustment'.split())
ROLE |= frozenset('item_id item_results partial partial_known_total display_mode'.split())
NTE_OVERVIEW = frozenset('id name level quality element awaken_level mix_level affinity_exp icon_url'.split())
GACHA = frozenset('schema_version pools details name id item_id total_draws s_count average guarantee luck_title luck_type lucky_type pity obtained_at total gold_total items gold pool coverage earliest latest imported_at source message failed_pools state total rarity_distribution rank rarity time timestamp quantity reward_name reward_id reward_rank pool_group_id result_type pool_id total_pulls hard_pity_remaining rule_basis as_of latest_record_at basis missing_requirements total_records records counts complete'.split())
GACHA |= frozenset('aggregates five_star_total period_count kind source_time time_basis diagnostics segment_count latest_confirmed continuity_confirmed warnings rule_version up_guarantee count status limit offset'.split())

# Named business fields used by the corresponding website components. Raw
# evolving dictionaries and account identity fields are never copied wholesale.
COMMON = frozenset('schema_version name title id level value count total current maximum expected_full_at updated_at state complete fetched_at icon_url description type entries items details'.split())
ACCOUNT = COMMON | frozenset('nickname server_name world_level active_days tycoon_level character_count achievement_count achievement_total house_count house_total vehicle_count vehicle_total extra profile unlock level_name next_exp exp_limit achievement_star big_count small_count box_list treasure_box_list phantom_box_list box_name num creat_time'.split())
STAMINA = COMMON | frozenset('city_current city_maximum daily_activity weekly_remaining energy max_energy liveness liveness_max_count weekly_inst_count weekly_inst_count_limit weekly_inst_title store_energy store_energy_limit store_energy_title store_energy_recover_time'.split())
PROGRESS = COMMON | frozenset('completed bronze silver gold categories cur refresh_at progress'.split())
EXPLORATION = COMMON | frozenset('areas country_groups detections by_level progress'.split())
END_FIELD = (COMMON | ACCOUNT | STAMINA | PROGRESS | ROLE) - {'role_id'}
END_FIELD |= frozenset('base stamina operators regions ship achievements main_mission char_count weapon_count avatar_url rarity potential evolve_phase profession property refine_level gem terms collections level_id puzzle_count chest_count piece_count blackbox_count levels puzzles chests equipment_chests pieces blackboxes settlements money money_max medals charId physicalStrength favorability'.split())
CALABASH = COMMON | frozenset('base_catch catch_quality cur_exp max_count phantom_list phantom_name phantom_icon phantom_id quality catch_prob'.split())
ACTIVITIES = COMMON | STAMINA | frozenset('sections unlock is_unlock exp next_exp max_exp max_level rank level_name badge_list badge_num max_badge_num max_card_num card_total_num card_num max_animal_num animal_num max_map_num map_num max_toy_num toy_num toy_count animal_count map_count item_num max_item_num reward_num max_reward_num reward_count reward badge card animal map toy sort'.split())
RESOURCES = COMMON | frozenset('period kind data total_coin total_star coin_inc star_inc inc coin_list star_list item_list num start_time end_time'.split())
COMBAT = COMMON | ROLE | frozenset('tower hologram slash data star max_star difficulty_list difficulty difficulty_name tower_area_list area_name floor_list floor floor_index floor_name role_list roles role_level challenge_info boss_name boss_level pass_time season_end_at is_unlock challenge_list challenge_name score rank all_score max_score half_list half_name buff_list buff_name buff_description'.split())
ASSETS = COMMON | frozenset('owned_count owned resident_ids furniture base advanced models show_name show_id members role_ids role_name slot role_id rarity image_urls'.split())
NEWS = frozenset('id title name summary content_category published_at source source_name source_title source_url source_stale url tags category cover_url image_url'.split())
# Existing public article builders: WuWa announcements, Tajiduo _post_url,
# endfield_public.NEWS_URL and sources.bilibili dynamic links. These anchors
# never become image prefetch URLs and do not broaden assets.ALLOWED_HOSTS.
ARTICLE_HOSTS = frozenset(('www.kurobbs.com','bbs.tajiduo.com','endfield.hypergryph.com','t.bilibili.com'))
END_GACHA = GACHA | COMMON | frozenset('key label six_star five_star free gaps pending since_last_six recent_six history pool_name pulls is_free last_sync_at pool_key char_id char_name newest_at oldest_at'.split())
END_REPORT = END_FIELD | frozenset('key label region_count settlement_count report overview training honor available availability observed_at todos remaining percent summary listed_count declared_count known_levels average_level max_level rarity_counts phase_counts items rooms room_count staffed_rooms operator_slots operators_available settlements_available officer_char_ids officers officers_available coupon areas equipment_chest_count mood_raw trust_raw mood_percent trust_percent trust_level_name conversion_model category is_plated obtained_at char_id doc_count slot_name slot_label tactical_item active_effect passive_effect operator_detail operator_detail_id operator_fetched_at operator_stale'.split())
END_CHALLENGES = COMMON | frozenset('reports supported available kind stale records honors summary listed_count highest challenge_count start_at end_at stars weeks groups stages difficulty passed result first_pass_at'.split())
PANEL_CAPS = {
 'nte':{'account':ACCOUNT,'stamina':STAMINA,'progress':PROGRESS,'exploration':EXPLORATION,'record':ACCOUNT|frozenset(('cards',)), 'roles':ROLE,'gacha':GACHA,'realestate':ASSETS,'vehicles':ASSETS,'teams':ASSETS},
 'wuthering_waves':{'account':ACCOUNT,'stamina':STAMINA,'progress':PROGRESS,'exploration':EXPLORATION,'roles':ROLE|frozenset(('extra',)),'gacha':GACHA,'combat':COMBAT,'calabash':CALABASH,'activities':ACTIVITIES,'resources':RESOURCES},
 'endfield':{cap:END_REPORT for cap in ('account','stamina','progress','exploration','roles','record','training','regions','ship','honor','operator_detail')},
}
PANEL_CAPS['endfield']['gacha']=END_GACHA | frozenset('report four_star unknown_rarity history_total history_available history_limit history_truncated known_exact_intervals average_exact_pulls pool_label'.split())
PANEL_CAPS['endfield']['combat']=END_CHALLENGES
for _game in PANEL_CAPS:
 PANEL_CAPS[_game].update(news=NEWS,events=CALENDAR,recent_events=CALENDAR)
DISPLAY_FIELDS = frozenset().union(COMMON,*[fields for caps in PANEL_CAPS.values() for fields in caps.values()])
PROVIDERS = frozenset(('kuro','tajiduo','skland','hypergryph','public'))
_TECHNICAL = re.compile(r'^(?:(?:缓存状态|快照状态|公共快照状态|完整性|来源诊断|来源状态|数据状态)(?:：|$)|缓存快照$|数据可能过期$|当前查询失败或待刷新，显示旧快照$|部分来源不可用，显示可用来源数据$)')


def _clean_text(value):
    """Pure text cleaning; typed field bounds are enforced by display_text."""
    text=re.sub(r'(?<!\d)\d{7,}(?!\d)','***',str(value))
    text=mask_links(text)
    text=re.sub(r'<@[^>]*>','',text)
    text=''.join(char for char in text if char=='\n' or not unicodedata.category(char).startswith('C')).strip()
    text=re.sub(r'(?:[A-Za-z]:[\\/]|/(?:home|Users|private|data)/)[^\s，；]+','[路径已隐藏]',text)
    return text


def display_text(value,limit=8000):
    # Match user-text sanitization without safe_text's 1800-character reply
    # window: complete source strings are retained or explicitly rejected.
    text=_clean_text(value)
    if len(text)>limit:raise RenderingUnavailable('qq_browser_data_limit')
    return text


def _article_excerpt(row):
    """The website list's 180-character summary, never an article full text."""
    from html import unescape
    def readable(value):
        if not isinstance(value,str):return ''
        value=re.sub(r'<(script|style|iframe)\b[^>]*>[\s\S]*?</\1>','',value,flags=re.I)
        return re.sub(r'<[^>]*>','',unescape(value)).strip()
    text=readable(row.get('summary')) or readable(row.get('body')) or readable(row.get('content_text'))
    text=re.sub(r'\s+',' ',_clean_text(text)).strip()
    return text[:180]+('…' if len(text)>180 else '')


def safe_article_url(value):
    if not isinstance(value,str) or not 1<=len(value)<=2048 or not value.isascii() or re.search(r'[\s\\\x00-\x1f\x7f]',value):return None
    try:
        url=urlsplit(value)
        path=unquote(url.path)
        if url.scheme not in ('http','https') or url.hostname not in ARTICLE_HOSTS or url.username or url.password or url.port not in (None,80,443):return None
        if url.query or url.fragment or not path.startswith('/') or re.search(r'[\s\\\x00-\x1f\x7f:%]',path) or any(part in ('.','..') for part in path.split('/')):return None
        return value
    except (ValueError,UnicodeError):return None


def user_notices(items):
    for item in items:
        if _TECHNICAL.match(str(item)):continue
        text=display_text(item).replace('；覆盖待核验。','。')
        if text.startswith('暂无成功快照；'):text='暂无可显示数据；请刷新后重试。'
        yield text


def panel_payload(game,provider,capability,payload):
    allowed=PANEL_CAPS.get(game,{}).get(capability)
    if allowed is None:raise RenderingUnavailable('qq_browser_unsupported_panel')
    if game=='endfield' and provider=='hypergryph' and capability=='account':allowed=ACCOUNT
    if capability=='news' and isinstance(payload,list):
        payload=[{**{key:value for key,value in row.items() if key in NEWS},'summary':_article_excerpt(row)} for row in payload if isinstance(row,dict)]
    def visit(value,depth=0):
        if depth>14:raise RenderingUnavailable('qq_browser_data_limit')
        if isinstance(value,dict):
            out={}
            for key,child in value.items():
                if key not in allowed:continue
                if capability=='news' and key=='id':out[key]=str(child) if type(child) in (str,int) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',str(child)) else None
                elif capability=='news' and key in ('url','source_url'):out[key]=safe_article_url(child)
                elif game=='endfield' and key in ('id','char_id','charId','operator_detail_id'):
                    out[key]=child if isinstance(child,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',child) else None
                elif key in ('sections','challenge_info') and isinstance(child,dict):
                    out[key]={f'bucket_{i}':visit(item,depth+1) for i,item in enumerate(child.values())}
                elif key=='by_level' and isinstance(child,dict):
                    out[key]={name:count for name,count in child.items() if name in ('轻波级','巨浪级','怒涛级','海啸级') and (count is None or type(count) in (int,float))}
                elif key in ('body','summary','content_text') and isinstance(child,str):
                    plain=re.sub(r'<(script|style|iframe)\b[^>]*>[\s\S]*?</\1>','',child,flags=re.I)
                    from html import unescape
                    out[key]=display_text(unescape(re.sub(r'<[^>]*>','',plain)))
                elif key=='image_urls' and isinstance(child,list):out[key]=[safe_public_url(url) for url in child]
                elif key.endswith(('_url','_icon')) or key=='url':out[key]=safe_public_url(child)
                elif key in ('rarity_counts','phase_counts') and isinstance(child,dict):
                    choices=set('123456') if key=='rarity_counts' else set('0123456')
                    out[key]={str(k):v for k,v in child.items() if str(k) in choices and type(v) in (int,float) and v>=0}
                elif key in ('counts','rarity_distribution') and isinstance(child,dict):out[key]={str(k):v for k,v in child.items() if str(k) in ('3','4','5','6','S','A','B','unknown') and type(v) in (int,float)}
                else:out[key]=visit(child,depth+1)
            return out
        if isinstance(value,list):return [visit(item,depth+1) for item in value]
        if isinstance(value,str):return display_text(value)
        if value is None or type(value) in (bool,int,float):return value
        return None
    return visit(payload)


def game_panel(game,provider,capability,row,*,summary=False,resolved=None):
    raw=row.payload
    if resolved is not None and capability=='roles':
        raw={**raw,'operators':[resolved]} if game=='endfield' and isinstance(raw,dict) else [resolved] if isinstance(raw,list) else {**raw,'entries':[resolved]}
    if summary and capability=='roles':
        if isinstance(raw,list):raw=raw[:6]
        elif isinstance(raw,dict):raw={**raw,**{key:raw[key][:6] for key in ('entries','operators') if isinstance(raw.get(key),list)}}
        fields=NTE_OVERVIEW|frozenset('schema_version entries operators role_id role_name attribute weapon chain breach star_level extra total_skill_level chain_unlock_num rarity potential evolve_phase profession property'.split())
        if game=='nte':fields=NTE_OVERVIEW|{'schema_version','entries'}
        raw=project(raw,fields)
    if summary and capability=='gacha':raw=project(raw,PANEL_CAPS[game]['gacha']-{'details','records','items','gold','recent_six','history','aggregates'})
    return {'game':game,'provider':provider,'capability':capability,'snapshot':metadata(row,panel_payload(game,provider,capability,raw))}


def game_snapshot(panels,now,page=1,*,title='游戏数据',command='总览',notices=()):
    games={panel['game'] for panel in panels}
    return snapshot('game_snapshot',next(iter(games)) if len(games)==1 else 'all',{'panels':panels,'notices':list(user_notices(notices))},now,page,title,command)


def notice_snapshot(card,now,page=1):
    from .cards import validate_card_document
    card=validate_card_document(card)
    sections=[]
    for section in card['sections']:
        if _TECHNICAL.match(section['title']):continue
        items=[]
        for row in [section,*section.get('rows',[])]:
            if row is not section and row.get('title') and not _TECHNICAL.match(row['title']):items.append(display_text(row['title']))
            items.extend(display_text(field['label']+'：'+field['value']) for field in row.get('fields',[]) if not _TECHNICAL.match(field['label']))
        if items:sections.append({'title':display_text(section['title']),'items':items})
    data={'title':display_text(card['title'],128),'sections':sections,'notices':list(user_notices(card['notices']))}
    return snapshot('notice',card['game'],data,now,page,data['title'],'帮助')


def filtered_events_snapshot(snapshots,command,now,page=1):
    from .event_views import normalized,endpoint
    from datetime import timedelta
    panels=[]
    for game,row in snapshots.items():
        selected=[]
        for item in normalized(row.payload):
            first,last=endpoint(item,'start'),endpoint(item,'end')
            invalid=first is not None and last is not None and last<=first
            if command=='events':
                include=not invalid and first is not None and last is not None and first<=now<last
                include|=(invalid or first is None or last is None) and not (last and last<=now or first and first>now)
            else:
                include=not invalid and any(stamp is not None and now<stamp<=now+timedelta(hours=168) for stamp in (first,last))
                include|=invalid or any(endpoint(item,side) is None and (item.get(side+'_text') or item.get(side+'_date') or item.get(side+'_precision') in ('relative','day','dependent')) for side in ('start','end'))
            if include:selected.append({**{key:value for key,value in item.items() if key!='display_title'},'name':item['display_title']})
        panels.append(game_panel(game,'public',command,QueryResult(selected,row.fetched_at,row.state,row.complete)))
    return game_snapshot(panels,now,page,title='进行中的活动' if command=='events' else '近期活动 · 未来168小时',command='活动' if command=='events' else '近期活动')


def project(value, allowed, *, depth=0):
    if depth>14:return None
    if isinstance(value,dict):
        out={}
        for key,child in value.items():
            if key not in allowed:continue
            if key.endswith(('_url','_icon')) or key=='icon_url':
                out[key]=safe_public_url(child)
            elif key=='version_metadata':out[key]=project(child,VERSION,depth=depth+1)
            elif key in ('rarity_distribution','counts') and isinstance(child,dict):
                out[key]={str(k):v for k,v in child.items() if str(k) in ('3','4','5','S','A','B','unknown') and type(v) in (int,float)}
            else:out[key]=project(child,allowed,depth=depth+1)
        return out
    if isinstance(value,list):
        # Oversized input fails validation; never silently declare truncation complete.
        return [project(item,allowed,depth=depth+1) for item in value]
    if value is None or type(value) in (str,bool,int,float):return value
    return None


def metadata(snapshot,payload):
    return {'payload':payload,'fetched_at':snapshot.fetched_at,'state':snapshot.state,'complete':snapshot.complete,'stale':snapshot.state not in ('ok','success')}


def snapshot(kind,game,data,now,page,title,command):
    # Minutes only, like the page shows: the snapshot is part of the image cache key,
    # and a microsecond clock made every request a cache miss.
    return validate_snapshot({'schema_version':1,'kind':kind,'game':game or 'all','display_data':data,
        'as_of':now.replace(second=0,microsecond=0).isoformat(),'page':page,'title':title,'next_command':command,'theme':'light'})


def calendar_snapshot(snapshots,now,page=1):
    games=[];output={}
    for game,row in snapshots.items():
        games.append({'game_id':game,'display_name':GAME_NAMES[game]})
        data=metadata(row,project(row.payload,CALENDAR))
        version=getattr(row,'version_metadata',None)
        if version is not None:data['version_metadata']=project(version,VERSION)
        output[game]={'events':data}
    command=(GAME_NAMES[next(iter(snapshots))]+' ' if len(snapshots)==1 else '')+'日历'
    return snapshot('calendar',next(iter(snapshots)) if len(snapshots)==1 else 'all',{'games':games,'snapshots':output},now,page,'活动日历 · 版本汇总',command)


def role_snapshot(game,row,now,page=1,*,detail=None,resolved_id=None):
    if game=='nte':
        payload=project(row.payload,ROLE)
        if resolved_id:
            from ..character_search import character_id
            entries=payload.get('entries') if isinstance(payload,dict) else None
            selected=[entry for entry in entries or [] if isinstance(entry,dict) and character_id(entry)==resolved_id]
            if len(selected)!=1:raise RenderingUnavailable('qq_browser_selected_role_unavailable')
            payload={**payload,'entries':selected}
        elif isinstance(payload,dict) and isinstance(payload.get('entries'),list):
            payload={'schema_version':payload.get('schema_version'),
                'entries':[project(entry,NTE_OVERVIEW) for entry in payload['entries'] if isinstance(entry,dict)]}
        data=metadata(row,payload)
        data['display_mode']='detail' if resolved_id else 'roster'
        return snapshot('nte_role',game,{'snapshot':data},now,page,'异环 · 角色练度','异环 角色'+(' '+resolved_id if resolved_id else ''))
    if game=='wuthering_waves' and detail is not None:
        if not resolved_id:return None
        from ..wuwa_role_detail import role_detail_data
        data=role_detail_data(detail.payload,resolved_id,allow_flat_missing_identity=True)
        if data is None:return None
        return snapshot('wuwa_role',game,{'detail':project(data,ROLE),'fetched_at':detail.fetched_at},now,page,'鸣潮 · '+str(data.get('role',{}).get('role_name') or '角色详情'),'鸣潮 角色 '+resolved_id)
    return None


def gacha_snapshot(game,row,now,page=1,*,ledger=None):
    if game=='wuthering_waves':return snapshot('wuwa_gacha',game,{'archive':project(row.payload,GACHA)},now,page,'鸣潮 · 抽卡档案','鸣潮 抽卡')
    if game=='nte':return snapshot('nte_gacha',game,{'snapshot':metadata(row,project(row.payload,GACHA)),'ledger':project(ledger.payload,GACHA) if ledger is not None else None,'roles':[]},now,page,'异环 · 抽卡统计与账本','异环 抽卡')
    return None


def asset_urls(node):
    if isinstance(node,dict):
        if node.get('kind')=='game_snapshot':
            # Only these panel components currently mount images. Account,
            # stamina, exploration, news and Endfield panels show text/metrics;
            # do not prefetch their unused nested role/weapon assets.
            for panel in node['display_data']['panels']:
                payload=panel['snapshot']['payload']
                if panel['capability']=='roles' and panel['game'] in ('nte','wuthering_waves'):
                    entries=payload if isinstance(payload,list) else payload.get('entries',[]) if isinstance(payload,dict) else []
                    for entry in entries:
                        if isinstance(entry,dict):yield from asset_urls(entry.get('icon_url'))
                elif panel['game']=='nte' and panel['capability']=='teams':
                    for entry in payload.get('entries',[]) if isinstance(payload,dict) else []:
                        if isinstance(entry,dict):
                            yield from asset_urls(entry.get('icon_url'))
                            yield from asset_urls(entry.get('image_urls',[]))
            return
        for value in node.values():yield from asset_urls(value)
    elif isinstance(node,list):
        for value in node:yield from asset_urls(value)
    elif isinstance(node,str):
        safe=safe_public_url(node)
        if safe:yield safe
