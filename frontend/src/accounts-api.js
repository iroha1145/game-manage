import { requestJson } from './http-client.js'
const accountPath = id => `/api/accounts/${encodeURIComponent(id)}`
export const getAccounts = () => requestJson('/api/accounts')
export const setDefaultRole = (id, role_id) => requestJson(accountPath(id) + '/default-role', { method: 'PUT', body: { role_id } })
export const revokeAuthorization = id => requestJson(accountPath(id) + '/authorization', { method: 'DELETE' })
const scoped = (id, role) => `${accountPath(id)}/roles/${encodeURIComponent(role)}`
export const getAccountSnapshot = (id, role, cap, options = {}) => requestJson(`${scoped(id, role)}/snapshot/${encodeURIComponent(cap)}`, { timeoutMs: 20000, ...options })
export const refreshAccount = (id, role, cap) => requestJson(`${scoped(id, role)}/refresh/${encodeURIComponent(cap)}`, { method: 'POST' })
export const getPublicSnapshot = (game, cap) => requestJson(`/api/public/games/${encodeURIComponent(game)}/${encodeURIComponent(cap)}`, { timeoutMs: 20000 })
export const connectCloudSkland = (cred, device_id = '', options = {}) => requestJson('/api/accounts/auth/skland/connect', { ...options, method: 'POST', body: { cred, device_id } })
export const connectCloudSklandPassport = (account_id, role_id, options = {}) => requestJson('/api/accounts/auth/skland/passport', { ...options, method: 'POST', body: { account_id, role_id } })
export const providerName = account => ({ kuro: '鸣潮 · 库街区', tajiduo: '异环 · 哒哒社区', hypergryph: '终末地 · 鹰角寻访', skland: '终末地 · 森空岛档案' })[account.provider] || '游戏授权'
// The installed cloud runtime is authoritative. A missing matrix is setup state,
// never a reason to guess capabilities or call legacy endpoints.
export const accountCapabilities = account => Array.isArray(account?.capabilities) ? account.capabilities.filter(cap => typeof cap === 'string') : []
