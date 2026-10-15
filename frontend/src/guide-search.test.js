import test from 'node:test'
import assert from 'node:assert/strict'
import { filterGuides, guideCharacterIds, guideForCharacter, ownedGuideRoles } from './guide-search.js'
const guides=[{id:'哈尼娅',name:'哈尼娅',aliases:['哈妮娅'],source_id:1,status:'reviewed'}, {id:'主角·零',name:'主角·零',aliases:['零','主角']}, {id:'黑羽',name:'黑羽'}]
test('guide search reuses aliases/pinyin while links retain original objects and form identity', () => {
  assert.deepEqual(filterGuides('nte',guides,' HNY '),[guides[0]])
  assert.equal(guideForCharacter('nte',guides,'1020'),guides[0])
  assert.equal(guideForCharacter('nte',guides,'1046'),null,'unqualified zero guide cannot become a form-specific guide')
  assert.deepEqual(guideCharacterIds('nte',guides[1]),['1046','1051'])
  assert.deepEqual(ownedGuideRoles('nte',guides[0],[{id:'1020',name:'哈妮娅'},{id:'x',name:'哈尼娅'}]),[{id:'1020',name:'哈妮娅'}])
  assert.deepEqual(filterGuides('nte',guides,'娜娜利'),[])
})
