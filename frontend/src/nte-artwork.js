// Exact asset IDs and path spellings from Tajiduo's game-records frontend.
const base = 'https://webstatic.tajiduo.com/bbs/yh-game-records-web-source/'
export function nteAssetImage(kind, id) {
  if (typeof id !== 'string') return ''
  if (kind === 'realestate' && /^bigword_[a-z]+_\d+$/.test(id)) return `${base}realestate/detail/${id}.png`
  if (kind === 'vehicles' && /^vehicle\d{3}$/.test(id)) return `${base}verhicle/wide/${id}.png`
  return ''
}
