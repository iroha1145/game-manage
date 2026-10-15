"""Optional isolated Chromium synthetic rich-equipment/scoring acceptance."""
from pathlib import Path
import os
from datetime import datetime,timezone
import pytest
from game_assistant.accounts.models import AccountScope,QueryResult
from game_assistant.adapters.neverness.parse import parse_roles
from game_assistant.assessment import AssessmentModel,Configuration,assess
from game_assistant.qq.browser_rendering import BrowserRenderer
from game_assistant.qq.render_snapshot import role_snapshot


async def test_rich_role_score_shared_browser_png():
    executable,font=os.environ.get('QQ_RENDER_TEST_EXECUTABLE'),os.environ.get('QQ_RENDER_TEST_FONT')
    if not executable or not font:pytest.skip('Explicit isolated Chromium/font required')
    now=datetime.now(timezone.utc)
    roles=parse_roles([{'id':'synthetic','name':'合成验证角色','alev':70,'groupType':'未核验命途原值','awakenEffect':['<b>觉醒效果纯文本</b>'],
        'fork':{'id':'fork_synthetic','name':'合成弧盘','alev':60,'blev':2,'des':'故事纯文本','buffName':'效果名称','buffDes':'效果模板 {1}','lbd':['10','20']},
        'skills':[{'id':'skill_1','name':'战技','type':'来源类型','level':8,'items':[{'title':'说明','desc':'<b>保留说明，安全纯文本</b>'}]}],
        'properties':[{'id':'attack','name':'攻击','value':'1000'},{'id':'unknown'}],
        'suit':{'id':'suit','name':'合成套装','des2':'二件说明','des4':'四件说明','suitCondition':['用户须核对条件'],'suitActivateNum':2,'core':[{'id':'item1','name':'来源 core 装备','lev':15,'mainProperties':[{'id':'m','name':'主项','value':'10%'}],'properties':[{'id':'a','name':'攻击','value':'100'}]}],'pie':[]}}]).model_dump(mode='json')
    model=AssessmentModel.model_validate(dict(game='nte',character_id='synthetic',version='synthetic-v1',source='user_configured',
        nte_profile=dict(character_id='synthetic',version='weights-v1',source='user_configured',substat_weights={'a':'1'},mainstat_weights={}),
        nte_spec=dict(version='nte-custom-weighting-v1',quality_factors={'custom':'1'},eligible_substats=['a'],mainstat_reference_values=[],catalog=[dict(canonical_id='a',label='自定义攻击偏好',kinds=['drive'],main=False,sub=True,unit='flat')])))
    configuration=Configuration.model_validate(dict(game='nte',character_id='synthetic',name='手动测试配置',source='user_configured',items=[dict(id='manual1',nte=dict(kind='drive',quality='custom',area='4',substats_complete=True,substats=[dict(canonical_id='a',observation_id='test1',value='100',unit='flat')]))]))
    roles['entries'][0]['assessment']=assess(configuration,model)
    snapshot=role_snapshot('nte',QueryResult(roles,now.isoformat(),'ok',None),now,resolved_id='synthetic')
    assert snapshot['display_data']['snapshot']['payload']['entries'][0]['assessment']['item_results'][0]['item_id']=='manual1'
    renderer=BrowserRenderer(executable_path=executable,font_path=font)
    envelope=QueryResult({'text':'合成富字段与个人评分验证','render_snapshot':snapshot,'shared_required':True,'scopes':[{'account_id':'synthetic-a','role_id':'synthetic-r','grant_version':1}]},now.isoformat(),'ok',None)
    try:
        png=await renderer.render_summary_async(AccountScope('synthetic-u','synthetic-a','synthetic-r'),envelope,budget_seconds=10)
        assert png.startswith(b'\x89PNG') and renderer.last_state['state']=='ready'
        assert not renderer._browser.contexts
        target=Path('.superpowers/sdd/2026-10-14-game-modules-phase-one/render-evidence/rich-assessment.png')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(png)
    finally:await renderer.aclose()
