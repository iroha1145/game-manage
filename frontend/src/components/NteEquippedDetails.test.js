import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content } from '../test-utils/vue.js'
import { prepareReuse } from '../qq-image/reuse-model.js'

const Equipped = await loadVue(new URL('./NteEquippedDetails.vue', import.meta.url))
const RoleDetail = await loadVue(new URL('./NteRoleDetail.vue', import.meta.url))
const completeRole = () => ({
  id: '1003', name: '早雾',
  skills: [{ name: '战技名称', level: 0, items: [{ title: '战技效果', desc: '完整战技描述末尾' }] }],
  city_skills: [{ name: '城区技能名称', level: null, items: [{ title: '城区效果', desc: '完整城区描述末尾' }] }],
})

test('image mode preserves supplied battle and city skill descriptions', t => {
  const root = mount(t, Equipped, { role: completeRole(), imageMode: true })
  assert.match(content(root), /战技说明.*战技名称.*战技效果：完整战技描述末尾/)
  assert.match(content(root), /城区技能说明.*城区技能名称.*城区效果：完整城区描述末尾/)
  assert.doesNotMatch(content(root), /补充资料与原文/)
})

test('web equipped details retain skill descriptions and source disclosure', t => {
  const root = mount(t, Equipped, { role: completeRole() })
  assert.match(content(root), /战技说明.*完整战技描述末尾.*城区技能说明.*完整城区描述末尾/)
  assert.match(content(root), /补充资料与原文/)
})

test('A projection keeps compact skill names and levels without mutating complete input', t => {
  const role = completeRole()
  const snapshot = { kind: 'nte_role', display_data: { snapshot: { payload: { entries: [role] } } } }
  const prepared = prepareReuse({ snapshot }).display_data.snapshot.payload.entries[0]
  const root = mount(t, RoleDetail, { role: prepared, imageMode: true })
  assert.match(content(root), /战技名称.*Lv0.*城区技能名称.*未提供/)
  assert.doesNotMatch(content(root), /战技说明|城区技能说明|完整战技描述末尾|完整城区描述末尾/)
  assert.equal(role.skills[0].items[0].desc, '完整战技描述末尾')
  assert.equal(role.city_skills[0].items[0].desc, '完整城区描述末尾')
})
