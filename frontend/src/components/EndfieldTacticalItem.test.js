import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
const Item=await loadVue(new URL('./EndfieldTacticalItem.vue',import.meta.url))

test('tactical item preserves zero rarity and literal effect templates without inventing owned date',t=>{
  const item={name:'合成战术设备',rarity:0,icon_url:'https://bbs.hycdn.cn/item.png',active_effect:'造成 {damage:0%} 伤害\n剩余 0 次',passive_effect:'<b>来源文本</b>'}
  const root=mount(t,Item,{item})
  assert.match(content(root),/稀有度 0/);assert.match(content(root),/主动效果 造成 \{damage:0%\} 伤害 剩余 0 次/)
  assert.match(content(root),/被动效果 <b>来源文本<\/b>/);assert.equal(nodes(root,'b').length,0)
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
