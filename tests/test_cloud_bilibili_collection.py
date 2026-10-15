"""Cloud identity and real scheduler/collector, with synthetic pages only."""
import asyncio
import time

from tests.test_cloud_bilibili_authorization import cloud, login
from tests.test_identity import write

ROOT = '/api/admin/bilibili-source'


def test_admin_collection_boundary_and_safe_status(cloud):
    client, identity, admin, *_ = cloud
    assert client.get(ROOT+'/status').status_code == 401
    invite = identity.create_invite(admin)
    assert write(client, '/api/identity/register', {'username':'reader','password':'Reader-password-123','invite':invite}).status_code == 200
    assert client.get(ROOT+'/status').status_code == 403
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':True}).status_code == 403
    login(client)
    assert client.post(ROOT+'/wuthering_waves/refresh', json={'backfill':True}).status_code == 403
    assert client.get(ROOT+'/status', headers={'Origin':'https://evil.example'}).status_code == 403
    assert client.get(ROOT+'/status', headers={'Host':'evil.example'}).status_code == 403
    assert write(client, ROOT+'/nte/refresh', {'backfill':True}).status_code == 404
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':'true'}).status_code == 422
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':False,'sessdata':'SYNTHETIC'}).status_code == 422
    assert client.get('/api/sources/bilibili').status_code == 404
    assert write(client, '/api/sources/bilibili/wuthering_waves/refresh', {}).status_code == 404
    source = client.app.state.bilibili
    source.store.set_state('wuthering_waves','123',message='SYNTHETIC_SECRET',diagnostic={'raw':'SYNTHETIC_SECRET'})
    result = client.get(ROOT+'/status').json()
    assert result['sources'][0]['queue_state'] == 'idle'
    assert 'SYNTHETIC_SECRET' not in str(result)
    assert 'diagnostic' not in str(result)


def test_manual_collection_shares_public_queue_and_backoff(cloud, monkeypatch):
    client, *_ = cloud
    login(client)
    polling = client.app.state.scheduler
    source = client.app.state.bilibili
    source.settings.bilibili_history_days = 7
    calls = []
    async def collect(fetch, uid, now, **options):
        calls.append((options['days'],options['mode']))
        options['on_page']([], 2)
        return {'cutoff':now.isoformat()}
    monkeypatch.setattr('game_assistant.sources.bilibili_service.collect_pages', collect)
    async def start_and_block():
        polling.start(periodic=False)
        for _ in range(polling.settings.cloud_poll_concurrency):
            await polling._global.acquire()
    client.portal.call(start_and_block)
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':True}).json()['state'] == 'queued'
    assert client.get(ROOT+'/status').json()['sources'][0]['queue_state'] == 'queued'
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':False}).status_code == 409
    # A periodic tick uses the same key and cannot add another public job.
    client.portal.call(polling.tick)
    assert len(polling._pending) == 1
    client.portal.call(polling._global.release)
    client.portal.call(polling.drain)
    assert calls == [(60,'backfill')]
    assert polling._due.get(('public','wuthering_waves'), 0) == 0
    result = client.get(ROOT+'/status').json()['sources'][0]
    assert result['queue_state'] == 'cooldown' and result['status'] == 'ok'
    assert result['history_complete'] and result['pages'] == 2
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':True}).json()['detail'] == 'source_backoff'
    source.store.set_state('wuthering_waves','123',next_retry=0)
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':False}).status_code == 200
    client.portal.call(polling.drain)
    assert calls[-1][1] == 'incremental'
    source.store.set_state('wuthering_waves','123',next_retry=0,history_complete=False)
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':False}).status_code == 200
    client.portal.call(polling.drain)
    assert calls[-1] == (7,'backfill')


def test_running_backfill_is_busy_and_rechecks_retry_after_queue(cloud, monkeypatch):
    client, *_ = cloud
    login(client)
    polling = client.app.state.scheduler
    source = client.app.state.bilibili
    gate = client.portal.call(asyncio.Event)
    entered = client.portal.call(asyncio.Event)
    async def collect(fetch, uid, now, **options):
        entered.set()
        await gate.wait()
        return {'cutoff':now.isoformat()}
    monkeypatch.setattr('game_assistant.sources.bilibili_service.collect_pages', collect)
    client.portal.call(lambda: polling.start(periodic=False))
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':False}).status_code == 200
    client.portal.call(entered.wait)
    assert client.get(ROOT+'/status').json()['sources'][0]['queue_state'] == 'running'
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':True}).json()['detail'] == 'source_busy'
    assert any(not task.done() for task in source.tasks.values())
    client.portal.call(gate.set)
    client.portal.call(polling.drain)
    source.store.set_state('wuthering_waves','123',next_retry=0)
    async def block():
        for _ in range(polling.settings.cloud_poll_concurrency):
            await polling._global.acquire()
    client.portal.call(block)
    assert write(client, ROOT+'/wuthering_waves/refresh', {'backfill':True}).status_code == 200
    source.store.set_state('wuthering_waves','123',next_retry=time.time()+3600)
    client.portal.call(polling._global.release)
    client.portal.call(polling.drain)
    assert client.get(ROOT+'/status').json()['sources'][0]['queue_state'] == 'cooldown'


def test_failure_keeps_old_rows_and_only_exposes_safe_codes(cloud, monkeypatch):
    from datetime import datetime, timezone
    from game_assistant.sources.bilibili import SourceError
    client, *_ = cloud
    login(client)
    source = client.app.state.bilibili
    now = datetime.now(timezone.utc).isoformat()
    old = {'id':'old','published_at':now,'decision':'excluded','reason':'fixture','reason_text':'fixture','body':'old successful content'}
    source.store.save_rows('wuthering_waves','123',[old])
    source.store.set_state('wuthering_waves','123',last_success=now,history_complete=False)
    async def failed(fetch, uid, now, **options):
        options['on_diagnostic']({'http_status':412,'business_code':-352})
        raise SourceError('SYNTHETIC_SECRET',http_status=412)
    monkeypatch.setattr('game_assistant.sources.bilibili_service.collect_pages',failed)
    client.portal.call(lambda:client.app.state.scheduler.start(periodic=False))
    assert write(client,ROOT+'/wuthering_waves/refresh',{'backfill':True}).status_code == 200
    client.portal.call(client.app.state.scheduler.drain)
    assert source.store.rows('wuthering_waves','123') == [old]
    source.store.set_state('wuthering_waves','123',diagnostic={'http_status':412,'business_code':-352,'raw':'SYNTHETIC_SECRET'})
    result = client.get(ROOT+'/status').json()['sources'][0]
    assert result['status'] == 'error' and result['queue_state'] == 'backoff'
    assert result['last_success'] == now and not result['history_complete']
    assert result['http_status'] == 412 and result['business_code'] == -352
    assert 'SYNTHETIC_SECRET' not in str(result)


def test_different_game_manual_jobs_use_existing_global_limit(cloud, monkeypatch):
    client, *_ = cloud
    login(client)
    polling = client.app.state.scheduler
    polling.public.bilibili.sources['nte'] = '456'
    polling.settings.cloud_provider_concurrency = 4
    polling._global = client.portal.call(lambda:asyncio.Semaphore(1))
    gate = client.portal.call(asyncio.Event)
    entered = client.portal.call(asyncio.Event)
    active = maximum = calls = 0
    async def collect(fetch,uid,now,**options):
        nonlocal active, maximum, calls
        calls += 1
        active += 1
        maximum = max(maximum,active)
        entered.set()
        await gate.wait()
        active -= 1
        return {'cutoff':now.isoformat()}
    monkeypatch.setattr('game_assistant.sources.bilibili_service.collect_pages',collect)
    client.portal.call(lambda:polling.start(periodic=False))
    assert write(client,ROOT+'/wuthering_waves/refresh',{'backfill':True}).status_code == 200
    client.portal.call(entered.wait)
    assert write(client,ROOT+'/nte/refresh',{'backfill':True}).status_code == 200
    states = {s['game_id']:s['queue_state'] for s in client.get(ROOT+'/status').json()['sources']}
    assert states == {'wuthering_waves':'running','nte':'queued'}
    client.portal.call(gate.set)
    client.portal.call(polling.drain)
    assert maximum == 1 and calls == 2
