import json
from pathlib import Path

import pytest

from game_assistant.character_search import search_characters, resolve_character, catalog_entries
from game_assistant.qq import presentation as view
from game_assistant.accounts.models import QueryResult
from tests.test_qq_unified_queries import CachedQuery, IDENTITY, service

CASES = json.loads((Path(__file__).parent / 'fixtures/character_search.json').read_text(encoding='utf-8'))

@pytest.mark.parametrize('case', CASES)
def test_shared_queries(case):
    found = search_characters(case['game'], case['query'])
    assert [item['character_id'] for item in found] == case['ids']
    assert all(item['match'] == case['match'] for item in found)

def test_scoped_forms_and_new_roles_never_borrow_another_identity():
    owned = [{'role_id':'1408','name':'漂泊者','attribute':'气动'}, {'role_id':'unknown','name':'漂泊者','attribute':'湮灭'}]
    assert resolve_character('wuthering_waves', '漂泊者', owned)['status'] == 'ambiguous'
    assert resolve_character('wuthering_waves', '漂泊者·湮灭', owned)['entry'] is owned[1]
    assert resolve_character('wuthering_waves', '风主', owned)['entry'] is owned[0]
    assert search_characters('nte', 'new hero', [{'id':'new','name':'New Hero'}])[0]['character_id'] == 'new'
    assert not search_characters('nte', 'BH', [{'id':'new','name':'薄荷'}])
    nte=[{'id':'nte-new','name':'同名'}]
    wuwa=[{'role_id':'wuwa-new','name':'同名'}]
    assert resolve_character('nte','同名',nte)['entry'] is nte[0]
    assert resolve_character('wuthering_waves','同名',wuwa)['entry'] is wuwa[0]

def test_qq_suggestions_only_expose_authorized_cache_and_do_not_select():
    snap = QueryResult({'entries':[{'id':'1010','name':'娜娜莉'}]}, None, 'ok', None)
    card = view.role_card('nte', 'tajiduo', snap, '娜娜利')
    assert card['kind'] != 'detail'
    assert '娜娜莉' in str(card) and '候选' in str(card)
    assert '哈尼娅' not in str(view.role_card('nte', 'tajiduo', snap, '哈妮娅'))

def test_qq_alias_resolves_detail_once_by_stable_id_in_authorized_scope(monkeypatch):
    query = CachedQuery()
    scope = query.add('wuthering_waves', 'kuro', 'ww', {'roles':[{'role_id':'1205','name':'长离'}]})
    api = service(query)
    calls = []
    monkeypatch.setattr(api, '_role_detail_snapshot', lambda actual, character: calls.append((actual, character)))
    context = {}
    api.query(IDENTITY, 'roles', 'wuthering_waves', role_name='CL', image_context=context)
    assert calls == [(scope, '1205')]
    assert context['card']['kind'] == 'detail' and '长离' in context['card']['title']
    calls.clear()
    api.query(IDENTITY, 'roles', 'wuthering_waves', role_name='chang')
    assert calls == []
