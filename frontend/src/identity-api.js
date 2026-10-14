import { requestJson, obtainCsrf, invalidateSession, HttpError } from './http-client.js'
const registrationMessages = Object.freeze({
  invalid_username:'用户名需为 3–64 位英文字母、数字、下划线（_）、点（.）或短横线（-）。',
  invalid_password:'密码需为 12–128 个字符。',
  invalid_invite:'邀请码不可用，请联系管理员获取新的邀请码。',
  registration_unavailable:'注册信息无法使用，请检查输入；已有账号请直接登录。',
})
export const getMe = () => requestJson('/api/identity/me')
export const getSessions = () => requestJson('/api/identity/sessions')
export const revokeSession = id => requestJson(`/api/identity/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' })
async function establish(action, body) {
  await obtainCsrf(true)
  let user
  try { user = await requestJson(`/api/identity/${action}`, { method: 'POST', body }) }
  catch (error) {
    if (action === 'register' && error instanceof HttpError && error.status === 400 && Object.hasOwn(registrationMessages, error.code)) {
      error.message = registrationMessages[error.code]
    }
    throw error
  }
  invalidateSession()
  await obtainCsrf()
  return user
}
export const loginSite = ({ username, password }) => establish('login', { username, password })
export const registerSite = async ({ username, password, invite }) => {
  if (typeof username !== 'string' || !/^[A-Za-z0-9_.-]{3,64}$/.test(username)) {
    const error = new HttpError(400, 'invalid_username'); error.message = registrationMessages.invalid_username
    throw error
  }
  return establish('register', { username, password, invite })
}
export async function logoutSite() {
  try { return await requestJson('/api/identity/logout', { method: 'POST' }) }
  finally { invalidateSession() }
}
