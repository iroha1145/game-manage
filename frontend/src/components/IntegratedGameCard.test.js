import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
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
  const props=reactive({game:game('endfield',['gacha']),externalSnapshots:{}})
  const root=mount(t,Card,props)
  nodes(root,'button').find(n=>content(n)==='抽卡统计').props.onClick()
  await nextTick()
  assert.match(content(root),/请登录有效的鹰角通行证/)
  assert.equal(nodes(root,'button').find(n=>content(n)==='导出记录'),undefined)
  props.game={...props.game,credentials_configured:true};props.externalSnapshots={account:{payload:{role_id:'r'}}};await nextTick()
  assert.match(content(root),/寻访记录/)
  assert.doesNotMatch(content(root),/敬请期待/)
})

test('integrated LOL shell exposes both announcements and local archive analysis', t => {
  t.mock.method(globalThis,'fetch',async()=>({ok:true,json:async()=>({matches:[],overview:{},coverage:{}})}))
  const root=mount(t,Card,{game:game('league_of_legends',['account','news','announcement','match']),externalSnapshots:{}})
  assert.ok(nodes(root,'button').some(n=>content(n)==='公告与资讯'))
  assert.ok(nodes(root,'button').some(n=>content(n)==='个人总览'))
})
