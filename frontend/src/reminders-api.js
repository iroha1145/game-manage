import { requestJson } from './http-client.js'
const path = (account,role) => `/api/accounts/${encodeURIComponent(account)}/roles/${encodeURIComponent(role)}/reminders`
export const getReminderRule = (account,role,signal) => requestJson(path(account,role),{signal})
export const saveReminderRule = (account,role,rule) => requestJson(path(account,role),{method:'PUT',body:rule})
export const getReminderInbox = (account,role,signal) => requestJson(path(account,role)+'/inbox',{signal})
const groupPath = group => `/api/admin/qq/groups/${encodeURIComponent(group)}/settings`
export const getGroupSettings = group => requestJson(groupPath(group))
export const saveGroupSettings = (group,settings) => requestJson(groupPath(group),{method:'PUT',body:settings})
