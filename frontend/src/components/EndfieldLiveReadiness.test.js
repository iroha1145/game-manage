import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue,mount,nodes,content } from '../test-utils/vue.js'
import { configureHttpClient,setAccountScope } from '../http-client.js'
import { attendanceCount,attendanceEnvelope } from '../endfield-attendance.js'
const Dashboard=await loadVue(new URL('./EndfieldDashboard.vue',import.meta.url))
const Attendance=await loadVue(new URL('./EndfieldAttendance.vue',import.meta.url))
const News=await loadVue(new URL('./EndfieldNewsSummary.vue',import.meta.url))
const CloudDetails=await loadVue(new URL('./CloudAccountDetails.vue',import.meta.url))
const flush=async()=>{await new Promise(setImmediate);await nextTick()}
const button=(root,label)=>nodes(root,'button').find(node=>content(node)===label)
const response=value=>new Response(JSON.stringify(value))
const status={connected:true,roles:[{role_id:'a',server_id:'1'},{role_id:'b',server_id:'1'}],selected_role_id:'a',selected_server_id:'1'}
const profile={payload:{base:{name:'合成档案'},observed_at:'2026-10-15T00:00:00Z'},fetched_at:'2026-10-15T01:00:00Z',stale:false}
const attendance={supported:true,status:'signed',calendar:[{day:1,done:true,name:'合成奖励',count:0},{day:2,done:false}],updated_at:'2026-10-14T00:01:00Z',stale:false}

test('attendance counts only complete boolean observations and unwraps independent source times',()=>{
 for(const calendar of [undefined,[],[{done:null}],[{done:'false'}],[{done:1}]])assert.deepEqual(attendanceCount(calendar),{known:0,total:null})
 assert.deepEqual(attendanceCount([{done:false},{done:false}]),{known:0,total:0})
 assert.deepEqual(attendanceCount([{done:true},{done:null}]),{known:1,total:null})
 const wrapped={fetched_at:'2026-10-15T00:00:00Z',stale:true,payload:attendance}
 const value=attendanceEnvelope(wrapped)
 assert.equal(value.updated_at,attendance.updated_at);assert.equal(value.fetched_at,wrapped.fetched_at);assert.equal(value.stale,true)
 assert.equal(attendance.stale,false);assert.equal(attendanceEnvelope({}),null)
})

test('attendance renders source days, literal unknowns and sign receipt when calendar reread failed',t=>{
 const unknown=mount(t,Attendance,{value:{supported:true,status:'unknown',calendar:[{day:1,done:null},{day:2,done:'false'}]}})
 assert.match(content(unknown),/本期已签天数未知/);assert.doesNotMatch(content(unknown),/已知已签 0|本期已签 0|日期未提供/)
 assert.match(content(unknown),/第 1 日 状态未知/)
 const receipt=mount(t,Attendance,{value:{status:'signed',stale:true,error:'签到成功后回读失败',awards:[{name:'奖励零',count:0}],signed_at:'2025-12-31T01:02:00Z',records:[{name:'来源记录',signed_at:'2025-12-30T00:00:00Z'}]}})
 assert.match(content(receipt),/上次状态：已签/);assert.match(content(receipt),/已返回签到奖励 奖励零 × 0/)
 assert.match(content(receipt),/签到于 2025-12-31 09:02/);assert.match(content(receipt),/状态观测于 未知/)
 assert.match(content(receipt),/2025-12-30 08:00 · 来源记录/);assert.doesNotMatch(content(receipt),/今日奖励|今日已签/)
 assert.equal(button(receipt,'手动签到'),undefined)
 const firstFailure=mount(t,Attendance,{value:{status:'unknown',stale:true,error:'首次失败',calendar:[],updated_at:null}})
 assert.match(content(firstFailure),/签到状态未取得/);assert.match(content(firstFailure),/尚无可显示的签到资料/)
 assert.doesNotMatch(content(firstFailure),/已有签到资料待更新|正在显示已有签到资料/)
})

test('overview transport failures mark same-role card and attendance stale without changing their timestamps',async t=>{
 let fail=false;const calls=[]
 t.mock.method(globalThis,'fetch',async(url,options)=>{
  calls.push([url,options.method]);if(url.endsWith('/status'))return response(status)
  if(url.endsWith('/card') || url.endsWith('/refresh'))return fail?new Response(JSON.stringify({detail:'档案网络失败'}),{status:503}):response(profile)
  if(url.endsWith('/attendance')){if(fail)throw new Error('签到网络失败');return response(attendance)}
  return response({})
 })
 const root=mount(t,Dashboard,{initialSection:'overview'});await flush();await flush()
 assert.equal(button(root,'手动签到').props.disabled,true)
 fail=true;await button(root,'刷新档案').props.onClick();await button(root,'刷新签到状态').props.onClick();await flush()
 assert.match(content(root),/合成档案/);assert.match(content(root),/正在显示已有资料，等待更新/)
 assert.match(content(root),/观测于 2026-10-15 08:00/);assert.match(content(root),/同步于 2026-10-15 09:00/)
 assert.match(content(root),/已有签到资料待更新/);assert.match(content(root),/上次状态：已签/)
 assert.match(content(root),/状态观测于 2026-10-14 08:01/)
 fail=false;await button(root,'刷新签到状态').props.onClick();await flush()
 assert.match(content(root),/今日已签/);assert.doesNotMatch(content(root),/已有签到资料待更新/)
 assert.deepEqual(calls.filter(([url])=>url.endsWith('/attendance')).map(([,method])=>method),['GET','GET','GET'])
})

test('first attendance failure can retry with GET and only explicit sign click sends POST',async t=>{
 let fail=true;const methods=[]
 t.mock.method(globalThis,'fetch',async(url,options)=>{
  if(url.endsWith('/status'))return response(status)
  if(url.endsWith('/card'))return response(profile)
  if(url.endsWith('/attendance')){methods.push(options.method);if(fail)throw new Error('首次失败');return response(options.method==='POST'?{status:'signed',awards:[{name:'提交奖励',count:1}],signed_at:'2026-10-15T00:00:00Z'}:{status:'unsigned',calendar:[{day:1,done:false}],updated_at:'2026-10-15T00:00:00Z'})}
  return response({})
 })
 const root=mount(t,Dashboard,{initialSection:'overview'});await flush();await flush()
 assert.match(content(root),/尚无可显示的签到资料/);assert.equal(button(root,'刷新签到状态').props.disabled,false)
 fail=false;await button(root,'刷新签到状态').props.onClick();await flush()
 assert.match(content(root),/今日待签/);assert.match(content(root),/本期已签 0 天/)
 assert.deepEqual(methods,['GET','GET'])
 await button(root,'手动签到').props.onClick();await flush()
 assert.deepEqual(methods,['GET','GET','POST']);assert.match(content(root),/提交奖励 × 1/)
})

test('role change rejects late attendance success and failure without importing old role status',async t=>{
 for(const reject of [false,true]) {
  let active='a',finish;let requests=0
  t.mock.method(globalThis,'fetch',async url=>{
   if(url.endsWith('/status'))return response({...status,selected_role_id:active})
   if(url.endsWith('/role')){active='b';return response({...status,selected_role_id:active})}
   if(url.endsWith('/attendance')){requests++;if(active==='a')return new Promise((resolve,no)=>{finish=()=>reject?no(new Error('旧角色失败')):resolve(response({...attendance,today_award:{name:'旧角色奖励'}}))});return response({status:'unsigned',today_award:{name:'新角色奖励'},updated_at:'2026-10-15T00:00:00Z'})}
   return response(profile)
  })
  const root=mount(t,Dashboard,{initialSection:'overview'});await flush();await flush()
  await nodes(root,'select')[0].props.onChange({target:{value:'b:1'}});await flush();await flush();finish();await flush()
  assert.equal(requests,2);assert.match(content(root),/新角色奖励/)
  assert.doesNotMatch(content(root),/旧角色奖励|旧角色失败|已有签到资料待更新|2026-10-14 08:01/)
  t.mock.restoreAll()
 }
})

test('cloud overview uses scoped GET refresh, unwraps attendance and never offers a sign action',async t=>{
 configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
 setAccountScope({user_id:'u',account_id:'s',role_id:'a',provider:'skland'})
 let fail=false;const calls=[]
 t.mock.method(globalThis,'fetch',async(url,options)=>{calls.push([url,options.method]);if(fail)throw new Error('云端失败');return response({payload:attendance,fetched_at:'2026-10-15T02:00:00Z'})})
 const root=mount(t,Dashboard,{cloudAccount:{account_id:'s',provider:'skland',roles:[{role_id:'a'}]},cloudRole:'a',snaps:{account:profile}});await flush();await flush()
 assert.match(content(root),/今日已签/);assert.match(content(root),/状态观测于 2026-10-14 08:01.*抓取于 2026-10-15 10:00/)
 assert.equal(button(root,'手动签到'),undefined)
 fail=true;await button(root,'刷新签到状态').props.onClick();await flush()
 assert.match(content(root),/上次状态：已签/);assert.match(content(root),/已有签到资料待更新/)
 assert.deepEqual(calls,[['/api/accounts/s/roles/a/endfield/skland/attendance','GET'],['/api/accounts/s/roles/a/endfield/skland/attendance','GET']])
})

test('cloud independent details retain attendance and card after transport failures and clear on owner change',async t=>{
 configureHttpClient({mode:'cloud'});t.after(()=>configureHttpClient({mode:'local'}))
 let fail=false;const calls=[]
 t.mock.method(globalThis,'fetch',async(url,options)=>{calls.push([url,options.method]);if(fail)throw new Error('云端失败');return response(url.endsWith('/attendance')?{payload:attendance,fetched_at:'2026-10-15T02:00:00Z'}:profile)})
 const props=reactive({account:{account_id:'s',provider:'skland'},role:'a'})
 const root=mount(t,CloudDetails,props)
 await button(root,'读取详情').props.onClick();await flush();fail=true
 await button(root,'读取详情').props.onClick();await flush()
 assert.match(content(root),/合成档案/);assert.match(content(root),/正在显示已有资料，等待更新/);assert.match(content(root),/同步于 2026-10-15 09:00/)
 nodes(root,'select')[0].props['onUpdate:modelValue']('attendance');await flush()
 await button(root,'刷新签到状态').props.onClick();await flush()
 assert.match(content(root),/尚无可显示的签到资料/);assert.doesNotMatch(content(root),/合成档案/)
 fail=false;await button(root,'刷新签到状态').props.onClick();await flush();fail=true
 await button(root,'刷新签到状态').props.onClick();await flush()
 assert.match(content(root),/上次状态：已签/);assert.match(content(root),/状态观测于 2026-10-14 08:01.*抓取于 2026-10-15 10:00/)
 assert.match(content(root),/第 1 日 已签到/);assert.doesNotMatch(content(root),/日期未提供/)
 props.role='b';await flush();assert.doesNotMatch(content(root),/合成奖励|2026-10-14 08:01|上次状态：已签/)
 assert.ok(calls.every(([,method])=>method==='GET'));assert.equal(button(root,'手动签到'),undefined)
})

const article=(index,extra={})=>({id:`a${index}`,title:`公告 ${index}`,source:'official',source_name:'官网',published_at:`2026-10-${String(index).padStart(2,'0')}`,url:`https://example.com/${index}`,...extra})
test('news summary reuses safe merged articles, caps latest five and preserves date-only precision',t=>{
 let all=0;t.mock.method(globalThis,'fetch',()=>{assert.fail('summary must not fetch')})
 const snapshots=[{state:'ok',fetched_at:'2026-10-15T00:00:00Z',payload:Array.from({length:6},(_,index)=>article(index+1))},{payload:[article(6,{source:'bilibili',source_name:'B站'}),article(7,{url:'javascript:alert(1)',source_stale:true})]}]
 const root=mount(t,News,{snapshots,onAll:()=>all++})
 assert.equal(nodes(root,'li').length,5)
 assert.match(content(nodes(root,'li')[0]),/公告 7/);assert.deepEqual(nodes(root,'h3').map(content),['公告 7','公告 6 ↗','公告 5 ↗','公告 4 ↗','公告 3 ↗'])
 assert.equal(nodes(root,'h3').filter(node=>content(node).includes('公告 6')).length,1)
 assert.match(content(root),/官网/);assert.match(content(root),/2026-10-07/)
 assert.doesNotMatch(content(root),/2026-10-07 00:00|2026-10-07 08:00/)
 assert.match(content(root),/快照更新于 2026-10-15 08:00/)
 assert.ok(nodes(root,'a').every(node=>node.props.href.startsWith('https://')))
 button(root,'查看全部公告 →').props.onClick();assert.equal(all,1)
})

test('news summary distinguishes no snapshot, successful empty, retained failure and fresh partial fallback',async t=>{
 const props=reactive({snapshots:[]}),root=mount(t,News,props)
 assert.match(content(root),/尚未采集公告快照/)
 props.snapshots=[{state:'ok',payload:[]}];await nextTick();assert.match(content(root),/已采集，暂无公告与资讯/)
 props.snapshots=[{state:'error',stale:true,error:'采集异常',payload:[article(1)]}];await nextTick()
 assert.match(content(root),/已有公告待更新/);assert.match(content(root),/保留上次成功公告/);assert.match(content(root),/公告 1/)
 props.snapshots=[{state:'error',stale:false,payload:[article(1)],poll_status:{source_statuses:{official:{state:'ok'},bilibili:{state:'error'}}}}];await nextTick()
 assert.match(content(root),/部分来源不可用，显示可用来源数据/);assert.doesNotMatch(content(root),/已有公告待更新|保留上次成功公告/)
})

test('formal overview shows existing public snapshots without collection and all link opens the news section',async t=>{
 const calls=[]
 t.mock.method(globalThis,'fetch',async url=>{calls.push(url);return response(url.endsWith('/status')?{connected:false,roles:[]}:{news:{items:[]}})})
 const root=mount(t,Dashboard,{initialSection:'overview',snaps:{news:{payload:[article(1)]},announcement:{payload:[article(2)]}}});await flush()
 assert.match(content(root),/公告 1/);assert.match(content(root),/公告 2/);assert.deepEqual(calls,['/api/endfield/skland/status'])
 button(root,'查看全部公告 →').props.onClick();await flush()
 assert.match(content(root),/公告与资讯/);assert.match(content(root),/公告 1/);assert.match(content(root),/公告 2/)
 assert.equal(calls.filter(url=>url==='/api/endfield/public').length,1)
})
