import test from 'node:test'
import assert from 'node:assert/strict'
import { gachaView, gachaPools, recentSixStars, sixPullsText, sixPullsParts, poolTotal, latestPoolIndex, poolSpans } from './endfield-gacha-summary.js'
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

test('the latest pool is the one with the newest pull, and unknown times never win', () => {
  assert.equal(latestPoolIndex([{ newest_at: 100 }, { newest_at: 900 }, { newest_at: 300 }]), 1)
  assert.equal(latestPoolIndex([{ newest_at: null }, { newest_at: 5 }]), 1)
  assert.equal(latestPoolIndex([{}, { newest_at: 'x' }]), -1)
  assert.equal(latestPoolIndex([]), -1)
})

test('pool card spans fill every row of the 12-column grid', () => {
  assert.deepEqual(poolSpans(5), [4, 4, 4, 6, 6])
  assert.deepEqual(poolSpans(4), [3, 3, 3, 3])
  assert.deepEqual(poolSpans(7), [4, 4, 4, 6, 6, 6, 6])
  assert.deepEqual(poolSpans(8), [4, 4, 4, 4, 4, 4, 6, 6])
  assert.deepEqual(poolSpans(1), [12])
  for (let count = 1; count <= 20; count++) {
    const spans = poolSpans(count)
    assert.equal(spans.length, count)
    // Rows are runs of equal spans; each run must add up to 12.
    let row = 0
    for (const span of spans) { row += span; if (row === 12) row = 0; assert.ok(row < 12) }
    assert.equal(row, 0)
  }
  for (const none of [0, -1, 2.5, NaN, undefined]) assert.deepEqual(poolSpans(none), [])
})
