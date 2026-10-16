import { defineAsyncComponent, h } from 'vue'

// An update replaces the built chunks, so a tab opened earlier can ask for one
// that no longer exists; only a reload picks up the new build.
const staleBuild = {
  inheritAttrs: false,
  render: () => h('div', { class: 'empty-page' }, [h('p', '界面已更新，请刷新页面后重试。'),
    h('button', { class: 'ui-button', onClick: () => window.location.reload() }, '刷新页面')]),
}

export const lazyPage = loader => defineAsyncComponent({ loader, errorComponent: staleBuild })
