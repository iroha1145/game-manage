import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'

const Card = await loadVue(new URL('./GameCard.vue', import.meta.url))
const game = (game_id, capabilities) => ({game_id,display_name:game_id,capabilities,credentials_configured:false})

test('integrated NTE keeps inline resources and the independent guide entry', async t => {
  const root=mount(t,Card,{game:game('nte',['stamina','roles']),externalSnapshots:{stamina:{payload:{schema_version:1,current:0,maximum:320}}}})
  assert.ok(nodes(root,'progress').some(n=>n.props.value===0 && n.props.max===320))
  assert.ok(!nodes(root,'button').some(n=>/查看体力/.test(content(n))))
  const guides=nodes(root,'button').find(n=>content(n)==='角色攻略')
  assert.ok(guides);guides.props.onClick();await nextTick()
  assert.ok(nodes(root,'button').some(n=>content(n)==='查看角色攻略'))
})

test('integrated shell retains the upstream Endfield gacha panel', async t => {
  t.mock.method(globalThis,'fetch',async()=>({ok:true,json:async()=>({connected:false,roles:[]})}))
  const root=mount(t,Card,{game:game('endfield',['gacha']),externalSnapshots:{}})
  nodes(root,'button').find(n=>content(n)==='抽卡统计').props.onClick()
  await nextTick()
  assert.match(content(root),/登录终末地后/)
  assert.match(content(root),/寻访记录/)
  assert.doesNotMatch(content(root),/敬请期待/)
})

test('integrated LOL shell exposes both announcements and local archive analysis', t => {
  t.mock.method(globalThis,'fetch',async()=>({ok:true,json:async()=>({matches:[],overview:{},coverage:{}})}))
  const root=mount(t,Card,{game:game('league_of_legends',['account','news','announcement','match']),externalSnapshots:{}})
  assert.ok(nodes(root,'button').some(n=>content(n)==='公告与资讯'))
  assert.ok(nodes(root,'button').some(n=>content(n)==='个人总览'))
})

test('NTE guides receive the account roles for the owned-only filter', async t => {
  const catalog = { reviewed_at:'2026-09-26', sources:[{ id:1, title:'原帖', author:'作者', version:'1.3', url:'https://www.tajiduo.com/bbs/index.html#/post?postId=1' }],
    guides:[{ id:'甲', name:'甲', aliases:[], element:'魂', role:'主 C', status:'reviewed', source_id:1, pages:[1], sections:[] },
            { id:'乙', name:'乙', aliases:[], element:'灵', role:'辅助', status:'reviewed', source_id:1, pages:[1], sections:[] }] }
  t.mock.method(globalThis,'fetch',async url=>({ok:true,json:async()=>url.endsWith('/guides') ? catalog : { id:1, images:[], paragraphs:[] }}))
  const root=mount(t,Card,{game:game('nte',['roles']),externalSnapshots:{roles:{payload:{schema_version:1,entries:[{name:'甲'}]}}}})
  nodes(root,'button').find(n=>content(n)==='角色攻略').props.onClick();await nextTick()
  nodes(root,'button').find(n=>content(n)==='查看角色攻略').props.onClick()
  for (let i=0;i<3;i++) { await new Promise(setImmediate); await nextTick() }
  nodes(root,'input').find(n=>n.props.type==='checkbox').props['onUpdate:modelValue'](true);await nextTick()
  const listed=nodes(root,'button').map(n=>n.props['aria-label']).filter(label=>/^查看.攻略$/.test(label||''))
  assert.deepEqual(listed,['查看甲攻略'])
  assert.doesNotMatch(content(root),/尚无角色资料/)
})
