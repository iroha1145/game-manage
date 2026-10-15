from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from game_assistant.assessment_routes import install_assessment_routes
from game_assistant.accounts.models import AccountScope
from tests.test_identity import identity, register, write
from tests.test_personal_assessment import config,wuwa_model


class Accounts:
    revoked=False
    def require_scope(self,principal,account,role):
        if self.revoked or account!='owned' or role!='role': raise HTTPException(404,'account_not_found')
        return AccountScope(principal.user_id,account,role)
    def describe(self,scope):
        if self.revoked: raise HTTPException(404,'account_not_found')
        return dict(game='wuthering_waves',version=1)


def test_authorized_model_save_configuration_compare_csrf_and_revocation(identity,tmp_path):
    client=identity[3]; accounts=Accounts()
    store=install_assessment_routes(client.app,accounts,tmp_path/'private')
    path='/api/accounts/owned/roles/role/assessment/wuthering_waves/c1'
    assert client.get(path).status_code==401
    register(identity)
    assert client.put(path+'/model',json=wuwa_model().model_dump(mode='json')).status_code==403
    assert write(client,path+'/model',wuwa_model().model_dump(mode='json'),method='put').status_code==200
    a=write(client,path+'/configurations',config().model_dump(mode='json')).json()['id']
    b=write(client,path+'/configurations',config().model_dump(mode='json')).json()['id']
    assert write(client,path+'/compare',dict(a=a,b=b)).json()['percent_delta']=='0.00'
    assert write(client,path+'/score',dict(id=a)).json()['value']=='20.00'
    assert client.get(path.replace('owned','other')).status_code==404
    assert client.get(path.replace('c1','other')).json()['configurations']==[]
    register(identity,username='bob')
    assert client.get(path).json()['configurations']==[]
    assert write(client,path+'/score',dict(id=a)).status_code==404
    accounts.revoked=True
    assert client.get(path).status_code==404
    assert write(client,path+'/model',wuwa_model().model_dump(mode='json'),method='put').status_code==404
    store.close()


def test_scoped_persistence_reopens_and_refuses_body_identity_and_source(identity,tmp_path):
    client=identity[3]; accounts=Accounts(); store=install_assessment_routes(client.app,accounts,tmp_path/'private')
    register(identity)
    path='/api/accounts/owned/roles/role/assessment/wuthering_waves/c1'
    bad=config().model_dump(mode='json');bad['character_id']='other'
    assert write(client,path+'/configurations',bad).status_code==422
    bad=config().model_dump(mode='json');bad['source']='equipped_snapshot'
    assert write(client,path+'/configurations',bad).status_code==422
    row=write(client,path+'/configurations',config().model_dump(mode='json')).json()
    assert write(client,path+'/score',dict(id=row['id'])).json()['status']=='unconfigured'
    assert write(client,path+'/configurations',{'user_id':'forged',**config().model_dump(mode='json')}).status_code==422
    assert write(client,path+'/configurations/'+row['id'],method='delete').status_code==200
    assert client.get(path).json()['configurations']==[]
    csrf=client.get('/api/identity/csrf').json()['csrf_token']
    assert client.post(path+'/configurations',content=b'{"padding":"'+b'x'*(128*1024)+b'"}',headers={'X-CSRF-Token':csrf}).status_code==413
    store.close()


def test_equipped_normalization_keeps_unknown_and_percentage_units():
    from game_assistant.assessment_equipped import equipped_configuration
    n=equipped_configuration('nte','c1',{'entries':[{'id':'c1','suit':{'core':[{'id':'i','properties':[{'id':'p','value':'3'}]}]}}]})
    assert n.items[0].kind is None and n.items[0].nte is None
    assert n.items[0].source_group=='core' and n.items[0].stats[0].unit is None
    w=equipped_configuration('wuthering_waves','c1',{'role':{'role_id':'c1'},'phantom_data':{'equip_phantom_list':[{'main_props':[{'attribute_name':'攻击','attribute_value':'10%'}],'sub_props':[{'attribute_name':'暴击','attribute_value':'0%'}]}]}})
    assert w.items[0].stats[0].canonical_id=='attack_ratio' and w.items[0].stats[0].value=='10'
    assert w.items[0].stats[1].value=='0' and w.items[0].stats[1].unit=='percent_points'
    repeated=equipped_configuration('nte','c1',{'entries':[{'id':'c1','suit':{'core':[{'id':'same'},{'id':'same'}]}}]})
    assert len({i.id for i in repeated.items})==2 and all(i.source_id=='same' for i in repeated.items)


def test_projection_uses_current_scope_model_and_strips_unrelated_private_data(tmp_path):
    from game_assistant.assessment_store import AssessmentStore
    from game_assistant.assessment_projection import with_assessment
    from game_assistant.accounts.models import QueryResult
    from game_assistant.qq.render_snapshot import role_snapshot
    from datetime import datetime,timezone
    store=AssessmentStore(tmp_path/'score.db'); scope=AccountScope('u','a','r')
    model=wuwa_model({'attack_flat':'0.1'})
    store.save(scope,model,'model')
    snap=QueryResult({'role':{'role_id':'c1','role_name':'synthetic'},'token':'secret',
        'phantom_data':{'equip_phantom_list':[{'main_props':[{'attribute_name':'攻击','attribute_value':'100'}]}]}},'2026-10-14T00:00:00Z','ok',None)
    value=with_assessment(snap,store,scope,'wuthering_waves')
    assert value.payload['assessment']['reason']=='UNKNOWN_STAT_COMPLETENESS'
    other=with_assessment(snap,store,AccountScope('other','a','r'),'wuthering_waves')
    assert other.payload['assessment']['status']=='unconfigured'
    projected=role_snapshot('wuthering_waves',snap,datetime.now(timezone.utc),detail=value,resolved_id='c1')
    assert projected['display_data']['detail']['assessment']['value'] is None
    assert 'token' not in projected['display_data']['detail']
    store.close()
