import { catalogEntries, characterId, normalizeSearch, searchCharacters } from './character-search.js'

// Guide objects are never rebuilt: source IDs, fingerprints and review state
// remain on the original object selected through the form ID.
export function guideCharacterIds(game, guide) {
  if (game === 'wuthering_waves') return [String(guide.id)]
  const names=[guide.name,...(guide.aliases || [])].map(normalizeSearch)
  return catalogEntries(game).filter(row=>[row.canonical_name,...row.aliases].some(name=>names.includes(normalizeSearch(name)))).map(row=>row.character_id)
}
export function guideForCharacter(game,guides,id) {
  return guides.find(guide=> {
    const ids=guideCharacterIds(game,guide)
    return ids.length===1 && ids[0]===String(id)
  }) || null
}
export function ownedGuideRoles(game,guide,roles) {
  const ids=guideCharacterIds(game,guide)
  return roles.filter(role=>ids.length ? ids.includes(characterId(role)) : normalizeSearch(role.name)===normalizeSearch(guide.name))
}
export function filterGuides(game,guides,query) {
  const key=normalizeSearch(query)
  if(!key)return guides
  const proxies=guides.flatMap(guide=> {
    const ids=guideCharacterIds(game,guide)
    return (ids.length?ids:['']).map(id=>({character_id:id,name:guide.name,guide}))
  })
  const found=searchCharacters(game,query,proxies)
  if(found.length)return [...new Set(found.map(item=>item.entry.guide))]
  return guides.filter(guide=>[guide.element,guide.role,...(guide.aliases || [])].some(value=>normalizeSearch(value).includes(key)))
}
