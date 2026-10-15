import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { Document, ShadowRoot } from 'happy-dom'
import { loadVue, mount, nodes, content, choose } from '../test-utils/vue.js'
import { configureHttpClient } from '../http-client.js'

const CloudApp = await loadVue(new URL('../CloudApp.vue', import.meta.url))
const tick = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const games = ['wuthering_waves', 'nte', 'endfield']
const response = data => new Response(JSON.stringify(data))
const events = name => ({ state: 'ok', fetched_at: '2026-10-13T00:00:00Z', payload: [{ name, category: '官方活动', start_at: null, end_at: null, source_title: `${name}原始公告`, source_url: 'https://example.com/synthetic-calendar', end_precision: 'version_end', end_text: '版本更新维护前' }] })
const button = (root, label) => nodes(root, 'button').find(node => content(node) === label)
async function fixture(t, publicRead, identity = () => 'A') {
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  const calls = []
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    calls.push({ path, method: options.method })
    if (path === '/api/identity/me') return response({ user_id: identity() })
    if (path.endsWith('/csrf')) return response({ csrf_token: 'synthetic-csrf' })
    if (path === '/api/accounts') return response({ accounts: [] })
    if (path.startsWith('/api/public/games/')) return publicRead(path, options)
    if (path === '/api/identity/logout') return response({})
    throw new Error(`Unexpected synthetic request: ${path}`)
  })
  const root = mount(t, CloudApp); await tick(); await tick()
  return { root, calls }
}
async function openCalendar(root) { button(root, '活动日历').props.onClick(); await tick(); await tick() }

test('cloud calendar defaults to all three games with one local filter and retains source/date precision', async t => {
  const { root, calls } = await fixture(t, path => response(events(`${path.split('/')[4]}合成活动`)))
  await openCalendar(root)
  for (const game of games) assert.match(content(root), new RegExp(`${game}合成活动`))
  assert.deepEqual(calls.filter(call => call.path.startsWith('/api/public/')), games.map(game => ({ path: `/api/public/games/${game}/events`, method: 'GET' })))
  assert.equal(nodes(root, 'select').length, 0, 'calendar has only the existing MenuSelect game filter')
  assert.match(content(root), /全部游戏/)
  choose(root, '筛选游戏', 'nte'); await tick()
  assert.match(content(root), /nte合成活动/)
  assert.doesNotMatch(content(root), /wuthering_waves合成活动|endfield合成活动/)
  assert.equal(calls.filter(call => call.path.startsWith('/api/public/')).length, 3)
  nodes(root, 'button').find(node => node.props['aria-label'] === '查看活动详情：nte合成活动').props.onClick(); await tick()
  assert.match(content(root), /nte合成活动原始公告/)
  assert.match(content(root), /版本更新维护前/)
  assert.ok(nodes(root, 'a').some(node => node.props.href === 'https://example.com/synthetic-calendar'))
})

test('calendar filtering during cache reads keeps the selection and does not repeat reads', async t => {
  const finish = []
  const { root, calls } = await fixture(t, path => new Promise(resolve => finish.push(() => resolve(response(events(`${path.split('/')[4]}加载活动`))))))
  await openCalendar(root)
  choose(root, '筛选游戏', 'nte'); await tick()
  const read = button(root, '读取公共活动')
  assert.equal(read.props.disabled, true)
  await read.props.onClick(); await tick()
  assert.equal(calls.filter(call => call.path.startsWith('/api/public/')).length, 3)
  finish.forEach(resolve => resolve()); await tick(); await tick()
  assert.match(content(root), /nte加载活动/)
  assert.doesNotMatch(content(root), /wuthering_waves加载活动|endfield加载活动/)
  assert.equal(button(root, '读取公共活动').props.disabled, false)
})

test('partial calendar read failure retains that game while successful games update independently', async t => {
  let round = 1
  const { root } = await fixture(t, path => {
    const game = path.split('/')[4]
    if (round === 2 && game === 'nte') return new Response('{}', { status: 503 })
    return response(events(`${game}第${round}轮活动`))
  })
  await openCalendar(root); round = 2
  await button(root, '读取公共活动').props.onClick(); await tick()
  assert.match(content(root), /wuthering_waves第2轮活动/)
  assert.match(content(root), /endfield第2轮活动/)
  assert.match(content(root), /nte第1轮活动/)
  assert.match(content(root), /异环 · 游戏数据读取或刷新异常.*保留上次成功快照/)
  choose(root, '筛选游戏', 'endfield'); await tick()
  assert.doesNotMatch(content(root), /游戏数据读取或刷新异常/)
  choose(root, '筛选游戏', 'nte'); await tick()
  round = 3; await button(root, '读取公共活动').props.onClick(); await tick()
  assert.match(content(root), /nte第3轮活动/)
  assert.doesNotMatch(content(root), /游戏数据读取或刷新异常|wuthering_waves第3轮活动/)
})

test('aggregate calendar distinguishes uncollected, collected empty, and first read failure by game', async t => {
  const { root } = await fixture(t, path => path.includes('/nte/') ? response({ state: 'never', payload: null }) : path.includes('/endfield/') ? new Response('{}', { status: 503 }) : response({ state: 'ok', payload: [] }))
  await openCalendar(root)
  assert.match(content(root), /异环 · 尚未采集活动/)
  assert.match(content(root), /终末地 · 游戏数据读取或刷新异常.*尚无可显示的成功快照/)
  choose(root, '筛选游戏', 'wuthering_waves'); await tick()
  assert.match(content(root), /已采集，暂无活动数据/)
  assert.doesNotMatch(content(root), /尚未采集|读取或刷新异常/)
})

test('logout clears calendar cache and ignores late public results in the next authenticated session', async t => {
  const previous = { Document: globalThis.Document, ShadowRoot: globalThis.ShadowRoot }
  Object.assign(globalThis, { Document, ShadowRoot })
  t.after(() => { for (const [name, value] of Object.entries(previous)) { if (value === undefined) delete globalThis[name]; else globalThis[name] = value } })
  let owner = 'A', delayed = false
  const finish = []
  const { root } = await fixture(t, path => delayed ? new Promise(resolve => finish.push(() => resolve(response(events('退出前迟到活动'))))) : response(events(`${owner}会话活动`)), () => owner)
  await openCalendar(root); assert.match(content(root), /A会话活动/)
  delayed = true; const pending = button(root, '读取公共活动').props.onClick(); await tick()
  await button(root, '退出网站').props.onClick(); await tick()
  assert.match(content(root), /网站登录/); assert.doesNotMatch(content(root), /A会话活动/)
  owner = 'B'; delayed = false
  // Re-authenticate through the real login form with synthetic credentials only.
  const inputs = nodes(root, 'input')
  inputs.find(node => node.props.name === 'username').props['onUpdate:modelValue']('synthetic-user')
  inputs.find(node => node.props.name === 'password').props['onUpdate:modelValue']('synthetic-password')
  t.mock.method(globalThis, 'fetch', async path => response(path === '/api/identity/me' || path === '/api/identity/login' ? { user_id: 'B' } : path.endsWith('/csrf') ? { csrf_token: 'synthetic-csrf' } : path === '/api/accounts' ? { accounts: [] } : events('B会话活动')))
  await nodes(root, 'form')[0].props.onSubmit({ preventDefault() {} }); await tick(); await tick()
  await openCalendar(root)
  finish.forEach(resolve => resolve()); await pending; await tick()
  assert.match(content(root), /B会话活动/)
  assert.doesNotMatch(content(root), /A会话活动|退出前迟到活动/)
})

test('changing authenticated user discards cached and delayed calendar state', async t => {
  t.mock.timers.enable({ apis: ['setInterval'] })
  let owner = 'A', delayed = false
  const finish = []
  const { root } = await fixture(t, path => delayed ? new Promise(resolve => finish.push(() => resolve(response(events('换用户前迟到活动'))))) : response(events(`${owner}用户活动`)), () => owner)
  await openCalendar(root); assert.match(content(root), /A用户活动/)
  delayed = true; const pending = button(root, '读取公共活动').props.onClick(); await tick()
  owner = 'B'; delayed = false; t.mock.timers.tick(60000); await tick(); await tick()
  finish.forEach(resolve => resolve()); await pending; await tick()
  assert.doesNotMatch(content(root), /A用户活动|换用户前迟到活动/)
  await button(root, '读取公共活动').props.onClick(); await tick()
  assert.match(content(root), /B用户活动/)
})

test('overview keeps the original local layout without a duplicate public news block', async t => {
  const { root, calls } = await fixture(t, path => response(events('合成活动')))
  assert.doesNotMatch(content(root), /公共资讯与活动|读取资讯/)
  assert.equal(calls.filter(call=>call.path.startsWith('/api/public/')).length,0)
  await openCalendar(root); assert.match(content(root), /全部游戏/)
  assert.deepEqual(calls.filter(call=>call.path.startsWith('/api/public/')).map(call=>call.path),games.map(game=>`/api/public/games/${game}/events`))
})
