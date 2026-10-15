import test from 'node:test'
import assert from 'node:assert/strict'
import { shipResident, shipPercent, SHIP_CONVERSION_MODEL } from './endfield-ship.js'
import { profileReport } from './endfield-reports.js'

test('ship uses the reviewed static ranges and exact trust boundaries shared with QQ', () => {
  for (const [raw, percent, stage] of [[0,0,'友好'],[3,1,'友好'],[57,19,'友好'],[69,23,'友好'],[299,99,'友好'],[300,100,'亲近'],[312,101,'亲近'],[336,103,'亲近'],[996,158,'亲近'],[1499,199,'亲近'],[1500,200,'信任'],[2000,200,'信任']]) {
    const item=shipResident({physicalStrength:raw,favorability:raw})
    assert.equal(item.trust_percent,percent,`trust ${raw}`)
    assert.equal(item.trust_level_name,stage)
  }
  assert.equal(shipResident({physicalStrength:10000}).mood_percent,100)
  const outside=shipResident({physicalStrength:10001})
  assert.equal(outside.mood_percent,null);assert.equal(outside.mood_raw,10001)
  for(const [value, shown] of [[0,'0%'],[33.35,'33.4%'],[0.05,'0.1%'],[99.99,'100%'],[200,'200%'],[null,'未知']]) assert.equal(shipPercent(value),shown)
})

test('ship decimal observations reject coercion and cross-language numeric spellings',()=>{
  for(const value of [null,undefined,true,false,{},[],NaN,Infinity,-1,'',' ','NaN','Infinity','0x10','0b11','0o10','1_0','１２','١٢']) {
    const item=shipResident({physicalStrength:value,favorability:value})
    assert.equal(item.mood_raw,null,`${String(value)} mood`);assert.equal(item.trust_raw,null)
    assert.equal(item.mood_percent,null);assert.equal(item.trust_percent,null);assert.equal(item.trust_level_name,null)
  }
  for(const [raw,value] of [['+3e2',300],['3E+2',300],['300.',300],['.5',.5],['-.0',-0],[' 0 ',0]]) {
    const item=shipResident({physicalStrength:raw,favorability:raw})
    assert.equal(item.mood_raw,value);assert.equal(item.trust_raw,value)
  }
})

test('new derived nulls remain authoritative while old report and raw residents gain the model',()=>{
  const original={id:'a',mood_raw:5000,trust_raw:312,mood_percent:null,trust_percent:null,trust_level_name:null}
  assert.deepEqual(shipResident(original),original)
  const old={schema_version:1,ship:{rooms:[{operators:[{id:'a',mood_raw:3335,trust_raw:996}]}]},training:{items:[{id:'a',name:'干员甲',avatar_url:'https://bbs.hycdn.cn/a.png'}]}}
  const result=profileReport({report:old}).ship
  assert.equal(result.rooms[0].operators[0].mood_percent,33.35)
  assert.equal(result.rooms[0].operators[0].trust_percent,158)
  assert.equal(result.rooms[0].operators[0].name,'干员甲')
  assert.equal(result.conversion_model.id,SHIP_CONVERSION_MODEL.id)
  assert.equal(old.ship.rooms[0].operators[0].mood_percent,undefined)
  const legacy=profileReport({ship:[{operators:[{charId:'a',physicalStrength:0,favorability:0}]}],operators:[{id:'a',name:'干员甲',avatar_url:'https://bbs.hycdn.cn/a.png'}]}).ship
  assert.equal(legacy.rooms[0].operators[0].name,'干员甲')
  assert.equal(legacy.rooms[0].operators[0].avatar_url,'https://bbs.hycdn.cn/a.png')
  assert.equal(legacy.rooms[0].operators[0].mood_percent,0)
})

test('legacy ship summaries require complete room and staff observation, preserving explicit report null',()=>{
  const summary=payload=>profileReport(payload).ship.summary
  assert.deepEqual(summary({availability:{ship:true},ship:[]}),{room_count:0,staffed_rooms:0,operator_slots:0})
  assert.deepEqual(summary({ship:[]}),{room_count:null,staffed_rooms:null,operator_slots:null})
  const known={availability:{ship:true},ship:[{operators:[],operators_available:true},{operators:[{charId:'a'},{charId:'b'}]}]}
  assert.deepEqual(summary(known),{room_count:2,staffed_rooms:1,operator_slots:2})
  assert.deepEqual(summary({...known,ship:[...known.ship,{operators:[]}]}),{room_count:3,staffed_rooms:null,operator_slots:null})
  assert.deepEqual(summary({...known,ship:[{operators:[{charId:'a'}],operators_available:false}]}),{room_count:1,staffed_rooms:null,operator_slots:null})
  assert.equal(summary({report:{schema_version:1,ship:{available:true,rooms:[],summary:{staffed_rooms:null}}}}).staffed_rooms,null)
})
