import test from 'node:test'
import assert from 'node:assert/strict'
import { configureHttpClient } from './http-client.js'
import { getCloudBilibiliStatus, startCloudBilibiliQr, refreshCloudBilibiliSource } from './cloud-bilibili-api.js'

const json = (value, status = 200) => new Response(JSON.stringify(value), { status })
const csrf = path => path.endsWith('/csrf') ? json({ csrf_token: 'fixture' }) : null
const cloud = t => { configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' })) }

test('a machine code from the cloud service becomes fixed text and stays readable on error.detail', async t => {
  cloud(t)
  t.mock.method(globalThis, 'fetch', async path => csrf(path) || json({ detail: 'csrf_required' }, 403))
  const failure = await startCloudBilibiliQr().catch(error => error)
  assert.equal(failure.message, 'B站授权暂不可用，请稍后重试')
  assert.equal(failure.detail, 'csrf_required'); assert.equal(failure.status, 403)
  t.mock.method(globalThis, 'fetch', async path => csrf(path) || json({ detail: 'source_busy' }, 409))
  const busy = await refreshCloudBilibiliSource('nte', false).catch(error => error)
  assert.equal(busy.detail, 'source_busy'); assert.equal(busy.message, 'B站授权暂不可用，请稍后重试')
})

test('Chinese text from the service is kept with its state and error code', async t => {
  cloud(t)
  t.mock.method(globalThis, 'fetch', async () => json({ detail: 'B站要求额外安全验证，请自行在官方登录页完成后重新登录', error_code: 'SECURITY_VERIFICATION_REQUIRED', state: 'blocked' }, 403))
  const failure = await getCloudBilibiliStatus().catch(error => error)
  assert.equal(failure.message, 'B站要求额外安全验证，请自行在官方登录页完成后重新登录')
  assert.equal(failure.errorCode, 'SECURITY_VERIFICATION_REQUIRED'); assert.equal(failure.state, 'blocked')
})

test('the request limit gives a Chinese message while a caller abort stays an abort', async t => {
  cloud(t)
  // AbortSignal.timeout's timer does not hold Node 22's event loop open, so the test fires the limit itself.
  let limit, reached
  t.mock.method(AbortSignal, 'timeout', () => (limit = new AbortController()).signal)
  t.mock.method(globalThis, 'fetch', (path, options) => csrf(path) || new Promise((_, reject) => {
    if (options.signal.aborted) return reject(options.signal.reason)
    options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true })
    reached()
  }))
  const fetched = () => new Promise(resolve => { reached = resolve })
  let started = fetched()
  const timedOut = startCloudBilibiliQr().catch(error => error)
  await started; limit.abort(new DOMException('signal timed out', 'TimeoutError'))
  assert.equal((await timedOut).message, '请求超时，请检查会话状态后重试')
  started = fetched()
  const caller = new AbortController(), pending = startCloudBilibiliQr(caller.signal).catch(error => error)
  await started; caller.abort()
  assert.equal((await pending).name, 'AbortError')
})

test('a malformed account status cannot be presented as unconfigured', async t => {
  cloud(t)
  t.mock.method(globalThis,'fetch',async()=>json({state:'configured'}))
  await assert.rejects(getCloudBilibiliStatus(),/无法确认是否已配置/)
})
