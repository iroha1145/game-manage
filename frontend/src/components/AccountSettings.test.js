import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { configureHttpClient } from '../http-client.js'
const AccountSettings = await loadVue(new URL('./AccountSettings.vue', import.meta.url))
test('two endfield authorizations remain separate and full UID absent from shared summary', async t => {
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  const calls = []; t.mock.method(globalThis, 'fetch', async (url, options) => { calls.push([url, options]); return new Response(JSON.stringify(url.endsWith('/csrf') ? { csrf_token: 'sample' } : {})) })
  const root = mount(t, AccountSettings, { accounts: [
    { account_id: 'gacha', provider: 'hypergryph', game: 'endfield', state: 'connected', roles: [{ role_id: '1234567890', display_name: '角色甲', is_default: true }] },
    { account_id: 'profile', provider: 'skland', game: 'endfield', state: 'connected', roles: [{ role_id: '9876543210', display_name: '角色乙', is_default: true }] },
  ] })
  assert.match(content(root), /鹰角寻访/); assert.match(content(root), /森空岛档案/)
  assert.doesNotMatch(content(root), /1234567890|9876543210|管理员来源配置/)
  const selects = nodes(root, 'select'); await selects[0].props.onChange({ target: { value: '1234567890' } })
  assert.ok(calls.some(x => x[0] === '/api/accounts/gacha/default-role' && x[1].method === 'PUT'))
})
