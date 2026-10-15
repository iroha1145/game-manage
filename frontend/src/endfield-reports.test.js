import test from 'node:test'
import assert from 'node:assert/strict'
import { selectOperators, selectMedals, profileReport, operatorImage, operatorArtwork } from './endfield-reports.js'

test('operator filters combine name rarity and profession; stable numeric sorting preserves zero and unknown last', () => {
  const items = [{ id:'missing',name:'未知',rarity:6,profession:'近卫' },{id:'zero',name:'管理员零',level:0,rarity:6,profession:'近卫'},
    {id:'high',name:'管理员甲',level:70,rarity:6,profession:'近卫'},{id:'same',name:'管理员乙',level:70,rarity:5,profession:'先锋'}]
  assert.deepEqual(selectOperators(items).map(item=>item.id),['high','same','zero','missing'])
  assert.deepEqual(selectOperators(items,{search:'管理员',rarity:'6',profession:'近卫'}).map(item=>item.id),['high','zero'])
  assert.equal(items[0].id,'missing')
})

test('source reports remain authoritative and old profiles do not invent todos or aggregate values', () => {
  const report={schema_version:1,overview:{todos:[]}}
  assert.equal(profileReport({report}).overview,report.overview)
  const legacy=profileReport({stamina:{current:0},operators:[],progress:[{name:'每日',cur:0,total:100}]})
  assert.equal(legacy.overview.stamina.current,0)
  assert.equal(legacy.overview.todos,null)
  assert.equal(legacy.training.summary.average_level,undefined)
  assert.equal(legacy.training.summary.listed_count,null)
  assert.equal(profileReport({regions:[],ship:[]}).regions.summary.region_count,null)
  assert.equal(profileReport({regions:[],ship:[]}).ship.summary.room_count,null)
})

test('operator artwork accepts only reviewed HTTPS image origins and no arbitrary media URLs', () => {
  assert.equal(operatorImage('https://example.com/avatar.png'),null)
  assert.equal(operatorImage('http://bbs.hycdn.cn/avatar.png'),null)
  assert.equal(operatorImage('https://bbs.hycdn.cn/avatar.svg'),null)
  assert.equal(operatorImage('https://bbs.hycdn.cn/avatar.png?token=x'),null)
  assert.equal(operatorImage('https://user:secret@bbs.hycdn.cn/avatar.png'),null)
})

test('official artwork fallback uses exact website keys or unique names, not inferred character IDs', () => {
  assert.match(operatorArtwork({id:'akekuri'}),/akekuri\./)
  assert.match(operatorArtwork({id:'char_123_unknown',name:'秋栗'}),/akekuri\./)
  assert.equal(operatorArtwork({id:'char_123_akekuri'}),null)
  assert.equal(operatorArtwork({name:'管理员'}),null)
  assert.ok(operatorArtwork({id:'endministrator1',name:'管理员'}))
  assert.equal(operatorArtwork({name:'秋栗',avatar_url:'https://bbs.hycdn.cn/known.png'}),'https://bbs.hycdn.cn/known.png')
})

test('detail portraits use reviewed exact identities, preserving ambiguous and unknown fallbacks', () => {
  const portrait=operatorArtwork({name:'佩丽卡'},{portrait:true})
  assert.match(portrait,/prelica\./)
  assert.notEqual(portrait,operatorArtwork({name:'佩丽卡'}))
  assert.equal(operatorArtwork({name:'管理员'},{portrait:true}),null)
  assert.equal(operatorArtwork({id:'char_123_perlica'},{portrait:true}),null)
  assert.equal(operatorArtwork({name:'未收录',avatar_url:'https://bbs.hycdn.cn/known.png'},{portrait:true}),'https://bbs.hycdn.cn/known.png')
})

test('legacy honors preserve all listed medals, confirmed zeros, unknowns and observed icon variants', () => {
  const medals=Array.from({length:12},(_,id)=>({achievementData:{id,name:'奖章'+id,initIcon:'init',reforge2Icon:'two',reforge3Icon:'three',platedIcon:'plated'},level:3,isPlated:id===0,obtainTs:1792029600}))
  const honor=profileReport({achievements:{count:0,medals}}).honor
  assert.equal(honor.items.length,12)
  assert.equal(honor.summary.declared_count,0)
  assert.equal(honor.items[0].icon_url,'plated')
  assert.equal(honor.items[1].icon_url,'three')
  assert.match(honor.items[0].obtained_at,/^2026-/)
  assert.equal(profileReport({achievements:{medals:[]}}).honor.summary.listed_count,null)
  assert.equal(profileReport({availability:{honor:true},achievements:{medals:[]}}).honor.summary.listed_count,0)
  const unknown=profileReport({achievements:{medals:[{obtainTs:'no',level:false}]}}).honor.items[0]
  assert.equal(unknown.level,null)
  assert.equal(unknown.obtained_at,null)
  assert.equal(unknown.is_plated,null)
})

test('saved region reports and legacy collection-only profiles gain names without changing observations', () => {
  const region={levels:[{id:'map01_lv001'}],collections:[{level_id:'map01_lv001',name:'上游新名称'}],areas:[{id:'map01_lv001',name:'枢纽区',collections:[]},{id:'map02_lv002',name:null}]}
  const saved={schema_version:1,regions:{items:[region]}}
  const result=profileReport({report:saved}).regions.items[0]
  assert.deepEqual(result.areas.map(item=>item.name),['上游新名称','武陵城'])
  assert.equal(region.areas[0].name,'枢纽区')
  const legacy=profileReport({regions:[{collections:[{level_id:'map02_lv001',chest_count:0},{level_id:'future'}]}]}).regions.items[0]
  assert.deepEqual(legacy.areas.map(item=>item.name),['景玉谷','future'])
  assert.equal(legacy.areas[0].chests.count,0)
  assert.equal(legacy.areas[0].chests.total,undefined)
})

test('legacy region money spelling alias keeps known zero before conut',()=>{
 const report=profileReport({regions:[{money:{count:0,conut:9}},{money:{count:null,conut:9}},{money:{conut:7}}]})
 assert.deepEqual(report.regions.items.map(item=>item.money.count),[0,9,7])
})

test('honor categories backfill only an unambiguous observed ID and preserve explicit unknown',()=>{
 const raw=[{achievementData:{id:0,cateName:' 探索 '}},{achievementData:{id:'dupe',cateName:'甲'}},{achievementData:{id:'dupe',cateName:'乙'}},{achievementData:{id:'explicit',cateName:'探索'}},{achievementData:{id:'invalid',cateName:42}}]
 const items=[{id:'0'},{id:'dupe'},{id:'explicit',category:null},{id:'invalid'},{id:'new',category:' 战斗 '}]
 const result=profileReport({achievements:{medals:raw},report:{schema_version:1,honor:{items}}}).honor.items
 assert.deepEqual(result.map(item=>item.category),['探索',null,null,null,'战斗'])
 assert.equal(items[0].category,undefined)
 assert.equal(profileReport({achievements:{medals:raw}}).honor.items[0].category,'探索')
})

test('honor filters intersect while time sorting leaves unknown dates last and never mutates source',()=>{
 const items=[{id:'u',name:'未知时间',category:null},{id:'a',name:'探索甲',category:'探索',obtained_at:'2025-10-15T00:00:00Z'},{id:'b',name:'探索乙',category:'探索',obtained_at:'2026-10-15T00:00:00Z'},{id:'c',name:'战斗甲',category:'战斗',obtained_at:'invalid'}]
 assert.deepEqual(selectMedals(items).map(item=>item.id),['b','a','u','c'])
 assert.deepEqual(selectMedals(items,{sort:'oldest'}).map(item=>item.id),['a','b','u','c'])
 assert.deepEqual(selectMedals(items,{sort:'source'}),items)
 assert.deepEqual(selectMedals(items,{search:'甲',category:'探索'}).map(item=>item.id),['a'])
 assert.deepEqual(selectMedals(items,{category:null}).map(item=>item.id),['u'])
 assert.equal(items[0].id,'u')
})
