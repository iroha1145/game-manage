import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
import { collectVersionCalendars } from '../calendar.js'
const Calendar=await loadVue(new URL('./VersionCalendarContent.vue',import.meta.url))
const NteRoles=await loadVue(new URL('./NteRolesPanel.vue',import.meta.url))
const WuwaGacha=await loadVue(new URL('./WuwaGacha.vue',import.meta.url))
const Community=await loadVue(new URL('./NteCommunityGacha.vue',import.meta.url))
const RenderRoot=await loadVue(new URL('./RenderRoot.vue',import.meta.url))

test('shared render source and output target both inherit the existing game accent token',t=>{
 for(const [game,color] of [['nte','var(--game-nte)'],['wuthering_waves','var(--game-wuwa)']]){
  const root=mount(t,RenderRoot,{snapshot:{kind:game==='nte'?'nte_role':'wuwa_role',game,as_of:'2026-10-15T12:00:00+08:00',display_data:{snapshot:{payload:{schema_version:1,entries:[]}},detail:{role:{}},fetched_at:null}}})
  for(const id of ['render-content','render-pages']){
   const node=nodes(root,'div').find(node=>node.props.id===id)
   assert.ok(node.props.class.includes('game-theme'))
   assert.equal(node.props.style['--game-accent'],color)
  }
 }
})

test('image pages for events and the calendar request no game icon file, which the QQ renderer would abort',t=>{
 const events=[{name:'跨月活动',category:'限时活动',start_at:'2026-10-01T10:00:00+08:00',end_at:'2026-11-20T10:00:00+08:00',source_title:'版本公告'}]
 const events_snapshot={payload:events,fetched_at:'2026-10-14T11:00:00+08:00',state:'ok',complete:true,stale:false}
 const base={schema_version:1,game:'nte',as_of:'2026-10-14T12:00:00+08:00',page:1,theme:'light'}
 const pages={
  game_snapshot:{...base,kind:'game_snapshot',title:'近期活动',next_command:'近期活动',display_data:{notices:[],panels:[{game:'nte',provider:'public',capability:'events',snapshot:events_snapshot}]}},
  calendar:{...base,kind:'calendar',title:'活动日历',next_command:'活动日历',display_data:{games:[{game_id:'nte',display_name:'异环'}],snapshots:{nte:{events:events_snapshot}}}},
 }
 for(const [kind,snapshot] of Object.entries(pages)){
  const root=mount(t,RenderRoot,{snapshot})
  assert.match(content(root),/跨月活动/,kind)
  assert.deepEqual(nodes(root,'img').map(n=>n.props.src),[],kind)
 }
})
test('screen and image calendar share all dated and unknown content without clipping or fake version end',t=>{
 const now=Date.parse('2026-10-14T12:00:00+08:00')
 const calendars=collectVersionCalendars([{game_id:'nte',display_name:'异环'}],{nte:{events:{payload:[
  {name:'跨月活动',start_at:'2026-10-01T10:00:00+08:00',end_at:'2026-11-20T10:00:00+08:00',source_title:'版本公告'},
  {name:'开始未知活动',end_at:'2026-11-01T10:00:00+08:00',source_title:'版本公告'},
 ]}}},'',now)
 for(const mode of ['screen','image']){
  const root=mount(t,Calendar,{calendars,asOf:now,mode})
  assert.match(content(root),/跨月活动.*开始未知活动/)
  assert.match(content(root),/活动日期范围/)
  assert.doesNotMatch(content(root),/覆盖待核验|不代表版本边界/)
  if(mode==='screen') assert.match(content(root),/版本结束：未知/)
  else assert.doesNotMatch(content(root),/版本结束|数据来源详情/)
  assert.deepEqual([...new Set(nodes(root,mode==='image'?'article':'button').map(n=>n.props['aria-label']))],['查看活动详情：跨月活动','查看活动详情：开始未知活动'])
 }
})
test('relative dates and explicit permanent openings appear on the normal calendar in screen and image modes',t=>{
 const now=Date.parse('2026-10-15T08:00:00+08:00')
 const calendars=collectVersionCalendars([{game_id:'nte',display_name:'异环'}],{nte:{events:{payload:[
  {name:'中期维护活动',start_at:null,start_date:'2026-10-15',start_precision:'relative',start_text:'维护完成后',start_estimated:true,end_at:'2026-11-05T05:59:00+08:00',end_precision:'minute'},
  {name:'故梦寻契',start_at:null,start_date:'2026-09-30',start_precision:'relative',permanent:true,end_precision:'permanent',end_text:'永久开放'},
  {name:'仍待日期',start_at:null,end_at:'2026-11-05T05:59:00+08:00',start_precision:'relative'},
 ]}}},'',now)
 for(const mode of ['screen','image']){
  const root=mount(t,Calendar,{calendars,asOf:now,mode})
  const tracks=nodes(root,'div').filter(n=>n.props.class==='event-lane')
  const relative=tracks.find(n=>content(n).includes('中期维护活动'))
  const permanent=tracks.find(n=>content(n).includes('故梦寻契'))
  assert.ok(relative)
  assert.ok(permanent)
  assert.match(content(relative),/预计/)
  assert.doesNotMatch(content(relative),/进行中|2026-10-15/)
  assert.equal(calendars[0].events.find(e=>e.name==='中期维护活动').start_date,'2026-10-15')
  assert.match(content(permanent),/常驻开放/)
  const unknown=nodes(root,mode==='image'?'article':'button').find(n=>n.props['aria-label']==='查看活动详情：仍待日期')
  assert.ok(unknown.props.class.includes('is-point'))
  assert.match(content(unknown),/开始未知/)
 }
})
test('image role hides search favorites and comparison controls; full fields remain',t=>{
 const root=mount(t,NteRoles,{imageMode:true,detailMode:true,snap:{payload:{schema_version:1,entries:[{id:'9001',name:'测试角色',level:0,properties:[{name:'攻击',value:'1234'}],skills:[{name:'战技',level:2}]}]}}})
 assert.match(content(root),/测试角色.*Lv0.*攻击.*1234.*战技/)
 assert.equal(nodes(root,'input').length,0)
 assert.ok(nodes(root,'details').every(node=>node.props.open))
})
test('gacha supplied snapshot disables import/API controls and retains unknown coverage',t=>{
 const root=mount(t,WuwaGacha,{imageMode:true,snapshot:{total:0,coverage:{message:'历史未知'},pools:[],items:[],gold:[]}})
 assert.match(content(root),/已导入记录 0 抽/)
 assert.equal(nodes(root,'form').length,0)
})

test('wuwa image groups current records by every pool without losing unmatched rows, zero or unknown',t=>{
 const root=mount(t,WuwaGacha,{imageMode:true,snapshot:{total:3,gold_total:1,pools:[{pool:'1',name:'角色池'},{pool:'2',name:'武器池'}],gold:[{pool:'1',name:'五星角色',rarity:5}],items:[{pool:'1',name:'角色甲',count:0},{pool:'2',name:'武器乙',rarity:null},{pool:null,name:'未分池记录'}]}})
 const groups=nodes(root,'section').filter(node=>String(node.props.class).includes('wuwa-pool-records'))
 assert.equal(groups.length,4)
 assert.match(content(groups[0]),/角色池.*五星角色/)
 assert.match(content(groups[1]),/角色池.*角色甲.*0/)
 assert.match(content(groups[2]),/武器池.*武器乙.*未知/)
 assert.match(content(groups[3]),/未知卡池.*未分池记录/)
 assert.equal(nodes(root,'tr').filter(node=>nodes(node,'td').length).length,4)
})
test('community image includes S records from every pool without hidden tabs',t=>{
 const records=prefix=>Array.from({length:30},(_,i)=>({name:prefix+i}))
 const root=mount(t,Community,{imageMode:true,snap:{payload:{schema_version:1,pools:[{name:'角色池',details:records('角色')},{name:'弧盘池',details:records('弧盘')}]}}})
 const groups=nodes(root,'section').filter(node=>String(node.props.class).includes('history-panel'))
 assert.equal(groups.length,2)
 assert.match(content(groups[0]),/角色池.*角色0.*角色29/)
 assert.match(content(groups[1]),/弧盘池.*弧盘0.*弧盘29/)
 assert.equal(nodes(root,'li').filter(node=>node.props.class?.includes('pull-row')).length,60)
 assert.equal(nodes(root,'nav').length,0)
})
