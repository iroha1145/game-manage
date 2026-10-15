import test from 'node:test'
import assert from 'node:assert/strict'
import { selectOperators, profileReport, operatorImage, operatorArtwork } from './endfield-reports.js'

test('operator filters combine name rarity and profession; stable numeric sorting preserves zero and unknown last', () => {
  const items = [{ id:'missing',name:'未知',rarity:6,profession:'近卫' },{id:'zero',name:'管理员零',level:0,rarity:6,profession:'近卫'},
    {id:'high',name:'管理员甲',level:70,rarity:6,profession:'近卫'},{id:'same',name:'管理员乙',level:70,rarity:5,profession:'先锋'}]
  assert.deepEqual(selectOperators(items).map(item=>item.id),['high','same','zero','missing'])
  assert.deepEqual(selectOperators(items,{search:'管理员',rarity:'6',profession:'近卫'}).map(item=>item.id),['high','zero'])
  assert.equal(items[0].id,'missing')
})

test('source reports remain authoritative and old profiles do not invent todos or aggregate values', () => {
  const report={schema_version:1,overview:{todos:[]}}
  assert.equal(profileReport({report}),report)
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
