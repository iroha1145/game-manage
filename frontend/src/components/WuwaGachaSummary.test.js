import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
const WuwaGacha = await loadVue(new URL('./WuwaGacha.vue', import.meta.url))
test('shared image view shows separated source summaries and unknown UP without any API request', async t => {
  let requests=0
  const before=globalThis.fetch
  globalThis.fetch=()=>{requests++;throw Error('image must not fetch')}
  t.after(()=>{globalThis.fetch=before})
  const root=mount(t,WuwaGacha,{imageMode:true,snapshot:{total:3,gold_total:1,items:[],gold:[],limit:50,offset:0,
    coverage:{segment_count:2,complete:false},pools:[{pool:'1',name:'角色池',total:3,
      pity:{status:'exact',count:0,rule_basis:'user_configured',rule_version:'personal',hard_pity_remaining:70,up_guarantee:'unknown'}}],
    aggregates:{total:1,items:[{kind:'five_star_summary',pool:'99',name:'来源五星',period_count:120,source:'mcgf'}],message:'不计入逐抽'}}})
  assert.match(content(root),/当前垫抽 0/)
  assert.match(content(root),/UP 保证未知/)
  assert.match(content(root),/来源自报五星周期抽数 120/)
  assert.match(content(root),/已导入记录/)
  assert.doesNotMatch(content(root),/来源片段|缺少判断依据|QQ 页码|来源 Unix/)
  assert.equal(nodes(root,'input').length,0)
  await Promise.resolve()
  assert.equal(requests,0)
})
