import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue, mount, content, nodes, choose } from '../test-utils/vue.js'
const MenuSelect = await loadVue(new URL('./MenuSelect.vue', import.meta.url))
const key = name => ({ key: name, preventDefault() {} })
const options = [{ value: 'all', label: '全部' }, { value: 3, label: '三号' }, { value: 'x', label: '其他' }]

function setup(t, modelValue = 'all') {
  const changes = []
  const root = mount(t, MenuSelect, { modelValue, options, label: '筛选', 'onUpdate:modelValue': v => changes.push(v) })
  const trigger = nodes(root, 'button')[0]
  return { root, trigger, changes }
}

test('shows the chosen label and marks it selected in the listbox', t => {
  const { root, trigger } = setup(t, 3)
  assert.equal(trigger.props.role, 'combobox')
  assert.equal(trigger.props['aria-label'], '筛选')
  assert.match(content(trigger), /三号/)
  const selected = nodes(root, 'li').filter(li => li.props['aria-selected'] === true)
  assert.deepEqual(selected.map(li => li.props['data-value']), ['3'])
})

test('keyboard opens, moves, picks with Enter and keeps the option value type', async t => {
  const { trigger, changes } = setup(t)
  trigger.props.onKeydown(key('ArrowDown')); await nextTick()
  assert.equal(trigger.props['aria-expanded'], true)
  trigger.props.onKeydown(key('ArrowDown')); await nextTick()
  assert.match(trigger.props['aria-activedescendant'], /-1$/)
  trigger.props.onKeydown(key('Enter')); await nextTick()
  assert.deepEqual(changes, [3])
  assert.equal(trigger.props['aria-expanded'], false)
})

test('Escape closes without choosing and End jumps to the last option', async t => {
  const { trigger, changes } = setup(t)
  trigger.props.onKeydown(key('Enter')); await nextTick()
  trigger.props.onKeydown(key('End')); await nextTick()
  assert.match(trigger.props['aria-activedescendant'], /-2$/)
  trigger.props.onKeydown(key('Escape')); await nextTick()
  assert.equal(trigger.props['aria-expanded'], false)
  assert.deepEqual(changes, [])
})

test('picking the current option again emits nothing', t => {
  const { root, changes } = setup(t, 'x')
  choose(root, '筛选', 'x')
  choose(root, '筛选', 'all')
  assert.deepEqual(changes, ['all'])
})

test('typing a label prefix highlights the first match', async t => {
  const { trigger, changes } = setup(t)
  trigger.props.onKeydown(key('Enter')); await nextTick()
  trigger.props.onKeydown(key('其')); await nextTick()
  assert.match(trigger.props['aria-activedescendant'], /-2$/)
  trigger.props.onKeydown(key('Enter')); await nextTick()
  assert.deepEqual(changes, ['x'])
})

test('an async disabled state closes the list and refuses a stale option click', async t => {
  const changes = [], props = reactive({ modelValue:'all', options, label:'筛选', disabled:false, 'onUpdate:modelValue':v => changes.push(v) })
  const root = mount(t, MenuSelect, props), trigger = nodes(root, 'button')[0]
  trigger.props.onKeydown(key('Enter')); await nextTick()
  assert.equal(trigger.props['aria-expanded'], true)
  props.disabled = true; await nextTick()
  assert.equal(trigger.props['aria-expanded'], false)
  choose(root, '筛选', 'x')
  assert.deepEqual(changes, [])
})

test('replacing options preserves the highlighted value and empty options close the list', async t => {
  const props = reactive({ modelValue:'all', options:[...options], label:'筛选' })
  const root = mount(t, MenuSelect, props), trigger = nodes(root, 'button')[0]
  trigger.props.onKeydown(key('Enter')); await nextTick()
  trigger.props.onKeydown(key('End')); await nextTick()
  props.options = [options[2], options[0]]; await nextTick()
  assert.match(trigger.props['aria-activedescendant'], /-0$/)
  props.options = []; await nextTick()
  assert.equal(trigger.props['aria-expanded'], false)
})

test('option selection cancels label activation and Escape does not close its containing dialog', async t => {
  const { root, trigger, changes } = setup(t)
  let prevented = false, stopped = false
  nodes(root, 'li')[1].props.onClick({ preventDefault() { prevented = true } })
  assert.equal(prevented, true)
  assert.deepEqual(changes, [3])
  trigger.props.onKeydown(key('Enter')); await nextTick()
  trigger.props.onKeydown({ key:'Escape', preventDefault() {}, stopPropagation() { stopped = true } })
  await nextTick()
  assert.equal(stopped, true)
  assert.equal(trigger.props['aria-expanded'], false)
})
