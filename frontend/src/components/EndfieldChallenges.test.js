import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue,mount,content,nodes } from '../test-utils/vue.js'
const Component=await loadVue(new URL('./EndfieldChallenges.vue',import.meta.url))
const fetched_at='2026-10-15T01:02:00Z'
test('challenge report shows hierarchy, zero and false with its category observation only',t=>{
 let selected,reloaded=0
 const value={kind:'war',fetched_at,records:[{name:'赛季甲',stars:0,weeks:[{name:'第一周',stars:0,groups:[{name:'组甲',star:0,normalDungeon:{name:'关卡甲',isPass:false},hardDungeon:{name:'关卡乙'}}]}]}],summary:{honors:[{name:'荣誉甲',star:0,first_pass_at:fetched_at}]}}
 const root=mount(t,Component,{value,kind:'war',onSelectKind:v=>selected=v,onReload:()=>reloaded++})
 assert.match(content(root),/战争抓取于 2026-10-15 09:02/);assert.match(content(root),/赛季甲 0 星/);assert.match(content(root),/第一周 0 星/)
 assert.match(content(root),/普通 关卡甲 未通关/);assert.match(content(root),/困难 关卡乙 状态未知/);assert.match(content(root),/荣誉甲.*0 星/);assert.match(content(root),/不代表完整历史/)
 nodes(root,'button').find(n=>content(n)==='丰碑').props.onClick();assert.equal(selected,'monument')
 nodes(root,'button')[0].props.onClick();assert.equal(reloaded,1)
})
test('failure, no collection, success empty and unsupported have separate messages',t=>{
 assert.match(content(mount(t,Component,{kind:'crisis',error:'失败'})),/失败 尚无可显示的已采集资料/)
 assert.doesNotMatch(content(mount(t,Component,{kind:'crisis',error:'失败'})),/本次返回没有|暂无挑战记录/)
 assert.match(content(mount(t,Component,{kind:'crisis'})),/尚未采集危机记录/)
 assert.match(content(mount(t,Component,{kind:'crisis',value:{kind:'crisis',fetched_at,records:[],summary:{highest:0,challenge_count:0}}})),/来源历史最高值 0.*来源挑战次数 0.*本次返回没有危机记录/)
 assert.match(content(mount(t,Component,{kind:'crisis',value:{kind:'crisis',supported:false}})),/暂不支持危机挑战/)
 assert.match(content(mount(t,Component,{kind:'war',value:{kind:'war',fetched_at,stale:true,error:'失败',records:[]}})),/已有资料待更新.*上次成功资料/)
})
