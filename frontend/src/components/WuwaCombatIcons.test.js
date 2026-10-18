import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, nodes, content } from '../test-utils/vue.js'
import { characterIcon } from '../wuwa-icons.js'

const Record = await loadVue(new URL('./WuwaCombatRecord.vue', import.meta.url))
const roles = [
  { role_id: 1304, role_name: '今汐', role_level: 90 },
  { role_id: 'future-character', role_name: '未来共鸣者', role_level: 0, role_icon_url: 'https://untrusted.example/role.png' },
]
const data = {
  tower: { difficulty_list: [{ difficulty: 3, tower_area_list: [{ area_name: '测试区域', floor_list: [{ floor: 1, star: 0, max_star: 3, role_list: roles }] }] }] },
  hologram: { challenge_info: { boss: [{ boss_name: '测试首领', difficulty: 1, pass_time: 0, roles }] } },
  slash: { difficulty_list: [{ difficulty: 1, challenge_list: [{ challenge_name: '测试挑战', score: 0, half_list: [{ half_name: '上半', score: 0, role_list: roles }] }] }] },
}

for (const mode of ['tower', 'hologram', 'slash']) {
  test(`${mode} records add each known character portrait without losing names, zero levels or unknown characters`, t => {
    const root = mount(t, Record, { mode, snap: { payload: { [mode]: { data: data[mode] } } } })
    assert.deepEqual(nodes(root, 'img').map(node => node.props.src), [characterIcon(1304)])
    assert.match(content(root), /今汐.*Lv\.90/)
    assert.match(content(root), /未来共鸣者.*Lv\.0/)
    assert.ok(!nodes(root, 'img').some(node => node.props.src.includes('untrusted.example')))
  })
}

test('a named-only challenge participant uses its exact known portrait and preserves the owner name map', t => {
  const root = mount(t, Record, { mode: 'hologram', roleNames: { 1102: '散华' }, snap: { payload: { hologram: { data: { challenge_info: { boss: [{ boss_name: '测试首领', roles: [{ name: '今汐' }, { role_id: 1102 }] }] } } } } } })
  assert.deepEqual(nodes(root, 'img').map(node => node.props.src), [characterIcon(1304), characterIcon(1102)])
  assert.match(content(root), /今汐.*散华/)
})
