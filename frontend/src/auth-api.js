import { requestResponse, isCloudMode } from './http-client.js'
import { getAccounts, revokeAuthorization } from './accounts-api.js'
export class AuthError extends Error {
  constructor(message, status = 0, retryAfter = 0) {
    super(message)
    this.name = 'AuthError'
    this.status = status
    this.retryAfter = retryAfter
  }
}

async function request(path, method = 'GET', body, timeoutMs = 30000) {
  const headers = { Accept: 'application/json' }
  if (method !== 'GET') headers['X-Game-Assistant'] = '1'
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let response
  try {
    const provider = { wuthering_waves: 'kuro', nte: 'tajiduo', endfield: 'hypergryph' }
    const cloudPath = path.replace(/^\/([^/]+)/, (_, game) => '/' + (provider[game] || game))
    response = await requestResponse(isCloudMode() ? `/api/accounts/auth${cloudPath}` : `/api/auth${path}`, {
      method, headers, credentials: 'same-origin',
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
      signal: AbortSignal.timeout(timeoutMs),
    })
  } catch {
    throw new AuthError('无法连接登录服务，请检查网络后重试')
  }
  let data
  try { data = await response.json() } catch { /* Do not display upstream HTML or diagnostics. */ }
  if (!response.ok) {
    const detail = typeof data?.detail === 'string' && data.detail.trim()
      ? data.detail : '登录服务暂时不可用，请稍后重试'
    const retry = Number(response.headers.get('Retry-After') || data?.retry_after)
    throw new AuthError(detail, response.status,
      Number.isFinite(retry) && retry > 0 ? Math.ceil(retry) : (response.status === 429 ? 60 : 0))
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new AuthError('登录服务响应异常，请重试', response.status)
  }
  return data
}

export const getAuthStatus = async () => {
  if (!isCloudMode()) return request('/status')
  const data = await getAccounts(), accounts = {}
  for (const [game, provider] of Object.entries({ wuthering_waves: 'kuro', nte: 'tajiduo', endfield: 'hypergryph' })) {
    const account = data.accounts?.find(row => row.provider === provider)
    accounts[game] = { configured: !!account && account.state !== 'revoked', state: account?.state || 'unconfigured', nickname: account?.roles?.find(row => row.is_default)?.display_name || '' }
  }
  return { accounts }
}
export const createAuthSession = (game) => request(`/${encodeURIComponent(game)}/sessions`, 'POST')
export const sendAuthSms = (game, body) => request(`/${encodeURIComponent(game)}/sms`, 'POST', body)
// Login exchanges several upstream credentials sequentially before saving the account.
export const loginAuth = (game, body) => request(`/${encodeURIComponent(game)}/login`, 'POST', body, 120000)
export const logoutAuth = async game => {
  if (!isCloudMode()) return request(`/${encodeURIComponent(game)}`, 'DELETE')
  const provider = { wuthering_waves: 'kuro', nte: 'tajiduo', endfield: 'hypergryph' }[game]
  const data = await getAccounts(), account = data.accounts?.find(row => row.provider === provider)
  if (!account) throw new AuthError('游戏授权不存在', 404)
  await revokeAuthorization(account.account_id)
  return { ok: true, account: { configured: false, state: 'unconfigured' } }
}
