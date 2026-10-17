// Chat images are read at a fraction of their encoded width. Retain the shared
// content and its hierarchy, but give every visible text run a readable size.
export function chatFontSize(size) {
  if (size <= 12) return 22
  if (size <= 15) return 26
  if (size <= 19) return 30
  if (size <= 27) return 34
  return 42
}

export function prepareChatLayout(source) {
  for (const supplement of source.querySelectorAll('.wuwa-supplement')) {
    if (![...supplement.children].some(child => child.tagName !== 'SUMMARY' && child.textContent.trim())) supplement.remove()
  }
  const view = source.ownerDocument.defaultView
  const text = [...source.querySelectorAll('*')].filter(element =>
    element.namespaceURI === 'http://www.w3.org/1999/xhtml' &&
    !element.closest('.qq-calendar, .sr-only, [hidden]') &&
    [...element.childNodes].some(node => node.nodeType === 3 && node.textContent.trim()))
  // Read first, then write: inherited styles must not be scaled a second time.
  const sizes = text.map(element => Number.parseFloat(view.getComputedStyle(element).fontSize) || 14)
  text.forEach((element, index) => {
    element.style.fontSize = `${element.matches('.render-observation') ? 22 : chatFontSize(sizes[index])}px`
    element.style.lineHeight = element.matches('h1,h2,h3,h4,strong,b') ? '1.35' : '1.5'
  })
  for (const row of source.querySelectorAll('.wuwa-draws tbody > tr')) {
    const cells = [...row.children]
    if (cells[3]) cells[3].dataset.chatLabel = '星级 '
    if (cells[4]) cells[4].dataset.chatLabel = '数量 '
  }
}
