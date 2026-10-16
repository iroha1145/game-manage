import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { searchCharacters } from './character-search.js'
import { filterRoles } from './nte-roles.js'
import { getWuwaGuide } from './wuwa-guides.js'
const cases = JSON.parse(readFileSync(new URL('../../tests/fixtures/character_search.json', import.meta.url)))
for (const c of cases) test(`${c.game}: ${c.query}`, () => {
  const found = searchCharacters(c.game, c.query)
  assert.deepEqual(found.map(item => item.character_id), c.ids)
  assert.ok(found.every(item => item.match === c.match))
})
const exact = (game, query, entries) => searchCharacters(game, query, entries).filter(item => item.match === 'exact').map(item => item.entry)
test('forms stay ambiguous, exact aliases precede partials, and filters/favorites retain identity', () => {
  const entries = [{id:'1019',name:'薄荷',quality:'A',level:1}, {id:'other',name:'BH extra',quality:'S',level:99}]
  assert.deepEqual(exact('nte', 'BH', entries), [entries[0]])
  assert.deepEqual(filterRoles(entries, {search:'bohe', favoritesOnly:true, favorites:['1019']}), [entries[0]])
  const forms = [{role_id:'1408',name:'漂泊者',attribute:'气动'}, {role_id:'unknown',name:'漂泊者',attribute:'湮灭'}]
  assert.equal(exact('wuthering_waves','漂泊者',forms).length, 2)
  assert.deepEqual(exact('wuthering_waves','漂泊者·湮灭',forms), [forms[1]])
  assert.equal(getWuwaGuide('unknown'),null)
})
