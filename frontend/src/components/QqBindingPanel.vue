<script setup>
import { onMounted,onBeforeUnmount,ref } from 'vue'
import { subscribeSessionInvalidation } from '../http-client.js'
import { generateQqLinkCode,listQqLinks,unlinkQqLink } from '../qq-api.js'
import { displayBeijing } from '../time.js'
const code=ref(''),expires=ref(''),links=ref([]),busy=ref(false),error=ref(''),copied=ref(false)
let generation=0,disposed=false
function clear(){generation++;code.value='';expires.value='';links.value=[];copied.value=false;error.value=''}
const unsubscribe=subscribeSessionInvalidation(clear)
async function run(action){if(busy.value)return;busy.value=true;error.value='';const current=generation;try{await action()}catch(e){if(!disposed&&current===generation&&e.name!=='AbortError')error.value=e.message}finally{if(!disposed)busy.value=false}}
async function load(){const current=generation;const data=await listQqLinks();if(!disposed&&current===generation)links.value=data.links||[]}
async function generate(){await run(async()=>{const current=generation;const data=await generateQqLinkCode();if(disposed||current!==generation)return;code.value=data.code;expires.value=data.expires_at;copied.value=false;await load()})}
async function copy(){await run(async()=>{const current=generation;try{await navigator.clipboard.writeText(`绑定 ${code.value}`)}catch{throw new Error('无法自动复制，请手动复制绑定指令')}if(!disposed&&current===generation)copied.value=true})}
async function unlink(link){await run(async()=>{const current=generation;await unlinkQqLink(link.link_id);if(!disposed&&current===generation)await load()})}
onMounted(()=>run(load))
onBeforeUnmount(()=>{disposed=true;clear();unsubscribe()})
</script>
<template>
  <section class="cap-card qq-binding"><h2>QQ 绑定</h2>
    <p>生成一次性码，在认可的群内 @机器人发送下方绑定指令。QQ 回复「绑定成功」即完成，无需回填回执。</p>
    <p>绑定码有效 2 分钟，仅可使用一次。不要提前分享绑定码，公开群内其他成员可能抢先使用。更换绑定码会使旧码失效。</p>
    <div class="qq-controls"><button class="ui-button" :disabled="busy" @click="generate">生成或更换绑定码</button><button class="ui-button" :disabled="busy" @click="run(load)">刷新已关联身份</button></div>
    <div v-if="code" class="qq-command"><code>绑定 {{ code }}</code><button class="ui-button" :disabled="busy" @click="copy">复制绑定指令</button><span v-if="copied" role="status">已复制</span><p>到期 {{ displayBeijing(expires) }}</p></div>
    <p v-if="error" role="alert">{{ error }}</p>
    <article v-for="(link, index) in links" :key="link.link_id"><h3>已关联 · {{ link.identity.scene === 'group' ? '群聊' : '私聊' }} {{ index + 1 }}</h3><details><summary>查看绑定标识</summary><p>群标识：{{ link.identity.group_openid || '无' }} · 发送者：{{ link.identity.sender_openid }}</p></details><button class="ui-button" :disabled="busy" @click="unlink(link)">解除关联</button></article>
    <p v-if="!links.length">尚无已关联的 QQ 身份。解除关联后立即禁止该身份查询私人数据。</p>
  </section>
</template>
<style scoped>
.qq-binding{display:grid;gap:12px;min-width:0}.qq-binding p,.qq-binding code{overflow-wrap:anywhere}.qq-controls,.qq-command{display:flex;flex-wrap:wrap;align-items:center;gap:8px}.qq-command p{flex-basis:100%;margin:0}.qq-binding article{border-top:1px solid var(--border);padding-top:12px}
</style>
