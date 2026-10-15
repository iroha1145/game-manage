<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { connectCloudSkland, connectCloudSklandPassport } from '../accounts-api.js'
import { isCloudMode, subscribeSessionInvalidation } from '../http-client.js'
const props = defineProps({ accounts: { type: Array, default: () => [] }, userId: { type: String, required: true } })
const emit = defineEmits(['changed'])
const accountId = ref(''), roleId = ref(''), cred = ref(''), deviceId = ref('')
const busy = ref(''), error = ref(''), success = ref('')
// The accounts endpoint returns only the website user's verified roles. An
// explicit owner, when supplied, must still match the current website session.
const sources = computed(() => props.accounts.filter(account => account.provider === 'hypergryph' && account.game === 'endfield' && account.state === 'active' && (!account.user_id || account.user_id === props.userId)))
const source = computed(() => sources.value.find(account => account.account_id === accountId.value))
const roles = computed(() => source.value?.roles || [])
const role = computed(() => roles.value.find(item => item.role_id === roleId.value))
const canConnect = computed(() => isCloudMode() && !!props.userId && !!source.value && !!role.value && !busy.value)
const sourceStamp = computed(() => JSON.stringify([props.userId, source.value?.account_id, source.value?.grant_id, source.value?.version, source.value?.state, roles.value, roleId.value]))
let operation = 0, controller = null
function clear() { operation++; controller?.abort(); controller = null; busy.value = ''; error.value = ''; success.value = ''; cred.value = ''; deviceId.value = '' }
watch(sourceStamp, clear, { flush: 'sync' })
watch(() => props.userId, () => { accountId.value = ''; roleId.value = ''; clear() }, { flush: 'sync' })
function chooseAccount(event) { accountId.value = event.target.value; roleId.value = ''; clear() }
function chooseRole(event) { roleId.value = event.target.value; clear() }
async function run(kind, request) {
  if (busy.value || !isCloudMode() || !props.userId) return
  const id = ++operation, owner = props.userId, stamp = sourceStamp.value
  controller = new AbortController(); const signal = controller.signal
  busy.value = kind; error.value = ''; success.value = ''
  const current = () => id === operation && owner === props.userId && stamp === sourceStamp.value
  try {
    await request(signal)
    if (!current()) return
    success.value = '森空岛档案已连接。请在授权列表查看；鹰角寻访和森空岛档案可分别选择角色。'
    emit('changed')
  } catch (failure) {
    if (!current() || failure.name === 'AbortError') return
    error.value = failure.status === 409 && failure.code === 'skland_role_mismatch'
      ? '所选鹰角角色与森空岛角色未能匹配。请核对角色后重试，也可使用下方手动授权；已有授权已保留。'
      : failure.status === 409 && failure.code === 'authorization_changed'
        ? '来源授权已变化，请刷新授权列表后重新选择账号与角色；已有授权已保留，也可使用下方手动授权。'
        : (failure.name === 'HttpError' ? failure.message : '连接失败，请稍后重试') + '；已有授权已保留，可使用下方手动授权。'
  } finally { if (current()) { busy.value = ''; controller = null } }
}
function connectPassport() {
  if (!canConnect.value) return
  const id = accountId.value, selectedRole = roleId.value
  return run('passport', signal => connectCloudSklandPassport(id, selectedRole, { signal }))
}
function connectManual() {
  if (busy.value || !cred.value.trim()) return
  const bodyCred = cred.value.trim(), bodyDevice = deviceId.value.trim()
  cred.value = ''; deviceId.value = ''
  return run('manual', signal => connectCloudSkland(bodyCred, bodyDevice, { signal }))
}
const stop = subscribeSessionInvalidation(clear)
onBeforeUnmount(() => { stop(); clear() })
</script>
<template>
  <section v-if="isCloudMode()" class="cap-card cloud-skland" aria-label="森空岛档案授权">
    <h2>终末地 · 森空岛档案授权</h2>
    <p>选择本人已授权的鹰角账号与角色，一键连接森空岛档案。两类授权独立显示、分别选择角色。</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="success" role="status">{{ success }}</p>
    <form aria-label="通过鹰角授权连接森空岛" @submit.prevent="connectPassport">
      <label>来源鹰角授权<select aria-label="用于连接森空岛的鹰角授权" :value="accountId" :disabled="!!busy" @change="chooseAccount"><option value="">请选择鹰角授权</option><option v-for="(account, index) in sources" :key="account.account_id" :value="account.account_id">鹰角授权 {{ index + 1 }} · {{ account.roles?.find(item => item.is_default)?.display_name || account.roles?.[0]?.display_name || '角色名称未提供' }}</option></select></label>
      <label>来源角色<select aria-label="用于连接森空岛的鹰角角色" :value="roleId" :disabled="!!busy || !source" @change="chooseRole"><option value="">请选择已核验角色</option><option v-for="(item, index) in roles" :key="item.role_id" :value="item.role_id">{{ item.display_name || `角色 ${index + 1}` }}{{ item.is_default ? '（鹰角默认）' : '' }}</option></select></label>
      <p v-if="!sources.length">暂无可用的鹰角授权，请先完成上方鹰角登录，或使用手动授权。</p><p v-else-if="source && !roles.length">此鹰角授权尚无已核验角色，请重新授权后连接，或使用手动授权。</p>
      <button class="ui-button" :disabled="!canConnect">{{ busy === 'passport' ? '连接中…' : '一键连接森空岛档案' }}</button>
    </form>
    <details><summary>手动授权备用</summary><p>无法通过鹰角连接时，可提交森空岛 cred。凭据仅提交到云端授权中心，用后清空。</p>
      <form aria-label="手动连接森空岛" @submit.prevent="connectManual"><label>森空岛 cred<input v-model="cred" type="password" autocomplete="off" required maxlength="4096" :disabled="!!busy" /></label><label>设备标识（如需要）<input v-model="deviceId" autocomplete="off" maxlength="512" :disabled="!!busy" /></label><button class="ui-button" :disabled="!!busy || !cred.trim()">{{ busy === 'manual' ? '连接中…' : '手动连接森空岛档案' }}</button></form>
    </details>
  </section>
</template>
<style scoped>
.cloud-skland,.cloud-skland form,.cloud-skland details{display:grid;gap:14px}.cloud-skland label{display:grid;gap:7px}.cloud-skland input,.cloud-skland select{width:100%;box-sizing:border-box;min-width:0;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--card-bg);color:var(--text)}h2,p{margin:0}summary{cursor:pointer}p[role=alert]{color:var(--danger);overflow-wrap:anywhere}
</style>
