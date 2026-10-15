// Copy the actual component DOM with its scoped Vue attributes. Content is never
// re-translated into a QQ template. Shared views retain their whole DOM;
// legacy callers split only at complete DOM/record boundaries.
import { formatBeijingDateTime } from './calendar.js'
export function paginateContent(source, target, input, height = 2300) {
  const pages = []
  let containers = new Map()
  function newPage() {
    containers = new Map()
    const page = document.createElement('section')
    page.className = 'render-page'
    const header = document.createElement('header')
    header.className = 'render-page-header'
    const title = document.createElement('h1')
    title.textContent = input.title
    const time = document.createElement('p')
    time.textContent = `查询时间：${formatBeijingDateTime(input.as_of)} · 北京时间 UTC+8`
    header.append(title, time)
    page.append(header)
    target.append(page)
    pages.push(page)
    return page
  }
  let page = newPage()
  // Shared views are complete website components. Keep their real DOM height;
  // the browser renderer validates the whole image against QQ output limits.
  if (['calendar','wuwa_role','nte_role','wuwa_gacha','nte_gacha','game_snapshot','notice'].includes(input.kind)) {
    for (const child of source.children) page.append(child.cloneNode(true))
    return pages
  }
  function add(node, ancestors = []) {
    let host = page
    const clones = []
    for (const ancestor of ancestors) {
      if (containers.has(ancestor)) { host=containers.get(ancestor); continue }
      const clone = ancestor.cloneNode(false)
      for (const heading of [...ancestor.children].filter(child => child.matches('h2,h3,header,.version-coverage,.version-bounds,.timeline-header'))) {
        if (heading !== node && !heading.contains(node)) clone.append(heading.cloneNode(true))
      }
      host.append(clone); clones.push(clone); host = clone
      containers.set(ancestor, clone)
    }
    const copy = node.cloneNode(true)
    host.append(copy)
    if (page.offsetHeight <= height) return
    copy.remove()
    clones[0]?.remove()
    for (const [original, clone] of containers) if (!clone.isConnected) containers.delete(original)
    const children = [...node.children]
    // A calendar window is a container of complete groups, not one indivisible
    // record. Fill the current page before carrying the next group to a new one.
    if (!node.matches('[data-render-block]') && children.length && node.querySelectorAll('[data-render-block]').length > 1) {
      for (const child of children) {
        if (child.matches('h2,h3,header,.version-coverage,.version-bounds,.timeline-header')) continue
        add(child, [...ancestors, node])
      }
      return
    }
    // A block fits on a new page: keep its fields together.
    if (page.childElementCount > 1) {
      page = newPage()
      return add(node, ancestors)
    }
    if (!children.length) throw Error('render_block_too_large')
    // Tables split by tbody/tr boundary and retain the header on each chunk.
    const nextAncestors = [...ancestors, node]
    for (const child of children) {
      // Repeated section context belongs to each content block, not another page.
      if (children.length > 1 && child.matches('h2,h3,header,.version-coverage,.version-bounds,.timeline-header')) continue
      add(child, nextAncestors)
    }
  }
  for (const child of source.children) add(child)
  if (pages.length > 100) throw Error('render_page_limit')
  pages.forEach((p, i) => {
    const footer = document.createElement('footer')
    footer.className = 'render-page-footer'
    footer.textContent = `第 ${i + 1} / ${pages.length} 页 · ${i + 1 < pages.length ? `下一页：${input.next_command} ${i + 2}` : '已到末页'} · 来源覆盖以页面说明为准`
    p.append(footer)
  })
  return pages
}
