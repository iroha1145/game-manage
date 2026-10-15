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
