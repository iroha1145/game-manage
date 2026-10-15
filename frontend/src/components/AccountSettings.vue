<script setup>
import { ref } from 'vue'
import { setDefaultRole, revokeAuthorization, providerName } from '../accounts-api.js'
const props = defineProps({ accounts: { type: Array, default: () => [] } })
const emit = defineEmits(['changed'])
const busy = ref(''), error = ref('')
const labels = { active: '已授权', connected: '已授权', expired: '授权失效', revoked: '授权已撤销', configured: '已配置', unconfigured: '未授权' }
async function action(id, run) { if (busy.value) return; busy.value = id; error.value = ''; try { await run(); emit('changed', id) } catch (failure) { if (failure.name !== 'AbortError') error.value = failure.message } finally { busy.value = '' } }
const chooseRole = (account, event) => action(account.account_id, () => setDefaultRole(account.account_id, event.target.value))
const revoke = account => action(account.account_id, () => revokeAuthorization(account.account_id))
</script>
<template>
  <section class="cloud-account-settings" aria-label="本人游戏授权">
    <h2>游戏授权与默认角色</h2><p>终末地的鹰角寻访和森空岛档案分别授权、分别选择角色。</p>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="!accounts.length">尚未关联游戏账号，请使用下方社区授权。</p>
    <article v-for="account in accounts" :key="account.account_id" class="cap-card">
      <header><h3>{{ providerName(account) }}</h3><span>{{ labels[account.state] || '状态未知' }}</span></header>
      <label>默认角色<select :value="account.roles?.find(role => role.is_default)?.role_id || ''" :disabled="!!busy || account.state === 'revoked'" @change="chooseRole(account, $event)"><option v-for="(role, index) in account.roles || []" :key="role.role_id" :value="role.role_id">{{ role.display_name || `角色 ${index + 1}` }}</option></select></label>
      <button class="ui-button" :disabled="!!busy || account.state === 'revoked'" @click="revoke(account)">撤销这项游戏授权</button>
    </article>
  </section>
</template>
<style scoped>
.cloud-account-settings{display:grid;gap:14px}.cloud-account-settings header{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}.cloud-account-settings article{display:grid;gap:12px}.cloud-account-settings label{display:grid;gap:8px}select{max-width:100%;padding:10px;border-radius:8px;background:var(--card-bg);color:var(--text);border:1px solid var(--border)}h2,h3,p{margin:0}
</style>
