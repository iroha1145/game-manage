import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
const Roles=await loadVue(new URL('./WuwaRoles.vue',import.meta.url))
const Render=await loadVue(new URL('./RenderRoot.vue',import.meta.url))
const snap=payload=>({payload,fetched_at:'2026-10-15T04:00:00Z',state:'ok',complete:false,stale:false})
const panel=(game,capability,payload)=>({game,provider:game==='nte'?'tajiduo':game==='endfield'?'skland':'kuro',capability,snapshot:snap(payload)})
const input=panels=>({kind:'game_snapshot',game:'all',as_of:'2026-10-15T04:00:00Z',display_data:{panels,notices:[]}})

test('wuwa image roster is a read-only complete web roster with zero and unknown',t=>{
 const root=mount(t,Roles,{imageMode:true,snap:snap([{role_id:'first',name:'合成首角色',level:0,chain:null},{role_id:'last',name:'合成末角色',level:null,chain:0}])})
 assert.match(content(root),/合成首角色/);assert.match(content(root),/合成末角色/)
 assert.match(content(root),/Lv\.0/);assert.match(content(root),/未知/)
 assert.equal(nodes(root,'input').length,0)
 assert.equal(nodes(root,'button').filter(n=>String(n.props.class).includes('wuwa-role ')).length,0)
 assert.equal(nodes(root,'article').filter(n=>String(n.props.class).includes('wuwa-role ')).length,2)
})

test('dashboard uses actual web capability cards without replacing zero or omitting first and last rows',t=>{
 const root=mount(t,Render,{snapshot:input([
  panel('nte','stamina',{schema_version:1,current:0,maximum:null,city_current:null,city_maximum:100,daily_activity:0,weekly_remaining:null}),
  panel('wuthering_waves','exploration',{country_groups:[{name:'合成首地区',progress:0,areas:[]},{name:'合成末地区',progress:null,areas:[]}]}),
  panel('endfield','roles',{operators:[{id:'a',name:'合成首干员',level:0,potential:null},{id:'z',name:'合成末干员',level:null,potential:0}]})
 ])})
 for(const value of ['本性像素','0','未知','合成首地区','合成末地区','合成首干员','合成末干员'])assert.ok(content(root).includes(value),value)
 assert.equal(nodes(root,'button').filter(n=>/配装|详情/.test(content(n))).length,0)
})

test('notice uses webpage primitives and keeps actionable authorization text',t=>{
 const root=mount(t,Render,{snapshot:{kind:'notice',game:'all',display_data:{title:'账号状态',sections:[{title:'绑定状态',items:['合成首条','授权已过期，请到社区账号重新登录。','合成末条']}],notices:['查询仅使用已有数据。']}}})
 assert.match(content(root),/账号状态.*绑定状态.*合成首条.*重新登录.*合成末条.*已有数据/)
})

test('endfield native content adapts independent stamina and preserves selected cached loadout',t=>{
 const root=mount(t,Render,{snapshot:input([
  panel('endfield','stamina',{current:0,maximum:null}),
  panel('endfield','roles',{operators:[{name:'精确选中干员',level:0,weapon:{name:'实际缓存武器',level:0,refine_level:null},equipment:[{name:'实际装备末条',level:null}],skills:[{name:'实际技能末条',level:0}]}]})
 ])})
 assert.match(content(root),/森空岛档案.*理智 0 \/ 未知/)
 assert.match(content(root),/精确选中干员.*实际缓存武器.*等级 LV\. 0.*精炼 未知.*实际装备末条.*等级 LV\. 未知/)
 const skills=nodes(root,'section').find(node=>node.props['aria-label']==='干员技能')
 assert.ok(skills);assert.match(content(skills),/LV\. 0.*实际技能末条/)
})

test('filtered activity panels keep supplied first and last events without replacing them by full-version content',t=>{
 const root=mount(t,Render,{snapshot:input([panel('nte','events',[{name:'筛选首活动',start_at:'2026-10-14T04:00:00Z',end_at:'2026-10-16T04:00:00Z'},{name:'筛选末活动',start_at:null,end_at:null}])])})
 assert.match(content(root),/筛选首活动/);assert.match(content(root),/筛选末活动/)
 assert.doesNotMatch(content(root),/版本完整活动/)
})

test('image news omits technical quality markers while keeping dates, category and whole supplied summary',t=>{
 const p=panel('nte','news',[{title:'普通公告',summary:'完整摘要正文',source_name:'内部来源标签',source_stale:true,published_at:'2026-10-14T04:00:00Z'}]);p.snapshot.stale=true
 const root=mount(t,Render,{snapshot:input([p])})
 assert.match(content(root),/普通公告.*完整摘要正文/)
 assert.match(content(root),/10\/14/)
 assert.doesNotMatch(content(root),/内部来源标签|来源采集异常|旧记录|数据可能过期/)
})

test('image news shares webpage excerpts for every long article and explicitly distinguishes summary from full text',t=>{
 const articles=Array.from({length:4},(_,i)=>({title:`长文公告${i}`,body:'合成长正文'.repeat(500)+`不可冒充全文末尾${i}`,published_at:'2026-10-14T04:00:00Z'}))
 const root=mount(t,Render,{snapshot:input([panel('wuthering_waves','news',articles)])})
 assert.match(content(root),/摘要.*全文.*原文.*看板/)
 for(let i=0;i<4;i++)assert.ok(content(root).includes(`长文公告${i}`))
 const summaries=nodes(root,'p').filter(n=>String(n.props.class).includes('item-summary'))
 assert.equal(summaries.length,4)
 assert.ok(summaries.every(n=>content(n)==='合成长正文'.repeat(500).slice(0,180)+'…'))
 assert.doesNotMatch(content(root),/不可冒充全文末尾/)
})

test('new image capability mounts and toggles stay offline; article excerpts and all challenge branches remain',async t=>{
 let requests=0
 const previous=globalThis.fetch
 globalThis.fetch=async()=>{requests++;throw Error('image mode must not fetch')}
 t.after(()=>{globalThis.fetch=previous})
 const long='合成长摘要正文'.repeat(40)+'合成摘要末尾'
 const root=mount(t,Render,{snapshot:input([
  panel('wuthering_waves','roles',[{role_id:'a',name:'只读角色',level:0}]),
  panel('wuthering_waves','activities',{sections:{one:{title:'完整玩法',liveness:0,liveness_max_count:null,description:'玩法完整正文'}}}),
  panel('wuthering_waves','resources',{current:{kind:'week',period:'合成周期',data:{total_coin:0,total_star:null}}}),
  panel('wuthering_waves','combat',{tower:{state:'ok',data:{difficulty_list:[]}},hologram:{state:'ok',data:{challenge_info:{a:[{boss_name:'合成首领末尾',difficulty:0,boss_level:null}]}}},slash:{state:'ok',data:{difficulty_list:[]}}}),
  panel('endfield','gacha',{schema_version:1,total:0,pools:[{key:'unknown',label:'未知计数卡池',total:null,six_star:null,five_star:0,since_last_six:{status:'unknown'},history:[]}]}),
  panel('nte','news',[{title:'合成首公告',summary:long},{title:'合成末公告',summary:'最后摘要'}])
 ])})
 for(const node of nodes(root,'details'))node.props.onToggle?.({target:{open:true},currentTarget:{open:true}})
 for(const node of nodes(root,'article').filter(n=>String(n.props.class).includes('wuwa-role ')))await node.props.onClick?.()
 await new Promise(setImmediate);await nextTick()
 assert.equal(requests,0)
 for(const value of [long.slice(0,180)+'…','玩法完整正文','合成首领末尾','逆境深塔','战术全息','冥歌海墟','6★ 未知','5★ 0','合成首公告','合成末公告'])assert.ok(content(root).includes(value),value)
 assert.doesNotMatch(content(root),/合成摘要末尾/)
 assert.doesNotMatch(content(root),/UID|server_id|role_id|来源补充字段/)
})
