<script setup>
import MenuSelect from './MenuSelect.vue'
import { ref } from 'vue'
import { useWuwaRequest } from '../wuwa-api.js'
import { gachaReason } from '../wuwa-gacha.js'
const props = defineProps({ accountKey:{type:String,default:''} })
const emit = defineEmits(['imported'])
const source=ref('json_import'),file=ref(null),fileInput=ref(null),preview=ref(null),error=ref(''),busy=ref(false)
const latest=ref(false),continuous=ref(false),pool=ref('1'),hard=ref(''),version=ref(''),ruleOpen=ref(false)
let generation=0
const request=useWuwaRequest(()=>props.accountKey,()=>{generation++;file.value=null;preview.value=null;if(fileInput.value)fileInput.value.value='';error.value='';busy.value=false})
function invalidate(){generation++;preview.value=null}
async function readFile(){
  if(!file.value || busy.value)return
  const f=file.value,gen=++generation
  error.value='';busy.value=true;preview.value=null
  try{
    if(f.size>2*1024*1024)throw Error('文件最大 2 MiB')
    const parsed=JSON.parse(await f.text())
    if(gen!==generation)return
    preview.value=await request.run('gacha/preview',{records:parsed,source:source.value,
      latest_confirmed:latest.value,continuity_confirmed:continuous.value})
  }catch(e){if(gen===generation)error.value=e.message || '文件格式无效'}
  finally{if(gen===generation)busy.value=false}
}
async function commit(){
  if(!preview.value || busy.value)return
  busy.value=true;error.value=''
  try{const result=await request.run('gacha/import',{preview_id:preview.value.preview_id});if(result){invalidate();emit('imported',result)}}
  catch(e){error.value=e.message;preview.value=null}finally{busy.value=false}
}
async function saveRule(){
  busy.value=true;error.value=''
  try{const result=await request.run('gacha/rules',{pool:pool.value,hard_pity:Number(hard.value),reset_rarity:'5',
    version:version.value,sharing:'independent',basis:'user_configured'});if(result)emit('imported',null)}
  catch(e){error.value=e.message}finally{busy.value=false}
}
async function backup(){
  busy.value=true;error.value=''
  try{
    let offset=0,next
    do{
      const archive=await request.run(`gacha/export?limit=2000&offset=${offset}`);if(!archive)return
      const url=URL.createObjectURL(new Blob([JSON.stringify(archive)],{type:'application/json'}))
      const a=globalThis.document.createElement('a');a.href=url;a.download=`wuwa-gacha-${offset}.json`;a.click();URL.revokeObjectURL(url)
      next=archive.export_page?.next_offset;offset=next
    }while(next!=null)
  }catch(e){error.value=e.message}finally{busy.value=false}
}
</script>
<template>
  <div class="wuwa-import-body">
    <p v-if="busy" class="wuwa-meta" role="status">正在读取 / 预览 / 提交，请稍候…</p>
    <div class="toolbar wuwa-import-row">
      <label>文件来源 <MenuSelect class="import-source-menu" label="文件来源" v-model="source" :disabled="busy" :options="[{value:'json_import',label:'逐抽记录 / 归档文件'},{value:'mcgf',label:'mcgf 五星汇总'},{value:'xhh',label:'xhh 五星汇总'}]" @change="invalidate" /></label>
      <input ref="fileInput" type="file" accept=".json,application/json" aria-label="预览抽卡文件" :disabled="busy" @change="file=$event.target.files?.[0];invalidate()" />
      <button class="ui-button small-button" :disabled="busy || !file" @click="readFile">预览文件</button>
    </div>
    <p class="wuwa-meta">单文件上限 2 MB。mcgf/xhh 仅导入五星汇总，不含逐抽明细。</p>
    <div v-if="source==='json_import'" class="toolbar">
      <label><input v-model="latest" type="checkbox" :disabled="busy" @change="invalidate" />包含最新抽卡记录</label>
      <label><input v-model="continuous" type="checkbox" :disabled="busy" @change="invalidate" />记录连续无遗漏</label>
    </div>
    <div v-if="preview" class="wuwa-notice">
      <p>{{ preview.import_kind==='aggregate'?'五星汇总':preview.import_kind==='archive'?'逐抽与汇总归档':'逐抽记录' }} · 收到 {{ preview.received }} 条 · 新增 {{ preview.new_records }} 条 · 重复 {{ preview.duplicates }} 条</p>
      <p>{{ preview.message }}</p><p>{{ preview.diagnostics?.map(gachaReason).join('、') }}</p>
      <button class="ui-button small-button primary" :disabled="busy" @click="commit">确认导入本次预览</button>
    </div>
    <button class="ui-button small-button" :disabled="busy" @click="backup">导出归档</button>
    <details :open="ruleOpen" @toggle="ruleOpen=$event.target.open">
      <summary>用户规则配置</summary>
      <form class="toolbar" @submit.prevent="saveRule">
        <input v-model="pool" aria-label="规则卡池 ID" required placeholder="卡池 ID" />
        <input v-model="hard" aria-label="用户设置保底上限" type="number" min="1" max="10000" required placeholder="保底上限" />
        <input v-model="version" aria-label="用户规则版本或依据" maxlength="512" required placeholder="规则版本 / 依据说明" />
        <button class="ui-button small-button" :disabled="busy">保存独立卡池规则</button>
      </form>
    </details>
    <p v-if="error" class="wuwa-error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.import-source-menu { max-width:100%; min-width:0; }
.import-source-menu :deep(.menu-select-trigger) { min-width:0; min-height:36px; max-width:100%; }
</style>
