import { formatBeijingDateTime } from './calendar.js'

export const CHAT_PAGE_HEIGHT = 1440
const HEADING = 'h1,h2,h3,h4,header,summary,thead,[data-render-heading],.cap-title,.timeline-header'
const RECORD = '[data-render-block],article,li,tr,.role-card,.wuwa-chain,.wuwa-tile,.pull-row,.ef-operator,.ef-medal,.challenge-group,dl > div'

// Clone authorized component content, breaking at records first. An oversized
// description continues onto another page without cropping or shrinking text.
export function paginateContent(source, target, input, height = CHAT_PAGE_HEIGHT) {
  const document = source.ownerDocument
  const pages = []
  const origins = new WeakMap()
  let current
  function newPage() {
    if (pages.length >= 100) throw Error('render_page_limit')
    const page = document.createElement('section')
    page.className = 'render-page'
    const header = document.createElement('header')
    header.className = 'render-page-header'
    const title = document.createElement('h1')
    title.textContent = input.title
    const time = document.createElement('p')
    time.textContent = `${formatBeijingDateTime(input.as_of)} · 北京时间`
    header.append(title, time)
    const body = document.createElement('div')
    body.className = 'render-page-body'
    const footer = document.createElement('footer')
    footer.className = 'render-page-footer'
    // Reserve the longest marker and continuation command before measuring.
    footer.innerHTML = '<span></span><span></span>'
    footer.children[0].textContent = '第 100 / 100 页'
    footer.children[1].textContent = `下一页：${input.next_command} 100`
    page.append(header, body, footer)
    target.append(page)
    pages.push(page)
    current = { page, body, footer, containers: new Map(), headings: new Map(), units: 0 }
    return current
  }
  const measuredHeight = page => Math.max(page.offsetHeight, page.scrollHeight, Math.ceil(page.getBoundingClientRect().height))
  const fits = () => measuredHeight(current.page) <= height
  function append(node, ancestors) {
    let host = current.body
    const created = []
    const headings = []
    for (const [index, ancestor] of ancestors.entries()) {
      if (current.containers.has(ancestor)) host = current.containers.get(ancestor)
      else {
        const clone = ancestor.cloneNode(false)
        host.append(clone)
        created.push(clone)
        current.containers.set(ancestor, clone)
        host = clone
      }
      const branch = ancestors[index + 1] || origins.get(node) || node
      const siblings = [...ancestor.childNodes].filter(child => child.nodeType === 1 || child.nodeType === 3 && child.textContent.trim())
      const before = siblings.slice(0, Math.max(0, siblings.indexOf(branch)))
      const isHeading = child => child.nodeType === 1 && child.matches(HEADING)
      const leading = []
      for (const child of before) { if (!isHeading(child)) break; leading.push(child) }
      const trailing = []
      for (const child of before.toReversed()) { if (!isHeading(child)) break; trailing.unshift(child) }
      const nearest = before.filter(isHeading).at(-1)
      const displayed = current.headings.get(ancestor) || new Set()
      for (const heading of new Set([...leading, ...trailing, ...(nearest ? [nearest] : [])])) {
        if (displayed.has(heading)) continue
        const copy = heading.cloneNode(true)
        host.append(copy)
        headings.push({ancestor, copy, original: heading})
        displayed.add(heading)
      }
      current.headings.set(ancestor, displayed)
    }
    const copy = node.cloneNode(true)
    host.append(copy)
    return { copy, rollback() {
      copy.remove()
      created[0]?.remove()
      for (const heading of headings) {
        heading.copy.remove()
        current.headings.get(heading.ancestor)?.delete(heading.original)
      }
      for (const [original, clone] of current.containers) if (!clone.isConnected) {
        current.containers.delete(original)
        current.headings.delete(original)
      }
    } }
  }
  function splitText(node, ancestors) {
    const letters = Array.from(node.textContent)
    let offset = 0
    while (offset < letters.length) {
      let low = 1, high = letters.length - offset, best = 0
      const piece = node.cloneNode(false)
      origins.set(piece, origins.get(node) || node)
      // Measure real line wrapping, including text without spaces.
      while (low <= high) {
        const count = Math.floor((low + high) / 2)
        piece.textContent = letters.slice(offset, offset + count).join('')
        const attempt = append(piece, ancestors)
        const fit = fits()
        attempt.rollback()
        if (fit) { best = count; low = count + 1 } else high = count - 1
      }
      if (!best) {
        if (!current.units) throw Error('render_block_too_large')
        newPage()
        continue
      }
      piece.textContent = letters.slice(offset, offset + best).join('')
      append(piece, ancestors)
      current.units++
      offset += best
      if (offset < letters.length) newPage()
    }
  }
  function add(node, ancestors = []) {
    if (node.nodeType === 8 || (node.nodeType === 3 && !node.textContent.trim())) return
    if (node.nodeType === 3) {
      const paragraph = document.createElement('span')
      paragraph.textContent = node.textContent
      origins.set(paragraph, node)
      return add(paragraph, ancestors)
    }
    const attempt = append(node, ancestors)
    if (fits()) { current.units++; return }
    attempt.rollback()
    // Keep a record together on a fresh page when possible. Larger compound
    // containers instead fill the current page with their first complete rows.
    if (current.units && node.matches(RECORD)) {
      const previous = current
      newPage()
      const whole = append(node, ancestors)
      if (fits()) { current.units++; return }
      whole.rollback()
      current.page.remove()
      pages.pop()
      current = previous
    }
    const children = [...node.childNodes].filter(child => child.nodeType !== 8 && (child.nodeType !== 3 || child.textContent.trim()))
    if (!node.children.length && node.textContent) return splitText(node, ancestors)
    if (!children.length || node.namespaceURI !== 'http://www.w3.org/1999/xhtml') {
      if (current.units) { newPage(); return add(node, ancestors) }
      throw Error('render_block_too_large')
    }
    const content = children.filter(child => child.nodeType !== 1 || !child.matches(HEADING))
    // The nearest preceding heading travels with its first row, so a page never
    // ends with the title of a section whose content begins on the next page.
    if (content.length) {
      for (const child of content) add(child, [...ancestors, node])
      const last = children.indexOf(content.at(-1))
      for (const child of children.slice(last + 1)) add(child, [...ancestors, node])
    } else {
      for (const child of children) add(child, [...ancestors, node])
    }
  }
  newPage()
  for (const child of source.childNodes) add(child)
  pages.forEach((page, index) => {
    const footer = page.querySelector('.render-page-footer')
    footer.children[0].textContent = `第 ${index + 1} / ${pages.length} 页`
    footer.children[1].textContent = index + 1 < pages.length ? `下一页：${input.next_command} ${index + 2}` : '已到末页'
    if (measuredHeight(page) > height) throw Error('render_page_too_large')
  })
  return pages
}
