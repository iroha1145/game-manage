import test from 'node:test'
import assert from 'node:assert/strict'
import { gachaView, gachaPools } from './endfield-gacha-summary.js'
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
