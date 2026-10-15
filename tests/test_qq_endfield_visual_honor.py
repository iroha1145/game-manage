"""Industrial Endfield reports keep source uncertainty and offline boundaries."""
from copy import deepcopy
from dataclasses import asdict
from io import BytesIO

from PIL import Image
import pytest
from pydantic import ValidationError

from game_assistant.qq.assets import PublicAssetCache, sanitize_image
from game_assistant.qq.card_rendering import render_card
from game_assistant.qq.card_rendering_v3 import EndfieldLayout
from game_assistant.qq.cards import card_to_text
from game_assistant.qq.commands import parse_command
from game_assistant.qq.endfield_presentation import honor_document, operator_document, overview_document
from game_assistant.qq.presentation import long_document, asset_refs
from game_assistant.qq.query_routes import QueryBody
from tests.test_qq_endfield_reports import cjk_font, snapshot, synthetic_account
from tests.test_qq_unified_queries import CachedQuery, IDENTITY, service, no_external_network


def synthetic_honor(count=12):
    return {'availability': {'honor': True}, 'achievements': {'count': count+2,
        'medals': [{'achievementData': {'id': f'medal_{index}', 'name': f'合成勋章{index:02}'},
                    'level': index%4, 'isPlated': index%2==0, 'obtainTs': 1792026000 if index else None}
                   for index in range(count)]}}


@pytest.mark.parametrize('raw',['终末地 光荣之路','终末地勋章','勋章 终末地','终末地 奖章'])
def test_honor_commands_are_endfield_only(raw):
    parsed=parse_command(raw)
    assert parsed.command=='honor' and parsed.game=='endfield'
    QueryBody(identity=asdict(IDENTITY),command=parsed.command,game=parsed.game)
    assert parse_command('鸣潮 勋章').command=='help'
    with pytest.raises(ValidationError):QueryBody(identity=asdict(IDENTITY),command='honor',game='nte')


def test_honor_uses_default_skland_snapshot_and_keeps_all_observed_medals():
    query=CachedQuery();query.add('endfield','hypergryph','hg',{'account':synthetic_honor(25)})
    query.add('endfield','skland','sk',{'account':synthetic_honor()})
    query.add('endfield','skland','other',{'account':synthetic_honor(20)},default=False)
    context={};reply=service(query).query(IDENTITY,'honor','endfield',image_context=context)
    assert [(scope.account_id,cap) for scope,cap in query.reads]==[('sk','account')]
    assert query.refreshes==[] and len(context['grants'])==1
    assert sum(len(section['rows']) for section in context['card']['sections'] if section.get('category')=='ef_medals')==12
    assert '合成勋章11' in reply['text'] and '账号声明勋章数：14' in reply['text']
    assert '镀层：是' in reply['text'] and '等级：0' in reply['text'] and '获得时间：未知' in reply['text']


def test_honor_unknown_empty_and_stale_states_remain_distinct():
    unknown=card_to_text(honor_document(snapshot({'achievements':{'medals':[]}})))
    empty=card_to_text(honor_document(snapshot({'availability':{'honor':True},'achievements':{'count':0,'medals':[]}})))
    assert '已采集勋章：未知' in unknown and '尚未采集' in unknown
    assert '已采集勋章：0' in empty and '列表为空' in empty
    assert '旧快照' in card_to_text(honor_document(snapshot(synthetic_honor(),state='error')))
    card=long_document(honor_document(snapshot(synthetic_honor(300))))
    assert any('省略' in notice for notice in card['notices'])


def test_honor_icons_only_use_safe_refs_and_do_not_modify_source():
    source=synthetic_honor(2);before=deepcopy(source)
    source['achievements']['medals'][0]['achievementData']['initIcon']='https://example.invalid/private.png'
    source['achievements']['medals'][1]['achievementData']['initIcon']='https://web.hycdn.cn/public/medal.png?token=private'
    before=deepcopy(source)
    card=long_document(honor_document(snapshot(source),PublicAssetCache()))
    assert not asset_refs(card) and source==before and 'private' not in str(card)


def test_industrial_render_uses_square_frames_and_no_initial_letter_placeholders(monkeypatch):
    operations=[];original=EndfieldLayout.paint
    def capture(self,height):
        operations.extend(self.ops)
        return original(self,height)
    monkeypatch.setattr(EndfieldLayout,'paint',capture)
    card=long_document(overview_document(snapshot()))
    png=render_card(card,font=cjk_font(),budget_seconds=10)
    assert Image.open(BytesIO(png)).width==1080
    texts=[operation[2] for operation in operations if operation[0]=='text']
    assert '01' in texts and 'DAILY OPERATIONS' in texts
    assert '每日活跃' in texts and '60/100' in texts
    assert '图标暂无' not in texts and '每' not in texts and '终' not in texts
    assert all(operation[3]==0 for operation in operations if operation[0]=='rect')
    # The daily metric now creates an actual nonzero progress fill.
    assert any(operation[0]=='rect' and operation[2]=='#ffd000' and operation[1][2]-operation[1][0]>100
               and operation[1][3]-operation[1][1]==8 for operation in operations)


def test_portrait_catalog_precedes_avatar_url_and_failed_portrait_uses_small_avatar(monkeypatch):
    cache=PublicAssetCache();source=synthetic_account()
    operator=source['operators'][1]
    operator['avatar_url']='https://web.hycdn.cn/public/small-avatar.png'
    card=long_document(operator_document(snapshot(source),'佩丽卡',cache),asset_cache=cache)
    portrait_ref=cache.ref_for('endfield','portrait','佩丽卡')
    avatar_ref=cache.register_url(operator['avatar_url'])
    assert card['image']==portrait_ref and card['sections'][0]['image']==avatar_ref
    assert asset_refs(card)=={portrait_ref,avatar_ref}
    marker=BytesIO();Image.new('RGB',(120,120),(12,94,163)).save(marker,format='PNG')
    cache._store(avatar_ref,sanitize_image(marker.getvalue()))
    uses=[];original=EndfieldLayout.avatar
    def capture(self,ref,title,x,y,width,height,**kwargs):
        uses.append((ref,width,height));return original(self,ref,title,x,y,width,height,**kwargs)
    monkeypatch.setattr(EndfieldLayout,'avatar',capture)
    render_card(card,font=cjk_font(),budget_seconds=10,asset_cache=cache)
    assert uses==[(avatar_ref,144,144)]
    marker=BytesIO();Image.new('RGB',(303,386),(163,94,12)).save(marker,format='PNG')
    cache._store(portrait_ref,sanitize_image(marker.getvalue(),portrait=True))
    uses.clear();render_card(card,font=cjk_font(),budget_seconds=10,asset_cache=cache)
    assert uses==[(portrait_ref,304,392)]


def test_honor_image_retains_more_than_ten_medals_within_transport_budget(monkeypatch):
    texts=[];original=EndfieldLayout.text
    def capture(self,value,*args,**kwargs):
        texts.append(value);return original(self,value,*args,**kwargs)
    monkeypatch.setattr(EndfieldLayout,'text',capture)
    card=long_document(honor_document(snapshot(synthetic_honor(12))))
    png=render_card(card,font=cjk_font(),budget_seconds=10)
    image=Image.open(BytesIO(png))
    assert sum(len(section['rows']) for section in card['sections'] if section.get('category')=='ef_medals')==12 and '合成勋章11' in card_to_text(card)
    assert image.width==1080 and image.width*image.height<=16_000_000 and len(png)<=1_048_576
    assert '2026-10-15 09:00' in texts and '2026-10-' not in texts
    with pytest.raises(ValueError,match='pixel_limit'):
        render_card(card,font=cjk_font(),max_pixels=100,budget_seconds=10)
