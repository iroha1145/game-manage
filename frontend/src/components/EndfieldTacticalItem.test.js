import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
const Item=await loadVue(new URL('./EndfieldTacticalItem.vue',import.meta.url))
const ReadOnly=await loadVue(new URL('./CloudReadOnlyDetails.vue',import.meta.url))

test('tactical item preserves zero rarity and literal effect templates without inventing owned date',t=>{
  const item={name:'合成战术设备',rarity:0,icon_url:'https://bbs.hycdn.cn/item.png',active_effect:'造成 {damage:0%} 伤害\n剩余 0 次',passive_effect:'<b>来源文本</b>'}
  const root=mount(t,Item,{item})
  assert.match(content(root),/稀有度 0/);assert.match(content(root),/造成 \{damage:0%\} 伤害 剩余 0 次/)
  assert.match(content(root),/<b>来源文本<\/b>/);assert.equal(nodes(root,'b').length,0)
  assert.equal(nodes(root,'img')[0].props.src,item.icon_url)
  assert.doesNotMatch(content(root),/获得于|装备于|拥有于/)
})

test('unknown tactical data and unsafe icons do not imply unequipped state or request unreviewed media',t=>{
  const missing=mount(t,Item,{})
  assert.match(content(missing),/来源未提供战术道具，无法判断当前装备状态/)
  assert.doesNotMatch(content(missing),/未装备|稀有度 0/)
  const unknown=mount(t,Item,{item:{name:'未知道具',rarity:null,icon_url:'https://example.com/a.png',active_effect:{text:'不可猜测'}}})
  assert.match(content(unknown),/稀有度 未知/);assert.match(content(unknown),/来源未提供效果说明/)
  assert.equal(nodes(unknown,'img').length,0)
})

test('cloud independent operator details consume the same tactical contract',t=>{
  const root=mount(t,ReadOnly,{kind:'operators',result:{payload:{name:'干员甲',tactical_item:{name:'云端道具',rarity:0,active_effect:'主动 {0}',passive_effect:'被动 {1}'}}}})
  assert.match(content(root),/云端道具/);assert.match(content(root),/稀有度 0/)
  assert.match(content(root),/主动效果 主动 \{0\}/);assert.match(content(root),/被动效果 被动 \{1\}/)
})

test('cloud operator obtained time preserves its own date and never uses outer fetch time',t=>{
 for(const obtained_at of ['2025-12-31T17:02:00Z',null,undefined]) {
  const root=mount(t,ReadOnly,{kind:'operators',result:{fetched_at:'2026-10-15T01:00:00Z',payload:{name:'干员甲',obtained_at}}})
  assert.match(content(root),obtained_at?/获得时间 2026-01-01 01:02（北京时间）/:/获得时间 未知（北京时间）/)
  assert.doesNotMatch(content(root),/获得时间 2026-10-15/)
 }
})

test('cloud operator endpoint envelope is authoritative including explicit null and supports legacy wrappers',t=>{
 const operator={name:'真实契约干员',obtained_at:'2025-12-31T17:02:00Z',weapon:{name:'契约武器'},tactical_item:{name:'契约道具',rarity:0}}
 for(const result of [{operator,fetched_at:'2026-10-15T00:00:00Z'},{payload:{operator}}, {payload:operator},operator]) {
  const root=mount(t,ReadOnly,{kind:'operators',result})
  assert.match(content(root),/真实契约干员 · 干员配装/);assert.match(content(root),/契约武器/);assert.match(content(root),/契约道具/)
  assert.match(content(root),/获得时间 2026-01-01 01:02/)
 }
 const root=mount(t,ReadOnly,{kind:'operators',result:{operator:null,...operator,payload:operator,fetched_at:'2026-10-15T00:00:00Z'}})
 assert.match(content(root),/获得时间 未知/);assert.match(content(root),/来源未提供战术道具/)
 assert.doesNotMatch(content(root),/真实契约干员|契约武器|契约道具|2026-01-01|2026-10-15/)
})

test('tactical display removes only verified flat paired color markers and leaves source parameters untouched',t=>{
 const active_effect='恢复 <@ba.vup>{triggerheal2:0%}</>；<@tips.purple>无限制支援主控干员</>，<@tips.orange>用尽后恢复次数</>。'
 const item={name:'颜色标记样本',active_effect,passive_effect:'原始 <foo>未知标签</foo> 与 {value:0%}'}
 const root=mount(t,Item,{item})
 assert.match(content(root),/恢复 \{triggerheal2:0%\}；无限制支援主控干员，用尽后恢复次数。/)
 assert.match(content(root),/<foo>未知标签<\/foo> 与 \{value:0%\}/)
 assert.match(content(root),/效果包含来源参数，未代入数值/)
 assert.doesNotMatch(content(root),/<@ba\.vup>|<@tips\.purple>|<@tips\.orange>/)
 assert.equal(item.active_effect,active_effect);assert.equal(nodes(root,'foo').length,0)
})

test('tactical display preserves unpaired, nested and unverified game markers literally',t=>{
 const active_effect='<@tips.orange>缺少闭合 | <@tips.red>未知颜色</> | <@tips.purple>嵌套<foo>内容</foo></>'
 const root=mount(t,Item,{item:{active_effect}})
 assert.ok(content(root).includes(active_effect));assert.equal(nodes(root,'foo').length,0)
 assert.doesNotMatch(content(root),/效果包含来源参数/)
})
