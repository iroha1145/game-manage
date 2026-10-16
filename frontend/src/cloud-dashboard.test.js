import test from 'node:test'
import assert from 'node:assert/strict'
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
  assert.match(dashboard.state.refreshing.account, /正在刷新/)
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
    assert.match(dashboard.state.refreshing.account, /失败.*保留/)
    t.mock.timers.tick(60000); await flush(); assert.equal(reads, 1)
    dashboard.dispose()
})

test('bounded tracking stops even if a read hangs; late read cannot replace a newer observation', async t => {
  let finish, reads = 0
  const dashboard = setup(t, { refreshAccount: async () => ({ state: 'queued' }), getAccountSnapshot: () => { reads++; return new Promise(resolve => { finish = resolve }) } })
  await dashboard.refresh('account'); t.mock.timers.tick(0); await flush()
  t.mock.timers.tick(30000); await flush()
  assert.match(dashboard.state.refreshing.account, /仍未确认.*读取/)
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
  assert.equal(reads, 10); assert.match(dashboard.state.refreshing.account, /仍未确认/)
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
