import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { configureHttpClient } from '../http-client.js'
import { nextTick } from 'vue'
const SiteLogin = await loadVue(new URL('./SiteLogin.vue', import.meta.url))
test('site login does not request game credentials or persist secrets', async t => {
  const previousDocument = globalThis.Document, previousShadowRoot = globalThis.ShadowRoot
  globalThis.Document = class {}; globalThis.ShadowRoot = class {}
  t.after(() => { globalThis.Document = previousDocument; globalThis.ShadowRoot = previousShadowRoot })
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options) => { calls.push([url, options]); return new Response(JSON.stringify(url.endsWith('/csrf') ? { csrf_token: 'sample' } : { user_id: 'A' })) })
  let writes = 0; const previous = globalThis.localStorage
  globalThis.localStorage = { setItem() { writes++ } }; t.after(() => { globalThis.localStorage = previous })
  const root = mount(t, SiteLogin)
  assert.match(content(root), /网站登录/); assert.doesNotMatch(content(root), /手机号|森空岛|鹰角/)
  for (const input of nodes(root, 'input')) if (input.props.name === 'username') input.props.onUpdateModelValue?.('alice')
  const inputs = nodes(root, 'input'); inputs.find(x => x.props.name === 'username').props['onUpdate:modelValue']('alice')
  inputs.find(x => x.props.name === 'password').props['onUpdate:modelValue']('sample-password')
  await nodes(root, 'form')[0].props.onSubmit({ preventDefault() {} })
  await nextTick()
  assert.ok(calls.some(x => x[0] === '/api/identity/login')); assert.equal(writes, 0)
})

test('registration explains username rules and rejects invalid input before a request', async t => {
  const previousDocument = globalThis.Document, previousShadowRoot = globalThis.ShadowRoot
  globalThis.Document = class {}; globalThis.ShadowRoot = class {}
  t.after(() => { globalThis.Document = previousDocument; globalThis.ShadowRoot = previousShadowRoot })
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  let calls = 0
  t.mock.method(globalThis, 'fetch', async () => { calls++; throw new Error('unexpected request') })
  const root = mount(t, SiteLogin)
  nodes(root, 'button').find(x => x.props.type === 'button').props.onClick()
  await nextTick()
  assert.match(content(root), /用户名为 3–64 位英文字母、数字、下划线（_）、点（\.）或短横线（-）/)
  const inputs = nodes(root, 'input')
  inputs.find(x => x.props.name === 'username').props['onUpdate:modelValue']('朋友账号')
  inputs.find(x => x.props.name === 'password').props['onUpdate:modelValue']('sample-password')
  inputs.find(x => x.props.name === 'invite').props['onUpdate:modelValue']('sample-invite')
  await nodes(root, 'form')[0].props.onSubmit({ preventDefault() {} })
  await nextTick()
  assert.match(content(root), /用户名需为 3–64 位英文字母、数字、下划线（_）、点（\.）或短横线（-）/)
  assert.equal(calls, 0)
  assert.equal(nodes(root, 'input').find(x => x.props.name === 'password').value, '')
  assert.equal(nodes(root, 'input').find(x => x.props.name === 'invite').value, '')
})
