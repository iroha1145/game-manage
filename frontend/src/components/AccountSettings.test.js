import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { configureHttpClient } from '../http-client.js'
const AccountSettings = await loadVue(new URL('./AccountSettings.vue', import.meta.url))
test('two endfield authorizations remain separate and full UID absent from shared summary', async t => {
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  const calls = []; t.mock.method(globalThis, 'fetch', async (url, options) => { calls.push([url, options]); return new Response(JSON.stringify(url.endsWith('/csrf') ? { csrf_token: 'sample' } : {})) })
  const root = mount(t, AccountSettings, { accounts: [
    { account_id: 'gacha', provider: 'hypergryph', game: 'endfield', state: 'active', roles: [{ role_id: '1234567890', display_name: '角色甲', is_default: true }] },
    { account_id: 'profile', provider: 'skland', game: 'endfield', state: 'active', roles: [{ role_id: '9876543210', display_name: '角色乙', is_default: true }] },
  ] })
  assert.match(content(root), /鹰角寻访/); assert.match(content(root), /森空岛档案/)
  assert.doesNotMatch(content(root), /1234567890|9876543210|管理员来源配置/)
  const selects = nodes(root, 'select'); await selects[0].props.onChange({ target: { value: '1234567890' } })
  assert.ok(calls.some(x => x[0] === '/api/accounts/gacha/default-role' && x[1].method === 'PUT'))
})

test('unavailable derived Skland credentials and roles have explicit labels and cannot change default roles', async t => {
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => { calls.push([url, options]); return new Response(JSON.stringify(url.endsWith('/csrf') ? { csrf_token: 'fixture' } : {})) })
  const root = mount(t, AccountSettings, { accounts: [
    { account_id: 'missing-credential', provider: 'skland', state: 'credential_unavailable', roles: [{ role_id: 'historical-a', display_name: '历史角色甲', is_default: true }] },
    { account_id: 'missing-role', provider: 'skland', state: 'role_unavailable', authorization_source: 'passport', parent_account_id: 'source', parent_role_id: 'source-role', roles: [] },
  ] })
  const rows = nodes(root, 'article')
  assert.match(content(rows[0]), /授权凭据不可用/)
  assert.match(content(rows[1]), /角色不在当前授权范围/)
  for (const row of rows) {
    const chooser = nodes(row, 'select')[0]
    assert.equal(chooser.props.disabled, true)
    await chooser.props.onChange({ target: { value: 'historical-a' } })
    assert.equal(nodes(row, 'button').find(node => content(node) === '撤销这项游戏授权').props.disabled, false)
  }
  assert.equal(calls.length, 0)
})

test('Skland grants display only safe explicit source metadata without guessing missing provenance', t => {
  const root = mount(t, AccountSettings, { accounts: [
    { account_id: 'source', provider: 'hypergryph', state: 'active', roles: [{ role_id: 'source-role', display_name: '已核验来源角色' }] },
    { account_id: 'derived', provider: 'skland', state: 'active', authorization_source: 'passport', parent_account_id: 'source', parent_role_id: 'source-role', roles: [] },
    { account_id: 'manual', provider: 'skland', state: 'expired', authorization_source: 'manual', roles: [] },
    { account_id: 'unknown', provider: 'skland', state: 'active', roles: [] },
  ] })
  const rows = nodes(root, 'article')
  assert.match(content(rows[1]), /来源：鹰角授权.*已核验来源角色/)
  assert.match(content(rows[2]), /来源：手动凭据/)
  assert.match(content(rows[3]), /来源未提供/)
  assert.doesNotMatch(content(root), /source-role|grant-/)
})
