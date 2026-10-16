import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue,mount,content,nodes } from '../test-utils/vue.js'
import { configureHttpClient,setAccountScope } from '../http-client.js'
const Dashboard=await loadVue(new URL('./EndfieldDashboard.vue',import.meta.url))
const Card=await loadVue(new URL('./GameCard.vue',import.meta.url))
const CloudCard=await loadVue(new URL('./CloudGameCard.vue',import.meta.url))
const CloudDetails=await loadVue(new URL('./CloudAccountDetails.vue',import.meta.url))
const flush=async()=>{await new Promise(setImmediate);await nextTick()}
const button=(root,label)=>nodes(root,'button').find(n=>content(n)===label)
const response=value=>new Response(JSON.stringify(value))
const fetched_at='2026-10-15T01:02:00Z'
const observed={kind:'war',fetched_at,records:[{name:'已有战争资料',stars:0,weeks:[]}]}
const status={connected:true,roles:[{role_id:'a',server_id:'1'},{role_id:'b',server_id:'1'}],selected_role_id:'a',selected_server_id:'1'}
test('Dashboard reread retains same-category data and original time after transport failure, then replaces it with successful empty data',async t=>{
 let mode='normal', calls=0
 t.mock.method(globalThis,'fetch',async url=>{
  if(url.endsWith('/status'))return response(status)
  if(url.includes('/challenges')){calls++;if(mode==='fail')throw new Error('合成网络失败');return response(mode==='empty'?{kind:'war',fetched_at:'2026-10-15T04:05:00Z',records:[]}:observed)}
  return response({})
 })
 const root=mount(t,Dashboard,{initialSection:'challenges'});await flush();await flush()
 assert.match(content(root),/已有战争资料/);mode='fail'
 await button(root,'重新读取战争').props.onClick();await flush()
 assert.match(content(root),/已有资料待更新.*暂时无法连接服务.*上次成功资料/);assert.match(content(root),/2026-10-15 09:02/);assert.match(content(root),/已有战争资料/)
 mode='empty';await button(root,'重新读取战争').props.onClick();await flush()
 assert.match(content(root),/2026-10-15 12:05/);assert.match(content(root),/本次返回没有战争记录/);assert.doesNotMatch(content(root),/已有战争资料|已有资料待更新/);assert.equal(calls,3)
})
test('Dashboard category and role switches invalidate late challenge results',async t=>{
 let finishWar,finishMonument,currentStatus=status
 t.mock.method(globalThis,'fetch',async url=>{
  if(url.endsWith('/status'))return response(currentStatus)
  if(url.endsWith('/role')){currentStatus={...status,selected_role_id:'b'};return response(currentStatus)}
  if(url.endsWith('kind=war'))return new Promise(resolve=>{finishWar=()=>resolve(response(observed))})
  if(url.endsWith('kind=monument'))return new Promise(resolve=>{finishMonument=()=>resolve(response({...observed,kind:'monument',records:[{name:'迟到丰碑'}]}))})
  return response({})
 })
 const root=mount(t,Dashboard,{initialSection:'challenges'});await flush();await flush()
 button(root,'丰碑').props.onClick();await flush();finishWar();await flush()
 assert.doesNotMatch(content(root),/已有战争资料/)
 const oldRole=finishMonument
 nodes(root,'select')[0].props.onChange({target:{value:'b:1'}});await flush()
 oldRole();await flush();assert.doesNotMatch(content(root),/已有战争资料|迟到丰碑/)
})
test('Dashboard first challenge failure is not rendered as an empty success',async t=>{
 t.mock.method(globalThis,'fetch',async url=>{if(url.endsWith('/status'))return response(status);if(url.includes('/challenges'))throw new Error('首次失败');return response({})})
 const root=mount(t,Dashboard,{initialSection:'challenges'});await flush();await flush()
 assert.match(content(root),/暂时无法连接服务.*尚无可显示的已采集资料/);assert.doesNotMatch(content(root),/暂无挑战记录|本次返回没有战争记录/)
})
const game={game_id:'endfield',display_name:'终末地',credentials_configured:true,capabilities:['account','gacha']}
const account={payload:{schema_version:1,role_id:'p',nickname:'鹰角甲'}}
const gacha={fetched_at,stale:true,payload:{schema_version:1,role_id:'p',total:123,report:{schema_version:1,role_id:'p',total:123,six_star:0,five_star:2,free:0,pending:true},pools:[]}}
test('formal GameCard overview passes local auth gate, keeps Eagle identity separate and forwards original refresh/detail',async t=>{
 t.mock.method(globalThis,'fetch',async()=>response({connected:false,roles:[]}))
 let refresh=0
 const props=reactive({game,externalSnapshots:{account,gacha},authAccount:{configured:true,state:'connected'},initialSection:'overview',onRefresh:()=>refresh++})
 const root=mount(t,Card,props);await flush()
 assert.match(content(root),/鹰角通行证 · 鹰角甲/);assert.match(content(root),/已记录寻访 123/);assert.match(content(root),/6★ 记录 0/);assert.match(content(root),/2026-10-15 09:02/)
 button(root,'刷新寻访数据').props.onClick();assert.equal(refresh,1)
 button(root,'查看寻访详情 →').props.onClick();await flush();assert.match(content(root),/寻访记录/)
 props.authAccount={configured:true,state:'expired'};await flush();assert.doesNotMatch(content(root),/鹰角甲|已记录寻访 123/)
 assert.equal(nodes(root,'button').find(n=>content(n)==='导出记录'),undefined)
})
test('formal cloud card refuses mismatched grant, role and Skland provider data',async t=>{
 configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
 setAccountScope({user_id:'u',account_id:'a',role_id:'p',provider:'hypergryph'})
 t.mock.method(globalThis,'fetch',async()=>response({}))
 const props=reactive({account:{account_id:'a',provider:'hypergryph',state:'active',roles:[{role_id:'p'}],capabilities:['account','gacha']},role:'p',userId:'u',snapshots:{account:{...account,account_id:'a',role_id:'p'},gacha:{...gacha,account_id:'a',role_id:'p'}}})
 const root=mount(t,CloudCard,props);await flush();assert.match(content(root),/已记录寻访 123/)
 props.snapshots.gacha={...props.snapshots.gacha,account_id:'other'};await flush();assert.doesNotMatch(content(root),/已记录寻访 123/);assert.match(content(root),/快照与当前鹰角身份不一致/)
 props.snapshots.gacha={...props.snapshots.gacha,account_id:'a',payload:{...gacha.payload,role_id:'other'}};await flush();assert.doesNotMatch(content(root),/已记录寻访 123/)
 props.account={...props.account,provider:'skland'};await flush();assert.doesNotMatch(content(root),/寻访摘要|鹰角甲|已记录寻访 123/)
})
test('actual cloud details entry distinguishes first failure and preserves previous wrapped response after later failure',async t=>{
 configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
 let failed=true
 const paths=[]
 t.mock.method(globalThis,'fetch',async url=>{paths.push(url);if(failed)throw new Error('云端失败');return response({payload:{...observed,stale:false},fetched_at})})
 const root=mount(t,CloudDetails,{account:{account_id:'s',provider:'skland'},role:'a'})
 nodes(root,'select')[0].props['onUpdate:modelValue']('challenges');await flush()
 await button(root,'重新读取战争').props.onClick();await flush();assert.match(content(root),/云端失败 尚无可显示/);assert.doesNotMatch(content(root),/本次返回没有/)
 failed=false;await button(root,'重新读取战争').props.onClick();await flush();assert.match(content(root),/已有战争资料/)
 failed=true;await button(root,'重新读取战争').props.onClick();await flush();assert.match(content(root),/已有资料待更新/);assert.match(content(root),/战争抓取于 2026-10-15 09:02/);assert.match(content(root),/已有战争资料/)
 assert.ok(paths.every(path=>path==='/api/accounts/s/roles/a/endfield/skland/challenges?kind=war'))
})
