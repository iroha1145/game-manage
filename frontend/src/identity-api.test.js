import test from 'node:test'
import assert from 'node:assert/strict'
import { configureHttpClient } from './http-client.js'
import { loginSite, registerSite, logoutSite } from './identity-api.js'
import { createCloudDashboard } from './cloud-dashboard.js'
test('website login obtains preauth csrf then authenticated csrf without game credentials', async t => {
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  const calls = []; let count = 0
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push([url, options]); return new Response(JSON.stringify(url.endsWith('/csrf') ? { csrf_token: `csrf-${++count}` } : { user_id: 'A', is_admin: false }))
  })
  await loginSite({ username: 'alice', password: 'sample-password' })
  assert.deepEqual(calls.map(x => x[0]), ['/api/identity/csrf','/api/identity/login','/api/identity/csrf'])
  assert.equal(calls[1][1].headers['X-CSRF-Token'], 'csrf-1')
  assert.deepEqual(JSON.parse(calls[1][1].body), { username: 'alice', password: 'sample-password' })
  await registerSite({ username: 'bob', password: 'sample-password', invite: 'sample-invite' })
  assert.ok(calls.some(x => x[0] === '/api/identity/register'))
  await logoutSite()
})
test('logout clears private state immediately and late account results cannot restore it', async t => {
  let resolveAccounts, finishLogout
  const dashboard = createCloudDashboard({
    getMe: async () => ({ user_id: 'A' }), obtainCsrf: async () => {}, getAccounts: () => new Promise(resolve => { resolveAccounts = resolve }),
    logoutSite: () => new Promise(resolve => { finishLogout = resolve }),
  })
  t.after(dashboard.dispose)
  const loading = dashboard.initialize(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
  dashboard.state.snapshots = { account: { payload: { nickname: 'A' } } }
  dashboard.state.sessions = [{ session_id: 'A' }]
  const logout = dashboard.logout()
  assert.equal(dashboard.state.user, null); assert.deepEqual(dashboard.state.snapshots, {}); assert.deepEqual(dashboard.state.sessions, [])
  resolveAccounts({ accounts: [{ account_id: 'A' }] }); await loading
  assert.deepEqual(dashboard.state.accounts, [])
  finishLogout({}); await logout
})
test('account refresh preserves selected role and existing payload; old user snapshot is ignored', async t => {
  const account = { account_id:'a', provider:'kuro', state:'active', roles:[{role_id:'r1',is_default:true},{role_id:'r2'}] }
  let finish
  const dashboard = createCloudDashboard({ getAccounts: async () => ({accounts:[account]}), getAccountSnapshot: () => new Promise(resolve => { finish = resolve }) })
  t.after(dashboard.dispose)
  dashboard.state.user = { user_id:'A' }; dashboard.selectAccount(account,'r2')
  dashboard.state.snapshots = { account:{payload:{nickname:'old'}} }
  await dashboard.loadAccounts()
  assert.equal(dashboard.state.role,'r2'); assert.equal(dashboard.state.snapshots.account.payload.nickname,'old')
  const pending = dashboard.loadSnapshot('account'); dashboard.clear(); dashboard.state.user = {user_id:'B'}; dashboard.selectAccount({...account,account_id:'b'})
  finish({payload:{nickname:'private-A'}}); await pending
  assert.deepEqual(dashboard.state.snapshots,{})
})
test('queued refresh suppresses duplicate submission; read failure retains payload and allows later coalesced refresh', async t => {
  let requests=0
  const dashboard=createCloudDashboard({refreshAccount:async()=>({state:++requests===1?'queued':'coalesced'}),getAccountSnapshot:async()=>{throw new Error('fixture source failure')}})
  t.after(dashboard.dispose)
  dashboard.state.user={user_id:'A'};dashboard.selectAccount({account_id:'a',provider:'kuro',roles:[{role_id:'r',is_default:true}]})
  dashboard.state.snapshots.account={payload:{nickname:'retained'},fetched_at:'2026-10-12T01:00:00Z'}
  await dashboard.refresh('account'); assert.match(dashboard.state.refreshing.account,/排队/)
  await dashboard.refresh('account'); assert.equal(requests,1)
  await dashboard.loadSnapshot('account');assert.equal(dashboard.state.snapshots.account.payload.nickname,'retained');assert.equal(dashboard.state.snapshots.account.state,'error')
  await dashboard.refresh('account'); assert.equal(requests,2);assert.match(dashboard.state.refreshing.account,/已有刷新任务/)
})
test('reauthorization of the same account and role invalidates cached views and old grant responses',async t=>{
  const original={account_id:'a',provider:'kuro',state:'active',version:1,grant_id:'g',roles:[{role_id:'r',is_default:true}]}
  const dashboard=createCloudDashboard({getAccounts:async()=>({accounts:[{...original,version:2}]})});t.after(dashboard.dispose)
  dashboard.state.user={user_id:'A'};dashboard.selectAccount(original);dashboard.state.snapshots.account={payload:'old-grant'}
  const revision=dashboard.state.revision
  await dashboard.loadAccounts()
  assert.deepEqual(dashboard.state.snapshots,{});assert.notEqual(dashboard.state.revision,revision)
})
test('idle poll clears refresh receipt while pending mutation and older reads preserve current refresh',async t=>{
  let finishRefresh,finishRead,deferRead=false
  const dashboard=createCloudDashboard({
    refreshAccount:()=>new Promise(resolve=>{finishRefresh=resolve}),
    getAccountSnapshot:()=>deferRead?new Promise(resolve=>{finishRead=resolve}):Promise.resolve({payload:{nickname:'current'},state:'ok',poll_status:{refresh_state:'idle'}}),
  });t.after(dashboard.dispose)
  dashboard.state.user={user_id:'A'};dashboard.selectAccount({account_id:'a',provider:'kuro',roles:[{role_id:'r',is_default:true}]})
  const pending=dashboard.refresh('account')
  await dashboard.loadSnapshot('account');assert.equal(dashboard.state.refreshing.account,'正在排队')
  finishRefresh({state:'queued'});await pending
  await dashboard.loadSnapshot('account'); assert.equal(dashboard.state.refreshing.account,'')
  deferRead=true;const olderRead=dashboard.loadSnapshot('account')
  const newerRefresh=dashboard.refresh('account');finishRefresh({state:'coalesced'});await newerRefresh
  finishRead({payload:{nickname:'old-observation'},state:'ok',poll_status:{refresh_state:'idle'}});await olderRead
  assert.match(dashboard.state.refreshing.account,/已有刷新任务/)
  deferRead=false;await dashboard.loadSnapshot('account')
  assert.equal(dashboard.state.refreshing.account,'')
})
