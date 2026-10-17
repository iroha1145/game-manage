import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'

const tick = async () => {
  await new Promise((resolve) => setImmediate(resolve))
  await nextTick()
}

test('archive backup saves each page compactly, the form the server kept under the 2 MiB import limit', async (t) => {
  const pages = [
    { format: 'game-manage-wuwa-gacha', list: [{ name: '漂泊者', time: '2026-01-01 12:00:00' }], export_page: { next_offset: 1 } },
    { format: 'game-manage-wuwa-gacha', list: [], export_page: { next_offset: null } },
  ]
  const expected = pages.map((page) => JSON.stringify(page))
  const requested = []
  t.mock.method(globalThis, 'fetch', async (url) => {
    requested.push(String(url))
    const page = pages.shift()
    return { ok: true, json: async () => page }
  })
  const saved = []
  t.mock.method(URL, 'createObjectURL', (blob) => { saved.push(blob); return 'blob:backup' })
  t.mock.method(URL, 'revokeObjectURL', () => {})
  const previous = globalThis.document
  globalThis.document = { createElement: () => ({ click() {} }) }
  t.after(() => { globalThis.document = previous })
  const root = mount(t, await loadVue(new URL('./WuwaGachaImport.vue', import.meta.url)), { accountKey: 'account:server' })
  nodes(root, 'button').find((n) => content(n).includes('导出归档')).props.onClick()
  for (let i = 0; i < 5; i++) await tick()
  assert.deepEqual(requested.map((url) => url.replace(/^.*gacha\/export/, 'export')), ['export?limit=2000&offset=0', 'export?limit=2000&offset=1'])
  assert.deepEqual(await Promise.all(saved.map((blob) => blob.text())), expected)
})
