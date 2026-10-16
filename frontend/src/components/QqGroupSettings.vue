<script setup>
import { ref } from 'vue'
import { getGroupSettings, saveGroupSettings } from '../reminders-api.js'
const group = ref(''), loadedGroup = ref(''), settings = ref(null), busy = ref(false), error = ref(''), status = ref('')
const games = [{id:'wuthering_waves',name:'鸣潮'},{id:'nte',name:'异环'},{id:'endfield',name:'终末地'}]
function toggle(key, value, event) { settings.value[key] = event.target.checked ? [...new Set([...settings.value[key],value])] : settings.value[key].filter(item=>item!==value) }
async function load() {
  if (busy.value || !group.value.trim()) return
  busy.value = true; error.value = ''; status.value = ''; settings.value = null
  const id = group.value.trim()
  try { const result = await getGroupSettings(id); settings.value = result.settings; loadedGroup.value = id }
  catch (failure) { error.value = failure.message }
  finally { busy.value = false }
}
async function save() {
  if (busy.value || !settings.value) return
  busy.value = true; error.value = ''; status.value = ''
  try { await saveGroupSettings(loadedGroup.value,{...settings.value,quiet_start:settings.value.quiet_start || null,quiet_end:settings.value.quiet_end || null}); status.value = '群设置已保存。' }
  catch (failure) { error.value = failure.message }
  finally { busy.value = false }
}
</script>
<template>
  <section class="cap-card group-settings" aria-label="管理员群设置">
    <h2>管理员 · QQ 群设置</h2>
    <p>可管理允许查询的游戏、图片偏好与查询频率。</p>
    <label>QQ 群标识<input v-model="group" aria-label="QQ 群标识" maxlength="256" autocomplete="off" :disabled="busy" /></label><button class="ui-button" :disabled="busy || !group.trim()" @click="load">读取群设置</button>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="status" role="status">{{ status }}</p>
    <form v-if="settings" @submit.prevent="save"><p>正在配置所读取的群。修改群标识后，须再次读取再保存。</p>
      <fieldset><legend>允许查询的游戏</legend><label v-for="game in games" :key="game.id"><input :checked="settings.allowed_games.includes(game.id)" type="checkbox" @change="toggle('allowed_games',game.id,$event)" />{{ game.name }}</label></fieldset>
      <p>限制游戏范围后，请使用带游戏名的查询；全游戏总览会被拒绝，避免展示已关闭游戏。</p>
      <label><input v-model="settings.image_preference" type="checkbox" />使用图片回复查询结果</label>
      <label>群查询每分钟上限<input v-model.number="settings.requests_per_minute" type="number" min="1" max="60" required /></label>
      <button class="ui-button primary" :disabled="busy">保存群设置</button>
    </form>
  </section>
</template>
<style scoped>
.group-settings,form{display:grid;gap:12px}.group-settings>button,form>button{justify-self:start}h2,p{margin:0}h2{font-size:16px;font-weight:500;line-height:24px}label{display:flex;align-items:center;flex-wrap:wrap;gap:8px}fieldset{display:flex;gap:14px;flex-wrap:wrap;margin:0;padding:0;border:0;min-width:0}legend{padding:0;margin-bottom:8px;font-size:13px;font-weight:500}input{padding:8px 10px;background:var(--card-bg);color:var(--text);border:1px solid var(--border);border-radius:var(--radius-control)}input[type=number]{width:100px}
</style>
