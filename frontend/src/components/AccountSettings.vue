<script setup>
import MenuSelect from './MenuSelect.vue'
import { ref } from 'vue'
import { setDefaultRole, revokeAuthorization, providerName } from '../accounts-api.js'
import QqGroupSettings from './QqGroupSettings.vue'
const props = defineProps({ accounts: { type: Array, default: () => [] }, isAdmin: { type: Boolean, default: false } })
const emit = defineEmits(['changed'])
const busy = ref(''), error = ref('')
const labels = { active: '已授权', connected: '已授权', expired: '授权失效', revoked: '授权已撤销', configured: '已配置', unconfigured: '未授权', credential_unavailable: '授权凭据不可用', role_unavailable: '角色不在当前授权范围' }
async function action(id, run) { if (busy.value) return; busy.value = id; error.value = ''; try { await run(); emit('changed', id) } catch (failure) { if (failure.name !== 'AbortError') error.value = failure.message } finally { busy.value = '' } }
const chooseRole = (account, value) => account.state === 'active' ? action(account.account_id, () => setDefaultRole(account.account_id, value)) : undefined
const channelName = account => ({ official: '官服', bilibili: 'B 服' })[account.channel] || '渠道未提供'
const revoke = account => action(account.account_id, () => revokeAuthorization(account.account_id))
function sklandSource(account) {
  if (account.authorization_source === 'manual') return '来源：手动凭据'
  if (account.authorization_source !== 'passport') return '来源未提供'
  const parent = props.accounts.find(item => item.account_id === account.parent_account_id && item.provider === 'hypergryph')
  const role = parent?.roles?.find(item => item.role_id === account.parent_role_id)
  return `来源：鹰角授权 · ${role?.display_name || '角色未提供'}${parent?.state?.startsWith('revoked') ? '（已撤销）' : ''}`
}
</script>
<template>
  <section class="cloud-account-settings" aria-label="本人游戏授权">
    <h2>游戏授权与默认角色</h2>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="!accounts.length">尚未关联游戏账号，请在下方登录。</p>
    <article v-for="account in accounts" :key="account.account_id" class="cap-card">
      <header><h3>{{ providerName(account) }}</h3><span>{{ labels[account.state] || '状态未知' }}</span></header>
      <p v-if="account.provider === 'hypergryph'">游戏渠道：{{ channelName(account) }}</p>
      <p v-if="account.provider === 'skland'">{{ sklandSource(account) }}</p>
      <label>默认角色<MenuSelect class="account-role-menu" label="默认角色" :model-value="account.roles?.find(role => role.is_default)?.role_id || ''" :disabled="!!busy || account.state !== 'active'" :options="(account.roles || []).map((role,index) => ({value:role.role_id,label:role.display_name || `角色 ${index + 1}`}))" @change="chooseRole(account, $event)" /></label>
      <button class="ui-button" :disabled="!!busy || account.state === 'revoked'" @click="revoke(account)">撤销这项游戏授权</button>
      <!-- Site reminders are temporarily hidden; server rules and inbox data remain intact. -->
    </article>
    <QqGroupSettings v-if="isAdmin" />
  </section>
</template>
<style scoped>
.cloud-account-settings{display:grid;gap:14px}.cloud-account-settings header{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}.cloud-account-settings header span{font-size:12px;color:var(--text-muted)}.cloud-account-settings article{display:grid;gap:12px}.cloud-account-settings article>button{justify-self:start}.cloud-account-settings label{display:grid;gap:8px;font-size:13px;font-weight:500}.account-role-menu{width:100%;min-width:0}.account-role-menu :deep(.menu-select-trigger){width:100%;min-width:0;min-height:40px;font-weight:400}h2,p{margin:0}h2{font-size:16px;font-weight:500;line-height:24px}h3{font-size:14px;font-weight:500}
</style>
