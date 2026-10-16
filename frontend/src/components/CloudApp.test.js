import test from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { nextTick } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { configureHttpClient } from '../http-client.js'
const CloudApp = await loadVue(new URL('../CloudApp.vue', import.meta.url))
const tick = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
test('public Bilibili authorization entry is visible only for the website administrator', async t => {
  for (const is_admin of [false,true]) {
    await t.test(String(is_admin), async sub => {
      configureHttpClient({mode:'cloud'});sub.after(()=>configureHttpClient({mode:'local'}))
      sub.mock.method(globalThis,'fetch',async path=> {
        const data=path==='/api/identity/me'?{user_id:'fixture',is_admin}:path==='/api/accounts'?{accounts:[]}:path==='/api/identity/sessions'?{sessions:[]}:path.endsWith('/csrf')?{csrf_token:'fixture'}:path.endsWith('/status')?{configured:false}:{state:'never',payload:null}
        return new Response(JSON.stringify(data))
      })
      const root=mount(sub,CloudApp);await tick();await tick()
      nodes(root,'button').find(n=>content(n)==='账号与授权').props.onClick();await tick()
      assert.equal(content(root).includes('管理员 · B 站公共源授权'),is_admin)
      assert.equal(content(root).includes('管理员 · QQ 群设置'),is_admin)
    })
  }
})
test('minute session check defers during an accepted refresh and resumes after short tracking settles', async t => {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval'] })
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  let identityReads = 0, posts = 0, reads = 0
  t.mock.method(globalThis, 'fetch', async path => {
    let data
    if (path === '/api/identity/me') { identityReads++; data = { user_id: 'A' } }
    else if (path.endsWith('/csrf')) data = { csrf_token: 'fixture' }
    else if (path === '/api/accounts') data = { accounts: [{ account_id: 'a', provider: 'hypergryph', state: 'active', capabilities: ['account'], roles: [{ role_id: 'r', is_default: true }] }] }
    else if (path.endsWith('/refresh/account')) { posts++; data = { state: 'queued' } }
    else if (path.endsWith('/snapshot/account')) { reads++; data = { account_id:'a',role_id:'r',state: 'ok', payload: { role_id:'r',nickname: reads > 3 ? '定时交互新快照' : '定时交互旧快照' }, poll_status: { refresh_state: posts && reads === 3 ? 'queued' : 'idle' } } }
    else data = { state: 'never', payload: null }
    return new Response(JSON.stringify(data))
  })
  const root = mount(t, CloudApp); await tick(); await tick()
  nodes(root,'button').find(n=>content(n).includes('授权 1')).props.onClick(); await tick(); await tick()
  t.mock.timers.tick(59000); await tick()
  await nodes(root, 'button').find(n => content(n) === '刷新数据').props.onClick(); await tick()
  t.mock.timers.tick(1000); await tick(); await tick()
  assert.equal(identityReads, 1, 'minute check must not invalidate active short tracking')
  assert.match(content(root), /刷新已排队/)
  t.mock.timers.tick(2000); await tick()
  assert.match(content(root), /定时交互新快照/); assert.doesNotMatch(content(root), /刷新已排队|刷新状态待确认/)
  assert.equal(reads, 4); assert.equal(posts, 1)
  t.mock.timers.tick(58000); await tick(); await tick()
  assert.equal(identityReads, 2, 'normal session checks resume on the next minute')
  assert.equal(reads, 5)
})
test('refresh UI converges without the minute timer and public never state is explicit', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] })
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  let posts = 0, reads = 0
  t.mock.method(globalThis, 'fetch', async path => {
    let data
    if (path === '/api/identity/me') data = { user_id: 'A' }
    else if (path.endsWith('/csrf')) data = { csrf_token: 'fixture' }
    else if (path === '/api/accounts') data = { accounts: [{ account_id: 'a', provider: 'hypergryph', state: 'active', capabilities: ['account'], roles: [{ role_id: 'r', is_default: true }] }] }
    else if (path.endsWith('/refresh/account')) { posts++; data = { state: 'queued' } }
    else if (path.endsWith('/snapshot/account')) { reads++; data = { account_id:'a',role_id:'r',state: 'ok', payload: { role_id:'r',nickname: reads > 3 ? '新快照' : '旧快照' }, poll_status: { refresh_state: posts && reads === 3 ? 'queued' : 'idle' } } }
    else data = { state: 'never', payload: null }
    return new Response(JSON.stringify(data))
  })
  const root = mount(t, CloudApp); await tick(); await tick()
  nodes(root,'button').find(n=>content(n).includes('授权 1')).props.onClick(); await tick(); await tick()
  const refresh = nodes(root, 'button').find(n => content(n) === '刷新数据')
  await refresh.props.onClick(); await tick(); assert.equal(refresh.props.disabled, true)
  t.mock.timers.tick(0); await tick(); assert.match(content(root), /刷新已排队/)
  t.mock.timers.tick(2000); await tick(); assert.equal(refresh.props.disabled, false)
  assert.doesNotMatch(content(root), /刷新已排队|正在读取状态/)
  assert.match(content(root), /新快照/); assert.equal(posts, 1); assert.equal(reads, 4)
  nodes(root,'button').find(n=>content(n)==='公告与资讯').props.onClick();await tick()
  assert.match(content(root), /尚未采集公告与资讯/); assert.doesNotMatch(content(root), /暂无公告与资讯/)
})
for (const [width, user] of [[390, 'A'], [1440, 'B']]) {
  test(`cloud mock DOM ${width}px user ${user} isolates navigation and revoked session clears all private views`, async t => {
    const browser = new Window({ width, height: 900 }), originalWindow = globalThis.window
    globalThis.window = browser; t.after(() => { globalThis.window = originalWindow; browser.happyDOM.abort() })
    configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
    const paths = []
    t.mock.method(globalThis, 'fetch', async (path) => {
      paths.push(path)
      if (path === '/api/identity/sessions') return new Response('{}', { status:401 })
      const data = path === '/api/identity/me' ? { user_id: user, is_admin:false } : path.endsWith('/csrf') ? { csrf_token:'fixture-csrf' } : { accounts:[{account_id:`account-${user}`,provider:'kuro',game:'wuthering_waves',state:'active',roles:[{role_id:`role-${user}`,display_name:`私人角色${user}`,is_default:true}]}] }
      return new Response(JSON.stringify(data))
    })
    const root = mount(t, CloudApp); await tick(); await tick()
    assert.match(content(root), new RegExp(`私人角色${user}`))
    nodes(root,'button').find(n=>content(n).includes('授权 1')).props.onClick(); await tick(); await tick()
    assert.match(content(root), /尚未提供云端数据能力/)
    assert.equal(nodes(root,'nav').find(n => n.props['aria-label'] === '云端导航')?.children.filter(n => n.type === 'button').length,4)
    assert.doesNotMatch(content(root), /英雄联盟|LCU|管理员来源配置|本地工作台/)
    await nodes(root,'button').find(n => content(n) === '网站会话').props.onClick(); await tick(); await tick()
    assert.doesNotMatch(content(root), /私人角色|鹰角寻访|森空岛档案/)
    assert.match(content(root), /网站登录/)
    assert.ok(paths.every(path => /^\/api\/(identity|accounts|public)(\/|$)/.test(path)))
  })
}
test('reloading on the accounts page keeps the first reads of its panels when the account list selects an authorization', async t => {
  const browser = new Window({ width: 1440, height: 900 }), originalWindow = globalThis.window
  browser.location.hash = '#/accounts'
  globalThis.window = browser; t.after(() => { globalThis.window = originalWindow; browser.happyDOM.abort() })
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  const account = { account_id: 'a1', provider: 'kuro', game: 'wuthering_waves', state: 'active', capabilities: [], roles: [{ role_id: 'r1', display_name: '角色甲', is_default: true }] }
  const link = { link_id: 'l1', identity: { scene: 'group', group_openid: 'fixture-group', sender_openid: 'fixture-sender' } }
  const answers = [], requests = []
  t.mock.method(globalThis, 'fetch', (path, options = {}) => new Promise((resolve, reject) => {
    requests.push(path)
    const data = path === '/api/identity/me' ? { user_id: 'u1', is_admin: false } : path.endsWith('/csrf') ? { csrf_token: 'fixture' } : path === '/api/accounts' ? { accounts: [account] } : path === '/api/qq/link-attempts' ? { links: [link] } : { state: 'never', payload: null }
    answers.push(() => resolve(new Response(JSON.stringify(data))))
    options.signal?.addEventListener('abort', () => reject(options.signal.reason), { once: true })
  }))
  const root = mount(t, CloudApp)
  // A real network answers in request order, one event-loop turn apart.
  for (let i = 0; i < 40 && (answers.length || i < 3); i++) { answers.shift()?.(); await tick() }
  for (let i = 0; i < 4; i++) await tick()
  assert.ok(requests.includes('/api/qq/link-attempts'))
  assert.match(content(root), /已关联 · 群聊/)
  assert.deepEqual(nodes(root, 'p').filter(n => n.props.role === 'alert').map(content), [])
  assert.match(content(nodes(root, 'section').find(n => String(n.props.class).includes('login-panel'))), /角色甲/)
})
test('cloud public events render the real calendar with unknown dates and source details', async t => {
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  const calls=[]
  t.mock.method(globalThis,'fetch',async path=>{
    calls.push(path)
    const data=path==='/api/identity/me'?{user_id:'A'}:path.endsWith('/csrf')?{csrf_token:'fixture'}:path==='/api/accounts'?{accounts:[]}:path.endsWith('/events')?{payload:[{name:'云端待定活动',category:'官方活动',start_at:null,end_at:null,source_title:'公开活动公告',source_url:'https://example.com/fixture-event'}],state:'ok',fetched_at:'2026-10-12T00:00:00Z',complete:null}:{payload:[],state:'ok'}
    return new Response(JSON.stringify(data))
  })
  const root=mount(t,CloudApp);await tick();await tick()
  nodes(root,'button').find(n=>content(n)==='活动日历').props.onClick();await tick();await tick()
  const undated=nodes(root,'button').filter(node=>node.props['aria-label']==='查看活动详情：云端待定活动')
  assert.equal(undated.length,3);assert.ok(undated.every(node=>content(node)==='云端待定活动 官方活动 · 时间待定'))
  const sources=nodes(root,'details').find(node=>String(node.props.class).includes('calendar-source-states'))
  assert.ok(sources);assert.ok(!sources.props.open)
  const trigger=nodes(root,'button').find(n=>n.props['aria-label']==='查看活动详情：云端待定活动')
  assert.ok(trigger);await trigger.props.onClick();await tick()
  const detail=nodes(root,'section').find(node=>node.props['aria-labelledby']==='calendar-detail-title')
  assert.match(content(detail),/开始时间.*未知.*截止时间.*未知/);assert.match(content(detail),/公开活动公告/)
  assert.ok(calls.includes('/api/public/games/wuthering_waves/events'))
  assert.ok(calls.every(path=>!path.startsWith('/api/games/')))
})
