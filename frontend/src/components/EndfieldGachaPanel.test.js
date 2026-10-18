import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue, mount, content, nodes, choose } from '../test-utils/vue.js'
const Panel = await loadVue(new URL('./EndfieldGachaPanel.vue', import.meta.url))
const flush = async () => { await new Promise(setImmediate); await nextTick() }
function api(t, handler) {
  const old = globalThis.fetch, calls = []
  t.after(() => { globalThis.fetch = old })
  globalThis.fetch = async url => { calls.push(url); const [status, body] = await handler(url); return new Response(JSON.stringify(body), { status }) }
  return calls
}
const summary = { schema_version: 1, role_id: 'r1', total: 30, complete: false, pools: [
  { key: 'E_CharacterGachaPoolType_Special', label: '特许寻访', kind: 'character', total: 30, six_star: 1, five_star: 3, free: 0,
    since_last_six: { count: 2, status: 'exact' }, gaps: 1, pending: true,
    history: [{ name: '提弗洛斯', pool_name: '冬猎', obtained_at: 1788300000000, pulls: 28, status: 'lower_bound' }] }] }
const snap = { payload: summary, fetched_at: '2026-09-24T12:00:00+08:00' }

test('pools show exact and lower-bound pity wording and an unfinished sync', async t => {
  const calls = api(t, () => [200, { total: 0, records: [] }])
  const root = mount(t, Panel, { snap, accountId: 'r1' }); await flush()
  const text = content(root)
  assert.match(text, /距上次 6★ 2 抽/)
  assert.match(text, /提弗洛斯 ≥28 抽/)
  assert.match(text, /还有未同步完的记录/)
  assert.match(text, /部分待同步/)
  assert.equal(calls.length, 0) // 逐条记录未展开时不读取
})

test('opening the record list reads the selected pool and pages through the local ledger', async t => {
  const calls = api(t, url => [200, { total: 60, records: [{ seq_id: '99', pool_key: 'E_CharacterGachaPoolType_Special', name: '提弗洛斯', rarity: 6, gacha_ts: 1788300000000 }] }])
  const root = mount(t, Panel, { snap, accountId: 'r1' }); await flush()
  nodes(root, 'details')[0].props.onToggle({ target: { open: true } }); await flush()
  assert.match(calls[0], /records\?pool_key=&offset=0&limit=50/)
  assert.match(content(root), /提弗洛斯 6★/)
  await nodes(root, 'button').find(n => content(n) === '下一页').props.onClick(); await flush()
  assert.match(calls.at(-1), /offset=50/)
  choose(root, '卡池', 'E_CharacterGachaPoolType_Special'); await flush()
  assert.match(calls.at(-1), /pool_key=E_CharacterGachaPoolType_Special&offset=0/)
})

test('missing login, legacy snapshots and read errors are explained without inventing data', async t => {
  api(t, () => [409, { detail: '请先登录终末地' }])
  assert.match(content(mount(t, Panel, { snap: null, accountId: '' })), /登录终末地后/)
  assert.match(content(mount(t, Panel, { snap: { payload: { pools: summary.pools } }, accountId: 'r1' })), /尚未同步寻访记录/)
  const props = reactive({ snap, accountId: 'r1' })
  const root = mount(t, Panel, props); await flush()
  nodes(root, 'details')[0].props.onToggle({ target: { open: true } }); await flush()
  assert.match(content(root), /请先登录终末地/)
})

test('report summary labels its bounded exact sample and keeps unknown history distinct from lower bounds', t=>{
  api(t,()=>[200,{}])
  const report={schema_version:1,total:30,six_star:1,five_star:3,free:0,gaps:1,pending:true,known_exact_intervals:2,average_exact_pulls:44}
  const root=mount(t,Panel,{snap:{payload:{...summary,report,pools:[{...summary.pools[0],history:[{name:'未知区间',pulls:12,status:'unknown'}]}]}},accountId:'r1'})
  assert.match(content(root),/免费寻访 0/);assert.match(content(root),/记录内准确区间均值 44 抽/)
  assert.match(content(root),/当前展示历史中 2 个抽数准确/);assert.match(content(root),/未知区间 未知/);assert.doesNotMatch(content(root),/未知区间 ≥12/)
})

test('closing the ledger while its response is pending discards late private records',async t=>{
  let resolve
  api(t,()=>new Promise(done=>{resolve=()=>done([200,{total:1,records:[{name:'迟到私人记录'}]}])}))
  const root=mount(t,Panel,{snap,accountId:'r1'});nodes(root,'details')[0].props.onToggle({target:{open:true}});await flush()
  nodes(root,'details')[0].props.onToggle({target:{open:false}});await flush();resolve();await flush()
  assert.doesNotMatch(content(root),/迟到私人记录/)
})

test('pool report coverage and unknown rarity are shown instead of inventing four-star remainder',t=>{
 const pool={...summary.pools[0],six_star:51,four_star:null,unknown_rarity:4,history:Array.from({length:50},()=>({name:'报告出货'})),history_limit:50}
 const root=mount(t,Panel,{accountId:'r1',snap:{payload:{...summary,report:{schema_version:1,pools:[pool]}}}})
 assert.match(content(root),/4★ 未知/);assert.match(content(root),/未知 \/ 其他 4/);assert.match(content(root),/最近 50 条 \/ 账本 51 条/)
 assert.match(content(root),/最多展示 50 条/);assert.match(content(root),/此处未展示全部 6★ 历史/);assert.match(content(root),/导出完整已保存账本/)
 assert.doesNotMatch(content(root),/提弗洛斯/)
})

const by = (root, type, name) => nodes(root, type).filter(node => String(node.props.class).split(' ').includes(name))
const history = [
  { name: '提弗洛斯', pool_name: '冬猎', obtained_at: 1788300000000, pulls: 66, status: 'exact' },
  { name: '余烬', pool_name: '熔火灼痕', obtained_at: 1786000000000, pulls: 52, status: 'lower_bound' },
]
const second = { key: 'E_CharacterGachaPoolType_Standard', label: '基础寻访', kind: 'character', total: 48, six_star: 1, five_star: 7, four_star: 40, unknown_rarity: 0, free: 0,
  since_last_six: { count: 17, status: 'exact' }, gaps: 0, pending: false, newest_at: 1790000000000, history: [{ name: '别礼', pulls: 31, status: 'lower_bound', obtained_at: 1790000000000 }] }
const wide = { ...summary.pools[0], total: 148, six_star: 2, five_star: 20, four_star: 126, unknown_rarity: 0, history, newest_at: 1788300000000 }

test('recent 6★ come newest first across pools, the latest card is marked and the latest pool is highlighted', t => {
  api(t, () => [200, {}])
  const root = mount(t, Panel, { accountId: 'r1', snap: { payload: { ...summary, total: 196, pools: [wide, second] }, fetched_at: '2026-09-24T12:00:00+08:00' } })
  const cards = by(root, 'article', 'six-card')
  assert.deepEqual(cards.map(node => content(nodes(node, 'strong')[0])), ['别礼', '提弗洛斯', '余烬'])
  assert.deepEqual(cards.map(node => String(node.props.class).includes('latest')), [true, false, false])
  assert.match(content(cards[0]), /别礼 ≥31 抽/)
  assert.match(content(cards[0]), /基础寻访/)
  const latest = by(root, 'article', 'pool-card').filter(node => String(node.props.class).includes('is-latest'))
  assert.equal(latest.length, 1)
  assert.match(content(latest[0]), /基础寻访/)
})

test('pool cards share the 12-column grid so every row is full and a single pool gets no highlight', t => {
  api(t, () => [200, {}])
  const many = Array.from({ length: 5 }, (_, index) => ({ ...wide, key: `pool-${index}`, label: `卡池${index}` }))
  const root = mount(t, Panel, { accountId: 'r1', snap: { payload: { ...summary, pools: many }, fetched_at: '2026-09-24T12:00:00+08:00' } })
  assert.deepEqual(by(root, 'article', 'pool-card').map(node => node.props.style['--span']), [4, 4, 4, 6, 6])
  const alone = mount(t, Panel, { accountId: 'r1', snap: { payload: { ...summary, pools: [wide] }, fetched_at: '2026-09-24T12:00:00+08:00' } })
  assert.equal(by(alone, 'article', 'pool-card').filter(node => String(node.props.class).includes('is-latest')).length, 0)
  assert.doesNotMatch(content(alone), /高亮为最近寻访的卡池/)
})

test('the overall ring never invents a split: a pool without a rarity count makes that share unknown', t => {
  api(t, () => [200, {}])
  const unsure = { ...second, key: 'u', label: '不明卡池', four_star: null, unknown_rarity: null }
  const root = mount(t, Panel, { accountId: 'r1', snap: { payload: { ...summary, pools: [wide, unsure] }, fetched_at: '2026-09-24T12:00:00+08:00' } })
  const ring = nodes(root, 'figure').find(node => node.props['aria-label'] === '全部卡池的稀有度占比')
  assert.ok(ring)
  assert.match(content(ring), /6★ 3 抽/); assert.match(content(ring), /5★ 27 抽/)
  assert.match(content(ring), /4★ 未知/); assert.match(content(ring), /未知 \/ 其他 未知/)
})

test('a bot image keeps every pool and history chip but has no rail, no highlight tag and no controls', t => {
  api(t, () => [200, {}])
  const root = mount(t, Panel, { imageMode: true, accountId: '', snap: { payload: { ...summary, pools: [wide, second] }, fetched_at: '2026-09-24T12:00:00+08:00' } })
  assert.equal(by(root, 'article', 'six-card').length, 0)
  assert.equal(by(root, 'article', 'pool-card').length, 2)
  for (const name of ['提弗洛斯', '余烬', '别礼']) assert.ok(content(root).includes(name), name)
  assert.equal(by(root, 'span', 'pool-latest').length, 0)
  assert.doesNotMatch(content(root), /最新/)
  for (const type of ['button', 'input', 'select', 'details']) assert.equal(nodes(root, type).length, 0, type)
})

test('QQ six-star pool history retains exact operator artwork and unknown names in compact rows',t=>{
 api(t,()=>{throw Error('image must not fetch')})
 const history=[{name:'秋栗',pulls:30,status:'exact'},{name:'未收录干员',pulls:null,status:'unknown'}]
 const root=mount(t,Panel,{imageMode:true,snap:{payload:{...summary,pools:[{...summary.pools[0],history}]}}})
 assert.deepEqual(nodes(root,'img').map(n=>n.props.src),['https://web.hycdn.cn/endfield/official-v4/_next/static/media/akekuri.3df4a3dc.png'])
 assert.match(content(root),/秋栗 30 抽.*未收录干员 未知/)
 assert.equal(nodes(root,'li').filter(n=>String(n.props.class).includes('six-image')).length,2)
 const web=mount(t,Panel,{snap:{payload:{...summary,pools:[{...summary.pools[0],history}]}}})
 assert.equal(nodes(web,'li').filter(n=>String(n.props.class).includes('six-image')).length,0)
})

test('recent and image-mode histories show weapons by pool kind and retain fallback names', async t => {
  const weaponPool = { ...summary.pools[0],key:'weapon:sample',kind:'weapon',label:'武库申领',
    history:[{name:'破碎君王',pulls:12,status:'exact',obtained_at:1792000000000},
      {name:'玉中身',pulls:0,status:'lower_bound',obtained_at:1791900000000}] }
  const characterPool = {...summary.pools[0],history:[{name:'祀',pulls:18,status:'lower_bound',obtained_at:1791800000000}]}
  const props = {accountId:'r1',snap:{payload:{...summary,pools:[weaponPool,characterPool]}}}
  const root = mount(t,Panel,props)
  const cards = by(root,'article','six-card')
  assert.deepEqual(cards.map(card=>nodes(card,'img')[0]?.props.alt),['破碎君王','玉中身','祀'])
  assert.ok(nodes(cards[0],'img')[0].props.src.startsWith('https://bbs.hycdn.cn/image/'))
  assert.match(content(cards[1]),/玉中身 ≥0 抽/)
  nodes(cards[0],'img')[0].props.onError()
  await nextTick()
  assert.equal(nodes(cards[0],'img').length,0)
  assert.match(content(cards[0]),/破碎君王/)
  const shared = mount(t,Panel,{...props,imageMode:true})
  assert.deepEqual(nodes(shared,'img').map(image=>image.props.alt),['破碎君王','玉中身','祀'])
})
