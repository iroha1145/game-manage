import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content } from '../test-utils/vue.js'
const Ledger=await loadVue(new URL('./NteGachaLedger.vue',import.meta.url))
test('summary-only image never labels a nonempty imported ledger as empty',t=>{
 const root=mount(t,Ledger,{imageMode:true,snapshot:{total_records:10,pools:[]}})
 assert.match(content(root),/逐条记录未加载；已导入 10 条，可在网页查看/)
 assert.doesNotMatch(content(root),/暂无逐抽记录/)
})
