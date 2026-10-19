import test from 'node:test'
import assert from 'node:assert/strict'
import { gachaView, gachaPools, recentSixStars, sixPullsText, sixPullsParts, poolTotal, poolGroups, poolPace, pullRuler, rarityShares, syncStatus } from './endfield-gacha-summary.js'
const snaps={account:{payload:{role_id:'r',nickname:'本人'}},gacha:{stale:true,payload:{schema_version:1,role_id:'r',report:{schema_version:1,role_id:'r',total:42}}}}
test('local passport identity keeps ordinary stale records but blocks wrong role and invalid credentials',()=>{
 assert.equal(gachaView({snaps,configured:true,authAccount:{configured:true,state:'connected'}}).snapshot,snaps.gacha)
 for(const overrides of [{configured:false},{authAccount:{state:'expired'}},{authAccount:{configured:false}},{snaps:{...snaps,gacha:{...snaps.gacha,poll_status:{state:'auth_expired'}}}},{snaps:{...snaps,gacha:{payload:{role_id:'other'}}}},{snaps:{...snaps,gacha:{payload:{role_id:'r',report:{role_id:'other'}}}}}]) {
  assert.equal(gachaView({snaps,...overrides}).snapshot,null)
 }
 assert.equal(gachaView({snaps:{account:snaps.account}}).accountId,'r')
})
test('cloud requires same active Eagle grant and role envelopes and never shares Skland data',()=>{
 const cloudAccount={account_id:'a',provider:'hypergryph',state:'active',roles:[{role_id:'r'}]}, cloudRole='r'
 const scoped=Object.fromEntries(Object.entries(snaps).map(([key,value])=>[key,{...value,account_id:'a',role_id:'r'}]))
 assert.equal(gachaView({snaps:scoped,cloudAccount,cloudRole}).snapshot,scoped.gacha)
 for(const account of [{...cloudAccount,provider:'skland'},{...cloudAccount,state:'expired'},{...cloudAccount,roles:[]}])assert.equal(gachaView({snaps:scoped,cloudAccount:account,cloudRole}).snapshot,null)
 assert.equal(gachaView({snaps,cloudAccount,cloudRole}).snapshot,null)
 for(const field of ['account_id','role_id'])for(const key of ['account','gacha']) {
  const wrong={...scoped,[key]:{...scoped[key],[field]:'wrong'}}
  assert.equal(gachaView({snaps:wrong,cloudAccount,cloudRole}).snapshot,null)
 }
})
test('legacy pool coverage is bounded and absent rarity counts stay unknown',()=>{
 const pool={six_star:51,total:100,history:Array.from({length:50},()=>({name:'A'}))}
 const [value]=gachaPools({pools:[pool]});assert.equal(value.history_available,50);assert.equal(value.history_total,51);assert.equal(value.history_truncated,true);assert.equal(value.history_limit,null);assert.equal(value.four_star,null)
 assert.equal(gachaPools({pools:[{...pool,six_star:40}]})[0].history_total,null)
 assert.equal(gachaPools({pools:[pool],report:{schema_version:1,pools:[]}}).length,0)
})

test('cloud envelope UUIDs and upstream game UID remain separate identity namespaces',()=>{
 const cloudRole='aaaaaaaaaaaa4123a12345678bbbbbbbb', accountId='internal-account'
 const cloudAccount={account_id:accountId,provider:'hypergryph',state:'active',roles:[{role_id:cloudRole}]}
 const account={account_id:accountId,role_id:cloudRole,payload:{role_id:'100123456',nickname:'本人'}}
 const gacha={account_id:accountId,role_id:cloudRole,payload:{schema_version:1,role_id:'100123456',report:{schema_version:1,role_id:'100123456'}}}
 assert.equal(gachaView({snaps:{account,gacha},cloudAccount,cloudRole}).snapshot,gacha)
 for(const wrong of [{...gacha,role_id:'other-internal-role'},{...gacha,payload:{...gacha.payload,role_id:'100654321'}},{...gacha,payload:{...gacha.payload,report:{role_id:'100654321'}}}]) {
  assert.equal(gachaView({snaps:{account,gacha:wrong},cloudAccount,cloudRole}).snapshot,null)
 }
})

test('pool coverage prefers explicit valid history total and marks contradictory counts unknown',()=>{
 const pool={six_star:55,history_total:60,history:[{name:'a'}]}
 assert.equal(gachaPools({pools:[pool]})[0].history_total,60)
 assert.equal(gachaPools({pools:[{...pool,history_total:0}]})[0].history_total,null)
 assert.equal(gachaPools({pools:[{...pool,history_total:null}]})[0].history_total,55)
 assert.equal(gachaPools({pools:[{...pool,history_total:'0',history:[]}]})[0].history_total,0)
})

test('recent 6★ merge every pool newest first, keep unknown times last and carry the pool label', () => {
  const pools = [
    { key: 'a', label: '特许寻访', history: [{ name: '甲', obtained_at: 2000, pulls: 10, status: 'exact' }, { name: '乙', obtained_at: 500, pulls: 30, status: 'lower_bound' }] },
    { key: 'b', label: '基础寻访', history: [{ name: '丙', obtained_at: 3000 }, { name: '丁', obtained_at: null }, { name: '戊', obtained_at: 2000 }] },
  ]
  const result = recentSixStars(pools)
  assert.deepEqual(result.map(item => item.name), ['丙', '甲', '戊', '乙', '丁'])
  assert.deepEqual(result.slice(0, 2).map(item => item.pool_label), ['基础寻访', '特许寻访'])
  assert.equal(recentSixStars(pools, 2).length, 2)
  assert.deepEqual(recentSixStars([{ key: 'x' }, null]), [])
  assert.equal(pools[0].history[0].pool_label, undefined)
})

test('6★ pull wording separates exact, minimum and unknown values', () => {
  assert.equal(sixPullsText({ pulls: 66, status: 'exact' }), '66 抽')
  assert.equal(sixPullsText({ pulls: 0, status: 'exact' }), '0 抽')
  assert.equal(sixPullsText({ pulls: 52, status: 'lower_bound' }), '≥52 抽')
  assert.equal(sixPullsText({ pulls: 12, status: 'unknown' }), '未知')
  assert.equal(sixPullsText({ pulls: null, status: 'exact' }), '未知')
  assert.deepEqual(sixPullsParts({ pulls: 52, status: 'lower_bound' }), { prefix: '≥', count: 52, unit: '抽' })
  assert.deepEqual(sixPullsParts({ pulls: 0, status: 'exact' }), { prefix: '', count: 0, unit: '抽' })
  assert.equal(sixPullsParts({ pulls: 12, status: 'unknown' }), null)
  assert.equal(sixPullsParts(undefined), null)
})

test('pool totals are unknown unless every pool states the count, and zero stays a real total', () => {
  assert.equal(poolTotal([{ six_star: 2 }, { six_star: 0 }, { six_star: 3 }], 'six_star'), 5)
  assert.equal(poolTotal([{ six_star: 2 }, { six_star: null }], 'six_star'), null)
  assert.equal(poolTotal([{ six_star: 2 }, {}], 'six_star'), null)
  assert.equal(poolTotal([], 'six_star'), null)
  assert.equal(poolTotal([{ five_star: '7' }], 'five_star'), 7)
})

test('pools group into character then weapon pools, keeping ledger order and dropping empty groups', () => {
  const pools = [{ key: 'w1', kind: 'weapon' }, { key: 'c1', kind: 'character' }, { key: 'c2', kind: 'character' }, null]
  assert.deepEqual(poolGroups(pools).map(group => [group.label, group.pools.map(pool => pool.key)]), [['干员寻访', ['c1', 'c2']], ['武器申领', ['w1']]])
  assert.deepEqual(poolGroups([{ key: 'w', kind: 'weapon' }]).map(group => group.kind), ['weapon'])
  assert.deepEqual(poolGroups([]), [])
})

test('pace averages exact intervals only and names the fastest and slowest once two differ', () => {
  const fast = { name: '快', pulls: 12, status: 'exact' }, slow = { name: '慢', pulls: 80, status: 'exact' }
  const pace = poolPace({ history: [fast, { name: '下限', pulls: 5, status: 'lower_bound' }, slow, { name: '未知', pulls: null, status: 'exact' }, { name: '?', pulls: 3, status: 'unknown' }] })
  assert.deepEqual({ ...pace, fastest: pace.fastest.name, slowest: pace.slowest.name }, { count: 2, average: 46, fastest: '快', slowest: '慢' })
  assert.equal(poolPace({ history: [{ pulls: 10, status: 'exact' }, { pulls: 11, status: 'exact' }, { pulls: 11, status: 'exact' }] }).average, 10.7)
  for (const one of [[fast], [fast, { ...fast }]]) {
    const single = poolPace({ history: one })
    assert.equal(single.fastest, null); assert.equal(single.slowest, null); assert.equal(single.average, 12)
  }
  assert.deepEqual(poolPace({ history: [{ pulls: 9, status: 'lower_bound' }] }), { count: 0, average: null, fastest: null, slowest: null })
  assert.deepEqual(poolPace(null), { count: 0, average: null, fastest: null, slowest: null })
})

test('a ruler per kind spans the longest stated 6★ up to the next ten and assumes no pity rule', () => {
  const pools = [{ kind: 'character', history: [{ pulls: 66, status: 'exact' }, { pulls: 74, status: 'lower_bound' }, { pulls: 99, status: 'unknown' }] },
    { kind: 'weapon', history: [{ pulls: 30, status: 'exact' }] }, { kind: 'character', history: [{ pulls: 80, status: 'exact' }] }]
  assert.equal(pullRuler(pools, 'character'), 80)
  assert.equal(pullRuler(pools, 'weapon'), 30)
  assert.equal(pullRuler([{ kind: 'weapon', history: [{ pulls: 3, status: 'exact' }] }], 'weapon'), 10)
  assert.equal(pullRuler([{ kind: 'character', history: [{ pulls: 0, status: 'lower_bound' }] }], 'character'), 10)
  assert.equal(pullRuler([{ kind: 'character', history: [{ pulls: null, status: 'exact' }] }], 'character'), null)
  assert.equal(pullRuler(pools.slice(0, 1), 'weapon'), null)
})

test('rarity shares divide by the pool total and leave an unstated count unknown', () => {
  const shares = rarityShares({ total: 200, six_star: 4, five_star: 20, four_star: null, unknown_rarity: 0 })
  assert.deepEqual(shares.map(part => [part.label, part.count, part.share]), [['6★', 4, .02], ['5★', 20, .1], ['4★', null, null], ['未知 / 其他', 0, 0]])
  assert.ok(rarityShares({ total: 0, six_star: 0 }).every(part => part.share == null))
})

test('sync status puts an unfinished scan first and only calls a proven scan complete', () => {
  assert.equal(syncStatus({ complete: false }, { pending: false }).label, '部分待同步')
  assert.equal(syncStatus({ complete: true }, { pending: true }).tone, 'warn')
  assert.equal(syncStatus({ complete: true }, null).label, '同步完成')
  assert.equal(syncStatus({ complete: null }, { pending: null }).label, '完整性未知')
  assert.equal(syncStatus(null, null).tone, 'unknown')
})
