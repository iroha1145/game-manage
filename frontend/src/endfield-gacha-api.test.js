import test from 'node:test'
import assert from 'node:assert/strict'
import { getRecords } from './endfield-gacha-api.js'
function serve(t, handler) {
  const old = globalThis.fetch; t.after(() => { globalThis.fetch = old })
  globalThis.fetch = handler
}
test('an unreachable local service gives a Chinese message instead of the raw fetch error', async t => {
  serve(t, async () => { throw new TypeError('Failed to fetch') })
  await assert.rejects(getRecords(), error => error.message === '无法连接服务，请稍后重试')
})
test('an abort reaches the caller unchanged', async t => {
  const aborted = Object.assign(new Error('The operation was aborted.'), { name: 'AbortError' })
  serve(t, async () => { throw aborted })
  await assert.rejects(getRecords(), error => error === aborted)
})
test('server errors keep their own message and a non-JSON page is replaced by fixed text', async t => {
  serve(t, async () => new Response(JSON.stringify({ detail: '没有可用的寻访记录' }), { status: 409 }))
  await assert.rejects(getRecords(), /没有可用的寻访记录/)
  globalThis.fetch = async () => new Response('<html>Bad Gateway</html>', { status: 502 })
  await assert.rejects(getRecords(), error => error.message === '寻访账本服务返回异常，请稍后重试')
})
