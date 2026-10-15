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

test('ship shows static zero percentages and stage with accessible scales and original observations',t=>{
  const root=mount(t,Reports,{payload,view:'ship'})
  assert.match(content(root),/培育室/);assert.match(content(root),/心情观测值 0/);assert.match(content(root),/信赖观测值 0/)
  assert.match(content(root),/心情 0%/);assert.match(content(root),/信赖 友好 0%/)
  assert.deepEqual(nodes(root,'progress').map(node=>[node.props.value,node.props.max]),[[0,'100'],[0,'200']])
  assert.match(content(root),/不外推当前状态/);assert.match(content(root),/查看原始观测值/)
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

test('detail return keeps roster filters and gives cached equipment its own timestamp',async t=>{
  let returned = 0, focused = 0
  const props=reactive({payload,view:'operators',fetchedAt:'2026-10-15T04:00:00Z',operatorDetailId:'',onCloseDetail:()=>{returned++;props.operatorDetailId=''}})
  const root=mount(t,Reports,props)
  nodes(root,'input')[0].props.onInput({target:{value:'干员甲'}});await nextTick()
  nodes(root,'button').find(node=>content(node)==='查看配装').props.onClick({currentTarget:{focus(){focused++}}})
  props.operatorDetailId='a';props.operatorDetail={name:'干员甲',level:0};props.operatorStale=true;props.operatorFetchedAt='2026-10-15T01:00:00Z'
  await nextTick();await nextTick()
  assert.match(content(root),/配装同步于.*09:00/)
  assert.match(content(root),/同步于.*12:00/)
  assert.match(content(root),/上次成功读取的配装/)
  nodes(root,'button').find(node=>content(node)==='← 返回全员练度').props.onClick()
  await nextTick();await nextTick()
  assert.equal(returned,1);assert.equal(focused,1)
  assert.equal(nodes(root,'input')[0].props.value,'干员甲')
  assert.match(content(root),/显示 1 \/ 2 名/)
  assert.doesNotMatch(content(root),/配装同步于/)
})

test('missing detail time is unknown and never borrows the profile fetch time',t=>{
  const root=mount(t,Reports,{payload,view:'detail',fetchedAt:'2026-10-15T04:00:00Z',operatorDetailId:'a',operatorDetail:{name:'干员甲'}})
  assert.match(content(root),/配装同步于 未知/)
  assert.match(content(root),/来源未提供独立更新时间/)
})

test('honor displays the whole supplied medal list and preserves zero and unknown fields',t=>{
  const items=Array.from({length:12},(_,i)=>({id:`m${i}`,name:`奖章${i}`,level:i===0?0:null,is_plated:i===0?false:i===1?true:null,obtained_at:i===0?'2026-10-15T00:00:00Z':null}))
  const root=mount(t,Reports,{payload:{report:{schema_version:1,honor:{available:true,summary:{declared_count:30,listed_count:12},items}}},view:'honor'})
  assert.match(content(root),/来源成就总数 30/);assert.match(content(root),/已记录奖章 12/)
  assert.match(content(root),/奖章11/);assert.match(content(root),/等级 0 未镀层/)
  assert.match(content(root),/已镀层/);assert.match(content(root),/获得于.*08:00/)
  assert.match(content(root),/镀层未知/);assert.match(content(root),/获得于 未知/)
  assert.doesNotMatch(content(root),/100%|30 \/ 30/)
})

test('known empty officer list is different from missing assignment data',t=>{
  const root=mount(t,Reports,{payload:{report:{schema_version:1,regions:{items:[{settlements:[{name:'空据点',officers:[],officers_available:true},{name:'未知据点',officers:[],officers_available:false}]}]}}},view:'regions'})
  assert.match(content(root),/派驻干员：无派驻/);assert.match(content(root),/派驻干员：未提供/)
})

test('ship keeps unsupported values visible and independent observation/fetch dates',t=>{
  const root=mount(t,Reports,{view:'ship',fetchedAt:'2026-10-15T01:00:00Z',payload:{observed_at:'2025-12-31T00:00:00Z',ship:[{operators:[{name:'越界样本',physicalStrength:8640000,favorability:null}]},{name:'空舱',operators_available:true,operators:[]},{name:'未知舱',operators:[]}]}})
  assert.match(content(root),/心情 未知/);assert.match(content(root),/心情观测值 8640000/)
  assert.match(content(root),/信赖 阶段未知 未知/);assert.equal(nodes(root,'progress').length,0)
  assert.match(content(root),/游戏观测于 2025-12-31 08:00.*抓取于 2026-10-15 09:00/)
  assert.match(content(root),/当前没有驻守干员记录/);assert.match(content(root),/尚未采集驻守干员资料/)
})

test('overview exposes observed main mission and only confirms full stamina with a known positive limit',t=>{
  for(const [current,maximum,full] of [[240,240,true],[250,240,true],[0,0,false],[0,null,false],[null,240,false]]){
    const root=mount(t,Reports,{view:'overview',payload:{base:{main_mission:'第三章 · 合成任务'},stamina:{current,maximum}}})
    assert.match(content(root),/主线进度 第三章 · 合成任务/)
    assert.equal(content(root).includes('该次观测理智已满'),full)
    if(full)assert.doesNotMatch(content(root),/预计回满/)
  }
})

test('honor category, search and time controls keep totals and distinguish no results from no data',async t=>{
  const items=[{id:'a',name:'探索甲',category:'探索',obtained_at:'2025-10-15T00:00:00Z'},{id:'b',name:'探索乙',category:'探索',obtained_at:'2026-10-15T00:00:00Z'},{id:'c',name:'战斗甲',category:'战斗'},{id:'u',name:'未分类奖章',category:null}]
  const root=mount(t,Reports,{view:'honor',payload:{report:{schema_version:1,honor:{available:true,items,summary:{declared_count:99,listed_count:4}}}}})
  const headings=()=>nodes(root,'h3').map(content)
  assert.deepEqual(headings(),['探索乙','探索甲','战斗甲','未分类奖章'])
  nodes(root,'select')[1].props['onUpdate:modelValue']('oldest');await nextTick()
  assert.deepEqual(headings(),['探索甲','探索乙','战斗甲','未分类奖章'])
  nodes(root,'select')[0].props['onUpdate:modelValue']('"探索"');nodes(root,'input')[0].props.onInput({target:{value:'甲'}});await nextTick()
  assert.deepEqual(headings(),['探索甲']);assert.match(content(root),/显示 1 \/ 4/);assert.match(content(root),/来源成就总数 99/)
  assert.match(content(root),/获得于 2025-10-15 08:00/)
  nodes(root,'input')[0].props.onInput({target:{value:'不存在'}});await nextTick()
  assert.match(content(root),/没有匹配的奖章/);assert.doesNotMatch(content(root),/当前档案没有奖章记录/)
  nodes(root,'button').find(node=>content(node)==='清除奖章筛选').props.onClick();await nextTick()
  assert.equal(headings().length,4)
  nodes(root,'select')[0].props['onUpdate:modelValue']('null');await nextTick()
  assert.deepEqual(headings(),['未分类奖章'])
})

test('legacy regional collections use the observed game labels',t=>{
  const root=mount(t,Reports,{view:'regions',payload:{regions:[{levels:[{id:'map01_lv001',puzzles:{count:0}}]}]}})
  for(const label of ['醚质','宝箱','装备制造模板','维修灵感点','协议采录桩'])assert.ok(content(root).includes(label))
  assert.doesNotMatch(content(root),/谜质|储藏箱|装备箱|片段|黑盒/)
})
