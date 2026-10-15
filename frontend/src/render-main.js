import { createApp, nextTick } from 'vue'
import './style.css'
import './wuwa.css'
import './render.css'
import RenderRoot from './components/RenderRoot.vue'
import { paginateContent } from './render-pagination.js'

let mounted = false
window.__RENDER_STATE__ = { state: 'idle' }
window.mountRender = async input => {
  if (mounted) throw Error('render_already_mounted')
  mounted = true
  const state = { schema_version: 1, job_id: input.job_id, input_fingerprint: input.input_fingerprint }
  try {
    document.documentElement.dataset.theme = 'light'
    const font = new FontFace('GameRenderNoto', 'url(/render-font.ttf)')
    await font.load()
    document.fonts.add(font)
    // Same design token controls both website and image mode.
    document.documentElement.style.setProperty('--font-sans', 'GameRenderNoto, sans-serif')
    createApp(RenderRoot, { snapshot: input }).mount('#app')
    await nextTick()
    if (input.kind !== 'calendar') document.querySelectorAll('details:not([data-render-collapsed])').forEach(node => { node.open = true })
    const missing = []
    await Promise.all([...document.images].map(async img => {
      img.loading = 'eager'
      try { await img.decode() } catch {
        missing.push(img.alt || '图标')
        img.dispatchEvent(new Event('error'))
        if (img.isConnected) {
          const placeholder = document.createElement('span')
          placeholder.className = 'render-missing-image'
          placeholder.textContent = img.alt || '图标不可用'
          img.replaceWith(placeholder)
        }
      }
    }))
    await nextTick()
    await document.fonts.ready
    const source = document.querySelector('#render-content')
    const blocks=[...source.querySelectorAll('[data-render-block],tbody > tr,.pull-row,.role-card,.wuwa-detail-section')]
    blocks.forEach((block,index) => { block.dataset.renderId=String(index) })
    const pages = paginateContent(source, document.querySelector('#render-pages'), input)
    const displayed=new Set(pages.flatMap(page => [...page.querySelectorAll('[data-render-id]')].map(block => block.dataset.renderId)))
    if (displayed.size !== blocks.length) throw Error('render_missing_content_blocks')
    const frame = () => new Promise(resolve => requestAnimationFrame(resolve))
    await frame()
    const bounds = pages.map(page => page.getBoundingClientRect().height)
    await frame()
    if (pages.some((page, i) => Math.abs(page.getBoundingClientRect().height - bounds[i]) > 1)) throw Error('render_unstable_layout')
    source.remove()
    window.__RENDER_STATE__ = { ...state, state: 'ready', pages: pages.map((p, i) => ({ page: i + 1, width: p.offsetWidth, height: p.offsetHeight })), content_blocks:blocks.length, displayed_blocks:displayed.size, missing_assets: missing }
  } catch {
    window.__RENDER_STATE__ = { ...state, state: 'failed', error: 'render_readiness_failed' }
  }
}
