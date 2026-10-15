import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import catalog from '../endfield-icon-catalog.js'

const Artwork = await loadVue(new URL('./EndfieldArtwork.vue', import.meta.url))
const [operatorId, role] = Object.entries(catalog.roles).find(([, item]) => item.portrait)

test('failed portrait falls back to supplied avatar and only then to an initial', async t => {
  const root = mount(t, Artwork, { role: true, portrait: true, operatorId, name: role.name, src: 'https://bbs.hycdn.cn/synthetic-avatar.png' })
  assert.equal(nodes(root, 'img')[0].props.src, role.portrait)
  nodes(root, 'img')[0].props.onError()
  await nextTick()
  assert.equal(nodes(root, 'img')[0].props.src, 'https://bbs.hycdn.cn/synthetic-avatar.png')
  nodes(root, 'img')[0].props.onError()
  await nextTick()
  assert.equal(nodes(root, 'img').length, 0)
  assert.equal(content(root), role.name.slice(0, 1))
})

test('portrait fallback can use the reviewed catalog avatar and resets for a new role', async t => {
  const props = reactive({ role: true, portrait: true, operatorId, name: role.name })
  const root = mount(t, Artwork, props)
  nodes(root, 'img')[0].props.onError()
  await nextTick()
  assert.equal(nodes(root, 'img')[0].props.src, role.icon)
  const [otherId, other] = Object.entries(catalog.roles).find(([id, item]) => id !== operatorId && item.portrait)
  props.operatorId = otherId; props.name = other.name
  await nextTick()
  assert.equal(nodes(root, 'img')[0].props.src, other.portrait)
})
