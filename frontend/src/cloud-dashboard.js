import { reactive } from 'vue'
import * as identity from './identity-api.js'
import * as accounts from './accounts-api.js'
import { setAccountScope, subscribeSessionInvalidation, obtainCsrf } from './http-client.js'
import { collectionState } from './snapshot-state.js'
const REFRESH_READ_INTERVAL = 2000, REFRESH_READ_LIMIT = 10, REFRESH_TRACK_TIMEOUT = 30000
export function createCloudDashboard(overrides = {}) {
  const api = { ...identity, ...accounts, obtainCsrf, ...overrides }
  const state = reactive({ user: null, accounts: [], selected: null, role: '', snapshots: {}, overview: {}, overviewLoading: false, sessions: [], error: '', loading: false, ready: false, refreshing: {}, refreshPending: {}, revision: 0 })
  let epoch = 0, disposed = false
  let overviewGeneration = 0
  const refreshVersions = new Map(), readVersions = new Map(), refreshJobs = new Map()
  const current = version => !disposed && version === epoch
  function stopRefresh(cap, job = refreshJobs.get(cap)) {
    if (!job || refreshJobs.get(cap) !== job) return
    clearTimeout(job.timer); clearTimeout(job.deadline); refreshJobs.delete(cap); state.refreshPending[cap] = false
  }
  function stopTracking() { for (const [cap, job] of refreshJobs) { state.refreshing[cap] = '刷新状态待确认，请读取快照'; stopRefresh(cap, job) } }
  function clear() { stopTracking(); epoch++; overviewGeneration++; state.revision++; setAccountScope(null); Object.assign(state, { user: null, accounts: [], selected: null, role: '', snapshots: {}, overview: {}, overviewLoading: false, sessions: [], error: '', loading: false, refreshing: {}, refreshPending: {} }) }
  const stop = subscribeSessionInvalidation(clear)
  async function initialize() {
    stopTracking()
    const version = ++epoch; state.loading = true
    try {
      const user = await api.getMe(); if (!current(version)) return
      await api.obtainCsrf(true); if (!current(version)) return
      if (state.user && state.user.user_id !== user.user_id) clear()
      state.user = user; await loadAccounts()
    }
    catch (error) { if (current(version) && error.status !== 401 && error.name !== 'AbortError') state.error = error.message }
    finally { state.ready = true; if (current(version)) state.loading = false }
  }
  async function loadAccounts() {
    const version = epoch, user = state.user?.user_id
    if (!user) return
    try {
      const data = await api.getAccounts()
      if (!current(version) || state.user?.user_id !== user) return
      state.accounts = Array.isArray(data.accounts) ? data.accounts : []
      for (const id of Object.keys(state.overview)) {
        const row = state.accounts.find(a => a.account_id === id), cached = state.overview[id]
        if (!row || row.state === 'revoked' || cached.version !== row.version || cached.grant_id !== row.grant_id || JSON.stringify(cached.roles) !== JSON.stringify(row.roles)) delete state.overview[id]
      }
      const selected = state.accounts.find(row => row.account_id === state.selected?.account_id) || state.accounts[0]
      if (selected && selected.account_id === state.selected?.account_id && selected.state === state.selected.state && selected.version === state.selected.version && selected.grant_id === state.selected.grant_id && JSON.stringify(selected.roles) === JSON.stringify(state.selected.roles)) state.selected = selected
      else selectAccount(selected || null)
    } catch (error) { if (current(version) && error.name !== 'AbortError') state.error = error.message }
  }
  function selectAccount(account, role) {
    stopTracking()
    epoch++; state.revision++; state.selected = account; state.role = role || account?.roles?.find(row => row.is_default)?.role_id || account?.roles?.[0]?.role_id || ''
    state.snapshots = {}; state.refreshing = {}; state.refreshPending = {}; state.error = ''; state.loading = false
    setAccountScope(account && state.role ? { user_id: state.user?.user_id, account_id: account.account_id, role_id: state.role, provider: account.provider, version:account.version, grant_id:account.grant_id } : null)
  }
  async function loadOverview() {
    const version = ++overviewGeneration, owner = state.user?.user_id, accountVersion = JSON.stringify(state.accounts)
    if (!owner) return
    const valid = () => !disposed && version === overviewGeneration && owner === state.user?.user_id && accountVersion === JSON.stringify(state.accounts)
    state.overviewLoading = true
    try {
      await Promise.all(state.accounts.filter(a => a.state !== 'revoked').map(async account => {
        const role = account.roles?.find(r => r.is_default)?.role_id || account.roles?.[0]?.role_id
        if (!role) return
        const caps = accounts.accountCapabilities(account).filter(cap => ['account','stamina','gacha'].includes(cap))
        const old = state.overview[account.account_id]
        const entry = { role, version: account.version, grant_id: account.grant_id, roles: account.roles, snapshots: old?.role === role ? { ...old.snapshots } : {} }
        await Promise.all(caps.map(async cap => {
          try { entry.snapshots[cap] = account.account_id === state.selected?.account_id && role === state.role && state.snapshots[cap] ? state.snapshots[cap] : await api.getAccountSnapshot(account.account_id, role, cap) }
          catch (error) { if (error.name !== 'AbortError') entry.snapshots[cap] = { ...(entry.snapshots[cap] || { payload: null }), state: 'error', error: error.message } }
        }))
        if (valid()) state.overview[account.account_id] = entry
      }))
    } finally { if (version === overviewGeneration) state.overviewLoading = false }
  }
  async function loadSnapshot(cap, trackedJob) {
    const version = epoch, account = state.selected?.account_id, role = state.role
    const refreshVersion = refreshVersions.get(cap), mutationPending = state.refreshing[cap] === '正在排队'
    const readVersion = (readVersions.get(cap) || 0) + 1
    readVersions.set(cap, readVersion)
    const valid = () => current(version) && refreshVersion === refreshVersions.get(cap) && readVersion === readVersions.get(cap) && (!trackedJob || refreshJobs.get(cap) === trackedJob)
    if (!account || !role) return
    try {
      const data = await api.getAccountSnapshot(account, role, cap)
      if (valid()) {
        state.snapshots[cap] = data
        const entry = state.overview[account]
        if (entry?.role === role) entry.snapshots[cap] = data
        if (!mutationPending && state.refreshing[cap] !== '正在排队') {
          const refreshState = data.poll_status?.refresh_state
          if (refreshState === 'queued' && refreshJobs.has(cap)) state.refreshing[cap] = '刷新已排队，正在读取状态…'
          else if (refreshState === 'running' && refreshJobs.has(cap)) state.refreshing[cap] = '正在刷新，保留已有快照…'
          else if (refreshState === 'idle' && state.refreshing[cap]) {
            state.refreshing[cap] = collectionState(data) === 'failed' ? `刷新失败，${data.payload == null ? '尚无成功数据' : '保留上次成功数据'}` : data.state === 'never' ? '刷新已结束，尚未采集到数据' : ''
            stopRefresh(cap)
          }
        }
        return data
      }
    }
    catch (error) { if (valid() && error.name !== 'AbortError') {
      state.snapshots[cap] = { ...(state.snapshots[cap] || { payload: null }), state: 'error', error: error.message }
      if (refreshJobs.has(cap) && !mutationPending) { state.refreshing[cap] = '刷新状态读取失败，保留已有数据；请稍后读取快照'; stopRefresh(cap) }
    } }
  }
  function trackRefresh(cap, job) {
    const valid = () => current(job.epoch) && refreshJobs.get(cap) === job
    function timeout() {
      if (!valid()) return
      state.refreshing[cap] = '刷新仍未确认完成，请稍后读取快照'
      // Ignore a hanging/late read after the bounded tracking window.
      readVersions.set(cap, (readVersions.get(cap) || 0) + 1); stopRefresh(cap, job)
    }
    async function poll() {
      if (!valid()) return
      await loadSnapshot(cap, job)
      if (!valid()) return
      if (++job.reads >= REFRESH_READ_LIMIT) timeout()
      else job.timer = setTimeout(poll, REFRESH_READ_INTERVAL)
    }
    job.deadline = setTimeout(timeout, REFRESH_TRACK_TIMEOUT)
    job.timer = setTimeout(poll, 0)
  }
  async function refresh(cap) {
    const version = epoch
    if (!state.selected || !state.role || refreshJobs.has(cap)) return
    refreshVersions.set(cap, (refreshVersions.get(cap) || 0) + 1)
    state.refreshing[cap] = '正在排队'
    const job = { epoch: version, reads: 0 }; refreshJobs.set(cap, job); state.refreshPending[cap] = true
    try {
      const receipt = await api.refreshAccount(state.selected.account_id, state.role, cap)
      if (current(version) && refreshJobs.get(cap) === job) {
        // Reads started during POST cannot settle or overwrite the accepted job.
        readVersions.set(cap, (readVersions.get(cap) || 0) + 1)
        state.refreshing[cap] = receipt.state === 'coalesced' ? '已有刷新任务，正在读取状态…' : '刷新已排队，正在读取状态…'
        trackRefresh(cap, job)
      }
    }
    catch (error) { if (current(version) && refreshJobs.get(cap) === job && error.name !== 'AbortError') { state.refreshing[cap] = ''; state.error = error.message; stopRefresh(cap, job) } }
  }
  async function loadSessions() {
    const version = epoch
    try { const data = await api.getSessions(); if (current(version)) state.sessions = data.sessions || [] }
    catch (error) { if (current(version) && error.name !== 'AbortError') state.error = error.message }
  }
  async function logout() {
    // Begin the server mutation before clearing in-memory data; its response is
    // deliberately irrelevant to private state. Failure remains visible to user.
    const pending = api.logoutSite(); clear()
    try { await pending } catch (error) { if (error.name !== 'AbortError' && error.status !== 401) state.error = '网站退出请求未完成，请重试退出' }
  }
  return { state, initialize, loadAccounts, selectAccount, loadSnapshot, loadOverview, refresh, loadSessions, logout, clear,
    dispose() { disposed = true; clear(); stop() } }
}
