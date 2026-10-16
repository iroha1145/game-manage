import test from 'node:test'
import assert from 'node:assert/strict'
import { h, nextTick, reactive } from 'vue'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'

const Panel = await loadVue(new URL('./BilibiliSourcePanel.vue', import.meta.url))
test('B站面板不把异常空列表称为历史完成，能查看过滤原因', async (t) => {
  const previous = globalThis.fetch
  globalThis.fetch = async path => ({ok:true,json:async()=>path.endsWith('/audit') ? {rows:[{
    id:'123',title:'版本PV',decision:'excluded',reason_text:'视频或转发视频',body:'9月15日PV',url:'https://t.bilibili.com/123',published_at:'2026-09-15T00:00:00Z',
  }]} : {sources:[{game_id:'nte',uid:'3546636978489848',status:'error',message:'动态列表异常为空',history_complete:false,total:0,accepted:0}],login:{configured:false}}})
  t.after(()=>{globalThis.fetch=previous})
  const root = mount(t, Panel, {})
  await new Promise(resolve=>setImmediate(resolve)); await nextTick()
  assert.match(content(root), /近 60 天待回补/)
  assert.match(content(root), /动态列表异常为空/)
  await nodes(root,'button').find(n=>content(n)==='查看筛选记录').props.onClick()
  await nextTick()
  assert.match(content(root), /暂无符合条件的动态/)
})

const status = () => ({ sources: [{ game_id: 'nte', uid: '1', status: 'ok', message: '', history_complete: true, total: 0, accepted: 0, running: false }], login: { configured: false } })
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
function serve(t, handler) {
  const previous = globalThis.fetch
  globalThis.fetch = handler
  t.after(() => { globalThis.fetch = previous })
}
const collect = root => nodes(root, 'button').find(n => content(n) === '刷新数据').props.onClick()

test('source counts include community articles and explain calendar separation', async t => {
  serve(t, async () => ({ ok: true, json: async () => ({ ...status(), sources: [{ ...status().sources[0], article_count: 2, total: 3, accepted: 0 }] }) }))
  const root = mount(t, Panel, {}); await flush()
  const income = nodes(root, 'div').find(n => nodes(n, 'dt').length === 1 && content(n).startsWith('收入资讯'))
  assert.match(content(income), /2 条/)
  assert.ok(nodes(root, 'button').some(n => n.props['aria-label']?.includes('社区') || n.props.title?.includes('社区')) || content(root).includes('社区'))
})

test('source panel opens all Bilibili login modes and reports configured versus verified', async t => {
  serve(t, async (path, options) => ({ok:true,json:async()=>options?.method==='POST'
    ?{session_id:'FAKE_QR',state:'waiting_scan',qr_image:'data:image/png;base64,FAKE',qr_expires_in:180}
    :{...status(),login:{configured:true,uid:'10001',nickname:'Test',state:'configured'}}}))
  const root=mount(t,Panel,{});await flush()
  await nodes(root,'button').find(n=>content(n).includes('更新 B 站登录')).props.onClick();await flush()
  for(const label of ['扫码登录','账号密码','手机号验证码','Cookie 导入'])assert.match(content(root),new RegExp(label))
  assert.match(content(root), /尚未重新验证/)
  assert.equal(nodes(root,'form').length,0)
})

test('refreshing during a timed status read keeps one polling loop', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let reads = 0, release
  serve(t, async (path, options) => {
    if (options?.method === 'POST') return { ok: true, json: async () => ({ queued: true }) }
    if (++reads === 2) await new Promise(resolve => (release = resolve))
    return { ok: true, json: async () => status() }
  })
  const root = mount(t, Panel, {})
  await flush()
  t.mock.timers.tick(30000); await flush()
  await collect(root)
  release(); await flush()
  const before = reads
  t.mock.timers.tick(30000); await flush()
  assert.equal(reads - before, 1)
})

test('a failed status read stops showing its error once a later read succeeds', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let reads = 0
  serve(t, async () => {
    if (++reads === 2) throw new TypeError('network down')
    return { ok: true, json: async () => status() }
  })
  const root = mount(t, Panel, {})
  await flush()
  t.mock.timers.tick(30000); await flush()
  assert.match(content(root), /无法读取B站来源状态/)
  t.mock.timers.tick(30000); await flush()
  assert.doesNotMatch(content(root), /无法读取B站来源状态/)
})

test('a non-JSON error page is replaced by the fixed failure text', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  serve(t, async (path, options) => options?.method === 'POST'
    ? { ok: false, status: 502, json: async () => { throw new SyntaxError("Unexpected token '<'") } }
    : { ok: true, json: async () => status() })
  const root = mount(t, Panel, {})
  await flush()
  await collect(root); await flush()
  assert.match(content(root), /操作失败，请稍后重试/)
  assert.doesNotMatch(content(root), /Unexpected token/)
})

test('a stopped local service shows Chinese text instead of the raw fetch error', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  serve(t, async (path, options) => {
    if (options?.method === 'POST') throw new TypeError('Failed to fetch')
    return { ok: true, json: async () => status() }
  })
  const root = mount(t, Panel, {})
  await flush()
  await collect(root); await flush()
  assert.match(content(root), /无法连接服务，请稍后重试/)
  assert.doesNotMatch(content(root), /Failed to fetch/)
})

test('an HTTP error keeps the detail the server sent', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  serve(t, async (path, options) => options?.method === 'POST'
    ? { ok: false, status: 409, json: async () => ({ detail: '正在同步中，请稍候' }) }
    : { ok: true, json: async () => status() })
  const root = mount(t, Panel, {})
  await flush()
  await collect(root); await flush()
  assert.match(content(root), /正在同步中，请稍候/)
})

test('a collection that finishes while two reads overlap emits collected once', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let reads = 0, audits = 0, collected = 0, releaseRead, releaseAudit
  serve(t, async (path, options) => {
    if (options?.method === 'POST') return { ok: true, json: async () => ({ queued: true }) }
    if (path.endsWith('/audit')) {
      // The audit triggered by "collected" stays pending so a second read can resolve meanwhile.
      if (++audits >= 2) await new Promise(resolve => (releaseAudit = resolve))
      return { ok: true, json: async () => ({ rows: [] }) }
    }
    reads += 1
    if (reads === 2) await new Promise(resolve => (releaseRead = resolve))
    const data = status()
    data.sources[0].running = reads === 2 || reads === 3
    return { ok: true, json: async () => data }
  })
  const root = mount(t, Panel, { onCollected: () => { collected += 1 } })
  await flush()
  await nodes(root, 'button').find(n => content(n) === '查看筛选记录').props.onClick(); await flush()
  t.mock.timers.tick(30000)
  await collect(root); await flush()
  releaseRead(); await flush()
  t.mock.timers.tick(2500); await flush()
  releaseAudit?.(); await flush()
  assert.equal(collected, 1)
})

test('the source panel defaults to more information and retains every mobile game, Endfield included', async (t) => {
  const previous = globalThis.fetch
  const source = (game_id, uid) => ({ game_id, uid, status: 'ok', message: '', history_complete: true, total: 1, accepted: 1, running: false })
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ sources: [source('wuthering_waves', '1955897084'), source('nte', '3546636978489848'), source('endfield', '1265652806')], login: { configured: false } }) })
  t.after(() => { globalThis.fetch = previous })
  const root = mount(t, Panel, {})
  await new Promise(resolve => setImmediate(resolve)); await nextTick()
  const fold=nodes(root,'details').find(node=>node.props.class==='bili-panel')
  assert.ok(fold)
  assert.ok(!fold.props.open)
  assert.match(content(nodes(fold,'summary')[0]),/更多信息/)
  const text = content(root)
  for (const name of ['鸣潮', '异环', '终末地']) assert.match(text, new RegExp(`${name} · UID`))
  assert.doesNotMatch(text, /endfield · UID/)
})

// App.vue keeps one panel across the overview and the game pages, so a host with a changeable gameId stands in for its route.
const twoGames = () => ({ login: { configured: false }, sources: ['wuthering_waves', 'nte'].map((game_id, index) => (
  { game_id, uid: String(index + 1), status: 'ok', message: '', history_complete: true, total: 1, accepted: 1, running: false })) })
const auditPage = (id, title) => ({ rows: [{ id, title, decision: 'accepted', reason_text: '游戏内通知', body: '', url: `https://t.bilibili.com/${id}`, published_at: '2026-10-01T00:00:00Z' }] })
const answer = body => ({ ok: true, json: async () => body })
function mountOnGame(t, gameId = '') {
  const props = reactive({ gameId })
  return { props, root: mount(t, { setup: () => () => h(Panel, props) }, {}) }
}
const viewAudit = (root, index) => nodes(root, 'button').filter(n => content(n) === '查看筛选记录')[index].props.onClick()
const auditOpen = root => nodes(root, 'div').some(n => n.props.class === 'bili-audit')

test('switching to another game clears the audit list of the previous one', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  serve(t, async path => answer(path.endsWith('/wuthering_waves/audit') ? auditPage('w1', '鸣潮版本公告')
    : path.endsWith('/nte/audit') ? auditPage('n1', '异环测试动态') : twoGames()))
  const { props, root } = mountOnGame(t)
  await flush()
  await viewAudit(root, 0); await flush()
  assert.match(content(root), /鸣潮版本公告/)
  props.gameId = 'nte'; await nextTick()
  assert.equal(auditOpen(root), false)
  assert.doesNotMatch(content(root), /鸣潮版本公告/)
  await viewAudit(root, 0); await flush()
  assert.match(content(root), /异环测试动态/)
  assert.doesNotMatch(content(root), /鸣潮版本公告/)
})

test('moving to the page of the game whose audit list is open keeps that list', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  serve(t, async path => answer(path.endsWith('/audit') ? auditPage('w1', '鸣潮版本公告') : twoGames()))
  const { props, root } = mountOnGame(t)
  await flush()
  await viewAudit(root, 0); await flush()
  props.gameId = 'wuthering_waves'; await nextTick()
  assert.equal(auditOpen(root), true)
  assert.match(content(root), /鸣潮版本公告/)
})

test('an audit answer that arrives after switching games is not shown on the new game', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  let release
  serve(t, async path => {
    if (path.endsWith('/wuthering_waves/audit')) await new Promise(resolve => (release = resolve))
    return answer(path.endsWith('/audit') ? auditPage('w1', '鸣潮版本公告') : twoGames())
  })
  const { props, root } = mountOnGame(t)
  await flush()
  const pending = viewAudit(root, 0)
  props.gameId = 'nte'; await nextTick()
  release(); await pending; await flush()
  assert.equal(auditOpen(root), false)
  assert.doesNotMatch(content(root), /鸣潮版本公告/)
})
