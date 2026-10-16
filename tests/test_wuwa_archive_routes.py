from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from game_assistant.snapshots import SnapshotStore
from game_assistant.wuwa_archive_routes import install_wuwa_archive_routes
from tests.test_wuwa_routes import Auth
from tests.test_wuwa_gacha import record


def make_client(tmp_path):
    app = FastAPI()
    adapter = SimpleNamespace(credentials_configured=True, _settings=SimpleNamespace(
        wuwa_user_id='community', wuwa_role_id='100', wuwa_server_id='S'))
    app.state.registry = SimpleNamespace(get=lambda _: adapter)
    app.state.auth = Auth()
    app.state.store = SnapshotStore(str(tmp_path / 'db'))
    app.state.settings = SimpleNamespace(auth_allowed_origins=['http://testserver'])
    install_wuwa_archive_routes(app)
    from game_assistant.api_security import install_api_security
    install_api_security(app, app.state.settings)
    return TestClient(app), app, adapter


def test_private_reads_empty_backfill_no_network_and_logout(tmp_path, monkeypatch):
    client, app, adapter = make_client(tmp_path)
    from game_assistant import wuwa_archive_routes as routes
    async def forbidden(*a, **kw):
        raise AssertionError('only explicit import may request gacha')
    monkeypatch.setattr(routes, 'fetch_official', forbidden)
    assert client.get('/api/wuwa/gacha').json()['state'] == 'need_import'
    assert client.get('/api/wuwa/history?kind=tower').json()['items'] == []
    result = client.post('/api/wuwa/history/backfill', json={}, headers={'X-Game-Assistant': '1'})
    assert result.json()['inserted'] == 0
    assert result.json()['complete'] is False
    assert client.get('/api/wuwa/history?kind=other').status_code == 422
    adapter.credentials_configured = False
    for path in ['/api/wuwa/gacha', '/api/wuwa/history?kind=roles']:
        assert client.get(path).status_code == 401


def test_write_guard_body_limit_identity_and_secret_errors(tmp_path):
    client, app, adapter = make_client(tmp_path)
    path = '/api/wuwa/gacha/preview'
    body = {'records': {'info': {'uid': '100'}, 'list': [record()]}}
    assert client.post(path, json=body).status_code == 403
    headers = {'X-Game-Assistant': '1', 'Origin': 'https://evil.test'}
    assert client.post(path, json=body, headers=headers).status_code == 403
    headers['Origin'] = 'http://testserver'
    preview=client.post(path,json=body,headers=headers).json()
    assert client.get('/api/wuwa/gacha').json()['total']==0
    assert client.post('/api/wuwa/gacha/import',json={'preview_id':preview['preview_id']},headers=headers).json()['inserted']==1
    assert client.get('/api/wuwa/gacha').json()['total'] == 1
    response = client.post(path, content=b'x' * (2 * 1024 * 1024 + 1), headers=headers)
    assert response.status_code == 413
    response = client.post(path, content=b'x' * (2 * 1024 * 1024 + 1),
                           headers={**headers, 'Content-Length': '1'})
    assert response.status_code == 413
    response = client.post(path, json={'url': 'https://evil.test/SECRET'}, headers=headers)
    assert response.status_code == 422 and 'SECRET' not in response.text
    response = client.post(path, json={'url': ['SECRET']}, headers=headers)
    assert response.status_code == 422 and 'SECRET' not in response.text
    body['records']['info']['uid'] = '101'
    assert client.post(path, json=body, headers=headers).status_code == 422
    adapter._settings.wuwa_role_id = '101'
    assert client.get('/api/wuwa/gacha').json()['total'] == 0
    assert client.get('/api/wuwa/gacha').headers['cache-control'] == 'no-store'
    assert client.get('/api/wuwa/gacha?limit=501').status_code == 422


def test_import_session_switch_discards_inflight_rows(tmp_path, monkeypatch):
    client, app, adapter = make_client(tmp_path)
    from game_assistant import wuwa_archive_routes as routes
    async def switched(*a):
        app.state.auth.generation += 1
        return {'records': {'info': {'uid': '100'}, 'list': [record()]}, 'failed_pools': []}
    monkeypatch.setattr(routes, 'fetch_official', switched)
    response = client.post('/api/wuwa/gacha/preview', json={'url': 'transient'}, headers={'X-Game-Assistant': '1'})
    assert response.status_code == 409
    assert client.get('/api/wuwa/gacha').json()['total'] == 0


def test_url_preview_does_not_write_and_direct_http_import_is_rejected(tmp_path,monkeypatch):
    client,_,_=make_client(tmp_path)
    from game_assistant import wuwa_archive_routes as routes
    async def official(*args):
        return {'records':{'info':{'uid':'100'},'list':[record()]},'failed_pools':['2']}
    monkeypatch.setattr(routes,'fetch_official',official)
    headers={'X-Game-Assistant':'1'}
    p=client.post('/api/wuwa/gacha/preview',json={'url':'TRANSIENT_SECRET'},headers=headers)
    assert p.status_code==200 and 'TRANSIENT_SECRET' not in p.text
    assert client.get('/api/wuwa/gacha').json()['total']==0
    for body in ({'url':'TRANSIENT_SECRET'},{'records':{'info':{'uid':'100'},'list':[record()]}}):
        assert client.post('/api/wuwa/gacha/import',json=body,headers=headers).status_code==422
    result=client.post('/api/wuwa/gacha/import',json={'preview_id':p.json()['preview_id']},headers=headers)
    assert result.status_code==200 and result.json()['inserted']==1


def test_actual_role_detail_read_archives_only_success(tmp_path):
    from game_assistant.adapters.wuthering_waves.routes import install_wuwa_routes
    from game_assistant.models import FetchResult
    client, app, adapter = make_client(tmp_path)
    async def detail(character):
        return FetchResult(ok=True, payload={'role_id': '100', 'server_id': 'S',
            'character_id': character, 'data': {'level': 0}, 'provenance': {'fetched_at': 'source-time'}})
    adapter.fetch_role_detail = detail
    install_wuwa_routes(app)
    assert client.get('/api/wuwa/roles/1501').status_code == 200
    rows = client.get('/api/wuwa/history?kind=role_detail').json()['items']
    assert len(rows) == 1 and rows[0]['source_at'] == 'source-time'
    async def failed(character):
        return FetchResult(ok=False, error='source failure')
    adapter.fetch_role_detail = failed
    assert client.get('/api/wuwa/roles/1501').status_code == 502
    assert len(client.get('/api/wuwa/history?kind=role_detail').json()['items']) == 1
def test_preview_commit_replay_rule_and_export(tmp_path):
    client,app,adapter=make_client(tmp_path)
    headers={'X-Game-Assistant':'1'}
    document={'info':{'uid':'100','server_id':'S'},'list':[record(id='one')]}
    preview=client.post('/api/wuwa/gacha/preview',json={'records':document},headers=headers)
    assert preview.status_code==200
    assert client.get('/api/wuwa/gacha').json()['total']==0
    token=preview.json()['preview_id']
    assert client.post('/api/wuwa/gacha/import',json={'preview_id':token},headers=headers).json()['inserted']==1
    assert client.post('/api/wuwa/gacha/import',json={'preview_id':token},headers=headers).status_code==409
    rule=dict(pool='1',hard_pity=80,reset_rarity='5',version='personal',sharing='independent',basis='user_configured')
    assert client.post('/api/wuwa/gacha/rules',json=rule,headers=headers).status_code==200
    assert client.get('/api/wuwa/gacha/export').json()['rules']==[rule]
    token=client.post('/api/wuwa/gacha/preview',json={'records':document},headers=headers).json()['preview_id']
    app.state.auth.generation+=1
    assert client.post('/api/wuwa/gacha/import',json={'preview_id':token},headers=headers).status_code==409
    assert client.post('/api/wuwa/gacha/preview',json={'records':document},headers={'X-Game-Assistant':'1','Origin':'https://evil.test'}).status_code==403


def test_preview_aggregate_source_selection_and_invalid_body(tmp_path):
    client,_,_=make_client(tmp_path)
    headers={'X-Game-Assistant':'1'}
    payload={'data':{'uid':'100','card_analysis_json':{'pool':{'five_cards':[
        dict(cardPoolType=99,name='未知五星',time='2026-01-01',draw_total=90)]}}}}
    preview=client.post('/api/wuwa/gacha/preview',json={'source':'mcgf','records':payload},headers=headers)
    assert preview.status_code==200
    assert client.post('/api/wuwa/gacha/import',json={'preview_id':preview.json()['preview_id']},headers=headers).status_code==200
    archive=client.get('/api/wuwa/gacha').json()
    assert archive['total']==0 and archive['aggregates']['total']==1
    assert client.post('/api/wuwa/gacha/preview',content=b'x'*(2*1024*1024+1),headers=headers).status_code==413
    assert client.post('/api/wuwa/gacha/preview',json={'source':'xhh','records':payload},headers=headers).status_code==422


def test_deeply_nested_json_is_rejected_not_a_server_error(tmp_path):
    client, _, _ = make_client(tmp_path)
    client = TestClient(client.app, raise_server_exceptions=False)
    nested = ('[' * 100000 + ']' * 100000).encode()
    headers = {'X-Game-Assistant': '1', 'Content-Type': 'application/json'}
    for path in ('/api/wuwa/gacha/import', '/api/wuwa/history/backfill'):
        response = client.post(path, content=nested, headers=headers)
        assert response.status_code == 422, (path, response.status_code)
