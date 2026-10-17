import { defineAsyncComponent, h } from 'vue'

// A failed download does not prove that a deployment changed the page.
const failedPage = {
  inheritAttrs: false,
  render: () => h('div', { class: 'empty-page', role: 'alert' }, [h('p', '页面模块加载失败，请刷新页面后重试。'),
    h('button', { class: 'ui-button', onClick: () => window.location.reload() }, '刷新页面')]),
}
const loadingPage = {
  inheritAttrs: false,
  render: () => h('p', { class: 'empty-page', role: 'status' }, '正在加载页面…'),
}

export const lazyPage = loader => defineAsyncComponent({
  loader, loadingComponent: loadingPage, delay: 200, timeout: 15000,
  errorComponent: failedPage,
})
