import catalog from '../../src/game_assistant/character-search-catalog.json' with { type: 'json' }

export const normalizeSearch = value => String(value ?? '').normalize('NFKC').toLowerCase().replace(/[\s.·・•‧]/gu, '')
export const characterId = entry => String(entry?.character_id ?? entry?.role_id ?? entry?.id ?? '').trim()
export const catalogEntries = game => catalog.characters.filter(row => row.game === game)
const publicName = entry => String(entry?.canonical_name ?? entry?.name ?? '')
export function characterLabel(game, entry) {
  const row = catalogEntries(game).find(row => row.character_id === characterId(entry))
  if (row) return row.canonical_name
  const form = entry?.form || entry?.attribute || ''
  return publicName(entry) + (form ? `·${form}` : '')
}
function terms(game, entry) {
  const row = catalogEntries(game).find(row => row.character_id === characterId(entry))
  return [...new Set([characterId(entry), publicName(entry), characterLabel(game, entry), ...(row ? [row.canonical_name,...row.aliases,...row.pinyin,...row.initials] : [])].map(normalizeSearch).filter(Boolean))]
}
function oneEdit(a,b) {
  if (Math.abs(a.length-b.length)>1) return false
  let i=0,j=0,edits=0
  while(i<a.length && j<b.length) {
    if(a[i]===b[j]) { i++;j++;continue }
    if(++edits>1) return false
    if(a.length>=b.length)i++
    if(b.length>=a.length)j++
  }
  return edits+(i<a.length || j<b.length ? 1:0)<=1
}
export function searchCharacters(game, query, entries = catalogEntries(game)) {
  const key=normalizeSearch(query)
  if(!key) return []
  const found = entries.filter(entry=>entry && typeof entry==='object').map(entry=> {
    const values=terms(game,entry)
    const score=values.includes(key)?0:values.some(v=>v.includes(key))?1:key.length>=2 && !/\d/u.test(key) && values.some(v=>v.length>=2 && !/\d/u.test(v) && oneEdit(key,v))?2:3
    return {entry,character_id:characterId(entry),canonical_name:characterLabel(game,entry),match:['exact','partial','suggestion'][score],score}
  }).filter(item=>item.score<3).sort((a,b)=>a.score-b.score)
  const exact=found.filter(item=>item.score===0)
  if(exact.length) return exact
  if(catalog.characters.some(row=>row.game!==game && terms(row.game,row).includes(key))) return []
  return found
}
