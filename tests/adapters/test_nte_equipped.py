import pytest
from game_assistant.adapters.neverness.parse import parse_roles


def test_rich_equipped_preserves_identity_unknowns_and_plain_text():
    role = parse_roles([{'id':'c1','properties':[{'id':'attack','value':'100'},{'id':'unknown'}],
        'groupType':'unmapped','awakenEffect':['<b>effect</b>'],
        'skills':[{'id':'s1','type':'COMBAT','items':[{'title':'<b>title</b>','desc':'<script>x()</script>safe'}]}],
        'fork':{'name':'fork without id','blev':2,'buffDes':'<i>{value}</i>','lbd':[1,2]},
        'suit':{'id':'set1','des2':'<b>set effect</b>','suitActivateNum':0,'suitCondition':[2,4],
                'core':[{'id':'i1','lev':0,'mainProperties':[{'id':'m1'}],'properties':[{'id':'p1'}]}]}}]).entries[0]
    assert role.properties[1].id == 'unknown' and role.properties[1].value is None
    assert role.group_type == 'unmapped' and role.awaken_effects == ['effect']
    assert role.skills[0].id == 's1' and role.skills[0].items[0].desc == 'safe'
    assert role.weapon.id is None and role.weapon.breakthrough_level == 2
    assert role.weapon.buff_description == '{value}' and role.weapon.lbd == [1,2]
    assert role.suit.id == 'set1' and role.suit.activation_count == 0
    assert role.suit.core[0].id == 'i1' and role.suit.core[0].level == 0
    assert role.suit.core[0].quality is None and role.suit.core[0].area is None
    assert role.suit.core[0].substats_complete is None
    assert role.properties[0].value == '100'


def test_missing_equipment_stays_unknown_and_bad_collections_rejected():
    role = parse_roles([{'id':'c1'}]).entries[0]
    assert role.suit is None and role.weapon is None and role.group_type is None
    for field,value in [('suit',{'core':{}}),('awakenEffect',{}),('skills',[{'items':{}}])]:
        with pytest.raises(ValueError):
            parse_roles([{'id':'c1',field:value}])
