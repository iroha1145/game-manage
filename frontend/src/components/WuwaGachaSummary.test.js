import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
const WuwaGacha = await loadVue(new URL('./WuwaGacha.vue', import.meta.url))
test('shared image view shows separated source summaries and unknown UP without any API request', async t => {
  let requests=0
  const before=globalThis.fetch
  globalThis.fetch=()=>{requests++;throw Error('image must not fetch')}
  t.after(()=>{globalThis.fetch=before})
  const root=mount(t,WuwaGacha,{imageMode:true,snapshot:{total:3,gold_total:1,items:[],gold:[],limit:50,offset:0,
    coverage:{segment_count:2,complete:false},pools:[{pool:'1',name:'角色池',total:3,
      pity:{status:'exact',count:0,rule_basis:'user_configured',rule_version:'personal',hard_pity_remaining:70,up_guarantee:'unknown'}}],
    aggregates:{total:1,items:[{kind:'five_star_summary',pool:'99',name:'来源五星',period_count:120,source:'mcgf'}],message:'不计入逐抽'}}})
  assert.match(content(root),/当前垫抽 0/)
  assert.match(content(root),/UP 保证未知/)
  assert.match(content(root),/来源自报五星周期抽数 120/)
  assert.match(content(root),/已导入记录/)
  assert.doesNotMatch(content(root),/来源片段|缺少判断依据|QQ 页码|来源 Unix/)
  assert.equal(nodes(root,'input').length,0)
  await Promise.resolve()
  assert.equal(requests,0)
})

test('summary artwork handles untyped weapons, newly cataloged items and count markers without altering source counts', async t => {
  const Summary = await loadVue(new URL('./WuwaGachaSummary.vue', import.meta.url))
  const { namedIcon } = await import('../wuwa-icons.js')
  const root = mount(t, Summary, { archive: { aggregates: { total: 4, items: [
    { name: '苍鳞千嶂', kind: 'five_star_summary', period_count: 73 },
    { name: '玉阙玄华', resource_type: '武器', kind: 'five_star_summary', period_count: 22 },
    { name: '莉莉', resource_type: '角色', kind: 'five_star_summary', period_count: 68 },
    { kind: 'current_count', period_count: 12 },
  ] } } })
  assert.deepEqual(nodes(root, 'img').map(n => n.props.src), [
    namedIcon('weapons', '苍鳞千嶂'), namedIcon('weapons', '玉阙玄华'), namedIcon('roles', '莉莉'),
  ])
  assert.match(content(root), /当前垫抽标记/)
  for (const count of [73, 22, 68, 12]) assert.match(content(root), new RegExp(`${count} 抽`))
  nodes(root, 'img')[0].props.onError()
  await (await import('vue')).nextTick()
  assert.match(content(root), /苍鳞千嶂/)
})

test('image draw records recover artwork from a role ID and an untyped weapon name', async t => {
  const Table = await loadVue(new URL('./WuwaDrawTable.vue', import.meta.url))
  const { namedIcon, characterIcon } = await import('../wuwa-icons.js')
  const rows = [{ resource_type: '角色', resource_id: '1102', name: 'Sanhua' }, { name: '苍鳞千嶂' }, { name: '未知物品' }]
  const root = mount(t, Table, { imageMode: true, rows })
  assert.deepEqual(nodes(root, 'img').map(n => n.props.src), [characterIcon('1102'), namedIcon('weapons', '苍鳞千嶂')])
  assert.match(content(root), /Sanhua/)
  assert.match(content(root), /未知物品/)
})

test('recent gold rail resolves a weapon without a type while keeping the source record visible', async t => {
  const { namedIcon } = await import('../wuwa-icons.js')
  t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => ({
    total: 1, gold_total: 1, pools: [], items: [],
    gold: [{ name: '苍鳞千嶂', rarity: 5, time: '2026-10-01T12:00:00' }],
  }) }))
  const root = mount(t, WuwaGacha, { accountKey: 'test:server' })
  await new Promise(resolve => setTimeout(resolve, 0))
  await (await import('vue')).nextTick()
  assert.deepEqual(nodes(root, 'img').map(n => n.props.src), [namedIcon('weapons', '苍鳞千嶂')])
  assert.match(content(root), /苍鳞千嶂/)
  assert.match(content(root), /最近一次/)
})
