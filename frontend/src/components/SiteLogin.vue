<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { loginSite, registerSite } from '../identity-api.js'
import AppIcon from './AppIcon.vue'
import GameArt from './GameArt.vue'
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
  <section class="site-login">
    <div class="site-login-art">
      <GameArt variant="orbit" />
      <span class="site-login-mark" aria-hidden="true"><AppIcon name="spark" :size="22" /></span>
      <p class="site-login-games">鸣潮 · 异环 · 终末地</p>
    </div>
    <div class="site-login-panel">
      <p class="eyebrow">游戏管家</p><h1>{{ registering ? '邀请注册' : '网站登录' }}</h1>
      <form @submit.prevent="submit">
        <label>用户名<input name="username" v-model="username" autocomplete="username" required maxlength="64" /></label>
        <small v-if="registering">用户名为 3–64 位英文字母、数字、下划线（_）、点（.）或短横线（-）。</small>
        <label>网站密码<input name="password" v-model="password" type="password" :autocomplete="registering ? 'new-password' : 'current-password'" required :minlength="registering ? 12 : 1" maxlength="128" /></label>
        <label v-if="registering">邀请码<input name="invite" v-model="invite" autocomplete="off" required maxlength="128" /></label>
        <p v-if="error" role="alert">{{ error }}</p>
        <button class="ui-button primary" :disabled="busy">{{ busy ? '正在验证…' : registering ? '注册并登录' : '登录' }}</button>
      </form>
      <button type="button" class="text-link" :disabled="busy" @click="registering = !registering; error = ''; password = ''; invite = ''">{{ registering ? '已有网站账号，去登录' : '使用邀请码注册' }}</button>
    </div>
  </section>
</template>
<style scoped>
/* A dark stage with the orbit artwork beside the form, on one white card. */
.site-login{width:min(100%,900px);margin:7vh auto;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,420px);overflow:hidden;border:1px solid var(--card-border);border-radius:var(--radius-shell);background:var(--card-bg);box-shadow:var(--card-hover-shadow)}
.site-login-art{position:relative;isolation:isolate;display:flex;flex-direction:column;justify-content:space-between;min-height:460px;padding:30px;overflow:hidden;color:#fff;background:radial-gradient(120% 140% at 0% 0%,#2a2f4d 0%,#151827 46%,#0f111a 100%)}
.site-login-art :deep(.game-art){z-index:-1}
.site-login-mark{display:grid;place-items:center;width:46px;height:46px;border-radius:15px;background:linear-gradient(140deg,#8b7bff,#4f46e5 55%,#7c3aed);box-shadow:0 10px 24px -12px rgba(79,70,229,.9),inset 0 1px 0 rgba(255,255,255,.25)}
.site-login-games{margin:0;font-size:24px;font-weight:600;line-height:32px;letter-spacing:-.02em}
.site-login-panel{display:grid;align-content:center;gap:18px;padding:44px 40px}
.site-login form{display:grid;gap:14px}.site-login label{display:grid;gap:7px;font-size:13px;font-weight:500}
.site-login input{width:100%;min-width:0;min-height:44px;box-sizing:border-box;padding:10px 14px;border:1px solid var(--border);border-radius:var(--radius-control);background:var(--card-bg);box-shadow:var(--btn-shadow);color:var(--text);font-weight:400}
.site-login input:focus-visible{border-color:var(--accent);outline:none;box-shadow:var(--ring)}
.site-login .ui-button.primary{min-height:44px;margin-top:4px}
h1,p{margin:0}h1{font-size:28px;font-weight:600;line-height:36px;letter-spacing:-.02em}p{line-height:1.6}small{font-size:12px;color:var(--text-muted)}p[role=alert]{color:var(--danger);font-size:13px}
.site-login .text-link{justify-self:start}
@media(max-width:760px){.site-login{grid-template-columns:1fr;margin:3vh auto}.site-login-art{min-height:200px;padding:22px}.site-login-games{font-size:20px;line-height:28px}.site-login-panel{padding:28px 22px}}
</style>
