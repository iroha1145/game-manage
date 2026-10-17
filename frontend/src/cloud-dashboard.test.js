import test from 'node:test'
import assert from 'node:assert/strict'
import { configureHttpClient, requestJson } from './http-client.js'
import { createCloudDashboard } from './cloud-dashboard.js'

const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve() }
const account = { account_id: 'a', provider: 'kuro', roles: [{ role_id: 'r', is_default: true }] }
function setup(t, api) {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] })
  const dashboard = createCloudDashboard(api)
  t.after(dashboard.dispose)
  dashboard.state.user = { user_id: 'A' }; dashboard.selectAccount(account)
  dashboard.state.snapshots.account = { payload: { nickname: 'old' }, state: 'ok', fetched_at: '2026-10-12T22:40:00+08:00' }
  return dashboard
}
const snapshot = (refresh_state, state = 'ok', nickname = 'new') => ({ payload: { nickname }, state, poll_status: { refresh_state, state } })

test('same-owner session checks do not orphan an in-flight snapshot', async t => {
  let finish
  const d = createCloudDashboard({ getMe: async () => ({ user_id:'A' }), obtainCsrf: async () => 'csrf',
    getAccounts: async () => ({ accounts:[account] }), getAccountSnapshot: () => new Promise(resolve => { finish=resolve }) })
  t.after(d.dispose)
  await d.initialize(); const pending=d.loadSnapshot('account')
  await d.initialize(); finish(snapshot('idle')); await pending
  assert.equal(d.state.readStates.account.status,'success')
  assert.equal(d.state.snapshots.account.payload.nickname,'new')
})

test('a session check cannot restore a cleared website identity', async t => {
  let finish
  const d=createCloudDashboard({getMe:()=>new Promise(resolve=>{finish=resolve}),obtainCsrf:async()=> 'csrf',getAccounts:async()=>({accounts:[account]})})
  t.after(d.dispose)
  const pending=d.initialize();d.clear();finish({user_id:'A'});await pending
  assert.equal(d.state.user,null)
})

test('overview and selected page coalesce only the same scoped snapshot GET', async t=>{
 let finish,calls=0
 const dashboard=setup(t,{getAccountSnapshot:()=>{calls++;return new Promise(resolve=>{finish=resolve})}})
 dashboard.state.snapshots={}
 dashboard.state.accounts=[{...account,capabilities:['account']}]
 const page=dashboard.loadSnapshot('account'),overview=dashboard.loadOverview()
 await flush();assert.equal(calls,1)
 finish(snapshot('idle'));await Promise.all([page,overview])
 assert.equal(dashboard.state.overview.a.snapshots.account.payload.nickname,'new')
})

test('overview displays each capability as it arrives while another read is pending', async t => {
  let finish
  const dashboard = createCloudDashboard({ getAccountSnapshot: async (_id, _role, cap) => {
    if(cap === 'account') return new Promise(resolve => { finish = resolve })
    return { state:'ok', payload:{ current:123, maximum:240 } }
  } })
  t.after(dashboard.dispose)
  dashboard.state.user={user_id:'fixture-user'}
  dashboard.state.accounts=[{...account,capabilities:['account','stamina'],version:1,grant_id:'fixture-grant'}]
  const pending=dashboard.loadOverview(); await flush()
  assert.equal(dashboard.state.overview.a?.snapshots.stamina?.payload.current,123)
  assert.equal(dashboard.state.overviewLoading,true)
  finish({state:'ok',payload:{nickname:'fixture'}}); await pending
})

test('snapshot read state is loading until success and is cleared on a scope switch', async t => {
  let finish
  const dashboard=setup(t,{getAccountSnapshot:()=>new Promise(resolve=>{finish=resolve})})
  const pending=dashboard.loadSnapshot('roles')
  assert.equal(dashboard.state.readStates?.roles?.status,'loading')
  finish({state:'ok',payload:[]}); await pending
  assert.equal(dashboard.state.readStates.roles.status,'success')
  dashboard.selectAccount({...account,account_id:'other'})
  assert.deepEqual(dashboard.state.readStates,{})
})

test('accepted refresh reads queued, running and idle snapshots promptly without another upstream refresh', async t => {
  let requests = 0, reads = 0
  const results = [snapshot('queued', 'ok', 'old'), snapshot('running', 'ok', 'old'), snapshot('idle')]
  const dashboard = setup(t, { refreshAccount: async () => { requests++; return { state: 'queued' } }, getAccountSnapshot: async () => { reads++; return results.shift() } })
  await dashboard.refresh('account')
  assert.equal(dashboard.state.snapshots.account.payload.nickname, 'old')
  t.mock.timers.tick(0); await flush()
  assert.equal(reads, 1); assert.match(dashboard.state.refreshing.account, /排队/)
  await dashboard.refresh('account'); assert.equal(requests, 1)
  t.mock.timers.tick(2000); await flush()
  assert.match(dashboard.state.refreshing.account, /刷新中/)
  t.mock.timers.tick(2000); await flush()
  assert.equal(dashboard.state.refreshing.account, '')
  assert.equal(dashboard.state.snapshots.account.payload.nickname, 'new')
  t.mock.timers.tick(60000); await flush(); assert.equal(reads, 3)
})

for (const readFailure of [false, true]) test(`${readFailure ? 'snapshot read' : 'idle collection'} failure preserves data and stops tracking with explicit failure`, async t => {
    let reads = 0
    const dashboard = setup(t, { refreshAccount: async () => ({ state: 'coalesced' }), getAccountSnapshot: async () => {
      reads++; if (readFailure) throw new Error('网络连接失败')
      return snapshot('idle', 'error', 'old')
    } })
    await dashboard.refresh('account'); t.mock.timers.tick(0); await flush()
    assert.equal(dashboard.state.snapshots.account.payload.nickname, 'old')
    assert.match(dashboard.state.refreshing.account, /失败.*上次/)
    t.mock.timers.tick(60000); await flush(); assert.equal(reads, 1)
    dashboard.dispose()
})

test('bounded tracking stops even if a read hangs; late read cannot replace a newer observation', async t => {
  let finish, reads = 0
  const dashboard = setup(t, { refreshAccount: async () => ({ state: 'queued' }), getAccountSnapshot: () => { reads++; return new Promise(resolve => { finish = resolve }) } })
  await dashboard.refresh('account'); t.mock.timers.tick(0); await flush()
  t.mock.timers.tick(30000); await flush()
  assert.match(dashboard.state.refreshing.account, /仍未完成.*重试/)
  assert.notEqual(dashboard.state.readStates.account?.status,'loading')
  assert.equal(dashboard.state.snapshots.account.payload.nickname, 'old')
  finish(snapshot('idle', 'ok', 'late')); await flush()
  assert.equal(dashboard.state.snapshots.account.payload.nickname, 'old')
  assert.equal(reads, 1)
})

test('switching user cancels tracking and ignores old snapshot and receipt responses', async t => {
  let finish, reads = 0
  const dashboard = setup(t, { refreshAccount: async () => ({ state: 'queued' }), getAccountSnapshot: () => { reads++; return new Promise(resolve => { finish = resolve }) } })
  await dashboard.refresh('account'); t.mock.timers.tick(0); await flush()
  dashboard.clear(); dashboard.state.user = { user_id: 'B' }; dashboard.selectAccount({ ...account, account_id: 'b' })
  finish(snapshot('idle', 'ok', 'private-A')); await flush(); t.mock.timers.tick(60000); await flush()
  assert.deepEqual(dashboard.state.snapshots, {}); assert.deepEqual(dashboard.state.refreshing, {}); assert.equal(reads, 1)
})

test('reads started before or during refresh acceptance cannot overwrite a newer snapshot', async t => {
  let finishOld, finishReceipt, finishDuring, count = 0
  const dashboard = setup(t, { refreshAccount: () => new Promise(resolve => { finishReceipt = resolve }), getAccountSnapshot: () => {
    count++
    if (count === 1) return new Promise(resolve => { finishOld = resolve })
    if (count === 2) return new Promise(resolve => { finishDuring = resolve })
    return Promise.resolve(snapshot('idle'))
  } })
  const older = dashboard.loadSnapshot('account'), refresh = dashboard.refresh('account'), during = dashboard.loadSnapshot('account')
  finishReceipt({ state: 'queued' }); await refresh
  t.mock.timers.tick(0); await flush()
  finishOld(snapshot('idle', 'ok', 'old-read')); finishDuring(snapshot('idle', 'ok', 'during-post')); await Promise.all([older, during])
  assert.equal(dashboard.state.snapshots.account.payload.nickname, 'new')
  assert.equal(dashboard.state.refreshing.account, '')
})

test('queued tracking has a read limit and a later manual read can settle the receipt', async t => {
  let reads = 0, done = false
  const dashboard = setup(t, { refreshAccount: async () => ({ state: 'queued' }), getAccountSnapshot: async () => { reads++; return snapshot(done ? 'idle' : 'queued', 'ok', done ? 'new' : 'old') } })
  await dashboard.refresh('account'); t.mock.timers.tick(0); await flush()
  for (let i = 0; i < 9; i++) { t.mock.timers.tick(2000); await flush() }
  assert.equal(reads, 10); assert.match(dashboard.state.refreshing.account, /仍未完成/)
  assert.equal(dashboard.state.refreshPending.account, false)
  t.mock.timers.tick(60000); await flush(); assert.equal(reads, 10)
  done = true; await dashboard.loadSnapshot('account')
  assert.equal(dashboard.state.refreshing.account, ''); assert.equal(dashboard.state.snapshots.account.payload.nickname, 'new')
})

test('rejected refresh preserves snapshots; logout or disposal drops a pending receipt without starting reads', async t => {
  let finish, reads = 0, reject = true
  const dashboard = setup(t, { refreshAccount: () => reject ? Promise.reject(new Error('刷新请求失败')) : new Promise(resolve => { finish = resolve }), getAccountSnapshot: async () => { reads++; return snapshot('idle') }, logoutSite: async () => ({}) })
  await dashboard.refresh('account')
  assert.match(dashboard.state.error, /刷新请求失败/); assert.equal(dashboard.state.refreshPending.account, false)
  assert.equal(dashboard.state.snapshots.account.payload.nickname, 'old')
  reject = false
  const pending = dashboard.refresh('account'); await dashboard.logout()
  finish({ state: 'queued' }); await pending; t.mock.timers.tick(60000); await flush()
  assert.equal(reads, 0); assert.deepEqual(dashboard.state.refreshing, {})
  dashboard.state.user = { user_id: 'B' }; dashboard.selectAccount(account)
  const pendingDispose = dashboard.refresh('account'); dashboard.dispose()
  finish({ state: 'queued' }); await pendingDispose; t.mock.timers.tick(60000); await flush()
  assert.equal(reads, 0); assert.deepEqual(dashboard.state.refreshing, {})
})

test('the error of a failed session check does not outlive the next successful one', async t => {
  let online = true
  const dashboard = createCloudDashboard({ getMe: async () => { if (!online) throw new TypeError('无法连接服务，请稍后重试'); return { user_id: 'A' } },
    obtainCsrf: async () => 'csrf', getAccounts: async () => ({ accounts: [account] }) })
  t.after(dashboard.dispose)
  await dashboard.initialize()
  online = false; await dashboard.initialize()
  assert.equal(dashboard.state.error, '无法连接服务，请稍后重试')
  assert.equal(dashboard.state.user.user_id, 'A', 'the signed-in page stays while the service is unreachable')
  online = true; await dashboard.initialize()
  assert.equal(dashboard.state.error, '', 'the banner of a past failure is still shown')
})

const unreachable = () => new TypeError('无法连接服务，请稍后重试')
const answered = status => Object.assign(new Error(`HTTP ${status}`), { status })
for (const [name, failure, expected] of [['the service cannot be reached', unreachable(), true], ['the service answers with an error', answered(503), true], ['the site session is already gone (401)', answered(401), false]])
  test(`logout when ${name}: the private state is cleared at once and ${expected ? 'a retry stays on offer' : 'nothing is left to retry'}`, async t => {
    let outcome = failure
    const dashboard = createCloudDashboard({ logoutSite: async () => { if (outcome) throw outcome; return {} } })
    t.after(dashboard.dispose)
    dashboard.state.user = { user_id: 'A' }; dashboard.selectAccount(account); dashboard.state.snapshots.account = { payload: { nickname: 'old' } }
    await dashboard.logout()
    assert.equal(dashboard.state.user, null); assert.deepEqual(dashboard.state.snapshots, {})
    assert.equal(dashboard.state.logoutFailed, expected)
    if (!expected) return
    dashboard.clear(); assert.equal(dashboard.state.logoutFailed, true, 'a session reset must not turn a failed logout into a signed-out page')
    outcome = null
    const retry = dashboard.logout(); assert.equal(dashboard.state.logoutFailed, false, 'the retry is under way'); await retry
    assert.equal(dashboard.state.logoutFailed, false); assert.equal(dashboard.state.error, '')
  })


test('session reinitialization refreshes CSRF after another tab rotates its cookie',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
  let owner='A',csrfReads=0
  t.mock.method(globalThis,'fetch',async(path,options)=>{
    if(path.endsWith('/csrf')){csrfReads++;return new Response(JSON.stringify({csrf_token:`csrf-${owner}`}))}
    if(options.method==='POST')return new Response(JSON.stringify({ok:true}),{status:options.headers['X-CSRF-Token']===`csrf-${owner}`?200:403})
    return new Response(JSON.stringify(path==='/api/identity/me'?{user_id:owner}:{accounts:[]}))
  })
  const d=createCloudDashboard();t.after(d.dispose)
  await d.initialize();owner='B';await d.initialize()
  assert.deepEqual(await requestJson('/api/accounts/synthetic/roles/r/refresh/account',{method:'POST'}),{ok:true})
  assert.equal(csrfReads,2)
})
