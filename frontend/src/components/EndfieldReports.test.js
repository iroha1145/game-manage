import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { configureHttpClient, setAccountScope } from '../http-client.js'
const Reports=await loadVue(new URL('./EndfieldReports.vue',import.meta.url))
const Dashboard=await loadVue(new URL('./EndfieldDashboard.vue',import.meta.url))
const tick=async()=>{await new Promise(resolve=>setImmediate(resolve));await nextTick()}
const payload={report:{schema_version:1,observed_at:'2026-10-15T00:00:00Z',overview:{base:{name:'合成管理员',level:42},stamina:{current:0,maximum:240},progress:[{id:'daily',name:'每日任务',cur:0,total:100,remaining:100}],todos:[{id:'daily',name:'每日任务',remaining:100}]},
  training:{summary:{listed_count:2,declared_count:3,known_levels:1,average_level:0,max_level:0,rarity_counts:{6:1},phase_counts:{0:1}},items:[{id:'a',name:'干员甲',level:0,rarity:6,profession:'近卫',potential:0},{id:'b',name:'干员乙',rarity:5,profession:'先锋'}]},
  regions:{items:[{id:'r',name:'四号谷地',level:0,money:{current:0,total:null},settlements:[{id:'s',name:'矿区据点',coupon:{current:0,total:100},officers:[{id:'a',name:'干员甲'}]}],areas:[{name:'矿区',collections:[{key:'chests',label:'储藏箱',current:0,total:5,remaining:5,percent:0}]}]}]},
  ship:{summary:{room_count:1,staffed_rooms:1,operator_slots:1},rooms:[{id:'room',name:'培育室',level:0,operators:[{id:'a',name:'干员甲',mood_raw:0,trust_raw:0}]}]}}}

test('overview shows only backend-known todos and keeps source observation time separate', t=>{
  const root=mount(t,Reports,{payload,view:'overview',fetchedAt:'2026-10-15T01:00:00Z',stale:true})
  assert.match(content(root),/合成管理员/);assert.match(content(root),/理智 0 \/ 240/)
  assert.match(content(root),/每日任务 还需 100/);assert.match(content(root),/观测于.*08:00/);assert.match(content(root),/同步于.*09:00/)
  assert.doesNotMatch(content(root),/所有任务已完成|实时/)
})

test('roster filters without losing source totals and exposes an on-demand detail action', async t=>{
  const seen=[];const root=mount(t,Reports,{payload,view:'operators',onInspect:id=>seen.push(id)})
  assert.match(content(root),/已记录干员 2/);assert.match(content(root),/来源干员数 3/);assert.match(content(root),/已知等级均值 0/)
  nodes(root,'input')[0].props.onInput({target:{value:'干员甲'}});await nextTick()
  assert.match(content(root),/显示 1 \/ 2 名/);assert.doesNotMatch(content(root),/干员乙/)
  nodes(root,'button').find(node=>content(node)==='查看配装').props.onClick();assert.deepEqual(seen,['a'])
})

test('regions distinguish unknown limits and show settlements, assignment and remaining collections',t=>{
  const root=mount(t,Reports,{payload,view:'regions'})
  assert.match(content(root),/地区调度券 0 \/ 未知/);assert.match(content(root),/矿区据点/);assert.match(content(root),/派驻干员：干员甲/)
  assert.match(content(root),/储藏箱 0 \/ 5.*剩余 5/)
  assert.equal(nodes(root,'progress').length,1)
})

test('ship preserves raw zero mood and trust without deriving a percent',t=>{
  const root=mount(t,Reports,{payload,view:'ship'})
  assert.match(content(root),/培育室/);assert.match(content(root),/心情观测值 0/);assert.match(content(root),/信赖观测值 0/)
  assert.doesNotMatch(content(root),/0%|实时预测/)
})

test('missing collection metadata stays unknown and fetched time does not become game observation time',t=>{
  const old={stamina:{updated_at:'2026-10-15T01:00:00Z'},operators:[],regions:[],ship:[]}
  const overview=mount(t,Reports,{payload:old,view:'overview',fetchedAt:'2026-10-15T01:00:00Z'})
  assert.match(content(overview),/观测于 未知/);assert.match(content(overview),/同步于.*09:00/)
  assert.match(content(overview),/已记录干员 未知/);assert.match(content(overview),/建设地区 未知/)
  const regions=mount(t,Reports,{payload:{report:{schema_version:1,regions:{items:[{name:'未采集据点的地区',settlements:[],settlements_available:false}]}}},view:'regions'})
  assert.match(content(regions),/据点 未知/);assert.doesNotMatch(content(regions),/据点 0/)
})

test('cloud reports consume the selected snapshot without extra profile collection and clear after owner changes',async t=>{
  configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}));setAccountScope({user_id:'u',account_id:'a',role_id:'r',provider:'skland'})
  const calls=[];t.mock.method(globalThis,'fetch',async path=>{calls.push(path);return new Response(JSON.stringify({supported:false}))})
  const props=reactive({cloudAccount:{account_id:'a',provider:'skland',roles:[{role_id:'r',display_name:'角色甲'}]},cloudRole:'r',snaps:{account:{payload}},initialSection:'regions'})
  const root=mount(t,Dashboard,props);await tick()
  assert.match(content(root),/四号谷地/);assert.equal(calls.length,0)
  props.cloudRole='other';await tick();assert.doesNotMatch(content(root),/四号谷地|合成管理员/)
  props.snaps={account:{payload:{report:{schema_version:1,regions:{items:[{name:'新地区'}]}}}}};await tick()
  assert.match(content(root),/新地区/)
})
