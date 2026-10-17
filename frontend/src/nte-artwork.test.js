import test from 'node:test'
import assert from 'node:assert/strict'
const art=await import('./nte-artwork.js').catch(()=>({}))
test('asset art uses exact official IDs and rejects URL/path injection',()=>{
 assert.equal(art.nteAssetImage?.('realestate','bigword_l_1'),'https://webstatic.tajiduo.com/bbs/yh-game-records-web-source/realestate/detail/bigword_l_1.png')
 assert.equal(art.nteAssetImage?.('vehicles','vehicle008'),'https://webstatic.tajiduo.com/bbs/yh-game-records-web-source/verhicle/wide/vehicle008.png')
 for(const id of ['../vehicle008','vehicle008?x','https://evil/a','v1',''])assert.equal(art.nteAssetImage?.('vehicles',id),'')
 assert.equal(art.nteAssetImage?.('teams','vehicle008'),'')
})
