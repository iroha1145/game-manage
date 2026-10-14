<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { loginSite, registerSite } from '../identity-api.js'
const emit = defineEmits(['authenticated'])
const registering = ref(false), username = ref(''), password = ref(''), invite = ref(''), error = ref(''), busy = ref(false)
let disposed = false
onBeforeUnmount(() => { disposed = true; password.value = ''; invite.value = '' })
async function submit() {
  if (busy.value) return
  busy.value = true; error.value = ''
  const body = { username: username.value.trim(), password: password.value, invite: invite.value.trim() }
  try { const user = await (registering.value ? registerSite(body) : loginSite(body)); if (!disposed) emit('authenticated', user) }
  catch (failure) { if (!disposed && failure.name !== 'AbortError') error.value = failure.status === 401 ? '用户名或密码不正确' : failure.message }
  finally { password.value = ''; invite.value = ''; if (!disposed) busy.value = false }
}
</script>
<template>
  <section class="site-login cap-card">
    <p class="eyebrow">游戏管家 · 云端个人空间</p><h1>{{ registering ? '邀请注册' : '网站登录' }}</h1>
    <p>使用网站账号访问本人游戏数据。游戏社区授权在登录后管理。</p>
    <form @submit.prevent="submit">
      <label>用户名<input name="username" v-model="username" autocomplete="username" required maxlength="64" /></label>
      <small v-if="registering">用户名为 3–64 位英文字母、数字、下划线（_）、点（.）或短横线（-）。</small>
      <label>网站密码<input name="password" v-model="password" type="password" :autocomplete="registering ? 'new-password' : 'current-password'" required :minlength="registering ? 12 : 1" maxlength="128" /></label>
      <label v-if="registering">邀请码<input name="invite" v-model="invite" autocomplete="off" required maxlength="128" /></label>
      <p v-if="error" role="alert">{{ error }}</p>
      <button class="ui-button" :disabled="busy">{{ busy ? '正在验证…' : registering ? '注册并登录' : '登录' }}</button>
    </form>
    <button type="button" class="text-link" :disabled="busy" @click="registering = !registering; error = ''; password = ''; invite = ''">{{ registering ? '已有网站账号，去登录' : '使用邀请码注册' }}</button>
  </section>
</template>
<style scoped>
.site-login{width:min(100%,420px);margin:8vh auto;display:grid;gap:18px}.site-login form{display:grid;gap:14px}.site-login label{display:grid;gap:7px}.site-login input{width:100%;min-width:0;box-sizing:border-box;padding:11px;border:1px solid var(--border);border-radius:8px;background:var(--input-bg);color:var(--text)}h1,p{margin:0}p{line-height:1.6}p[role=alert]{color:var(--danger)}
</style>
