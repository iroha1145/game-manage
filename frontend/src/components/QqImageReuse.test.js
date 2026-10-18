import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
import { challengeReport } from '../endfield-challenges.js'

const Reuse = await loadVue(new URL('../qq-image/ReuseBody.vue', import.meta.url))
const input = (game, provider, payload) => ({ command: '合成挑战回归', snapshot: {
  kind: 'game_snapshot', game, as_of: '2026-10-15T04:00:00Z',
  display_data: { panels: [{ game, provider, capability: 'combat', snapshot: {
    payload, fetched_at: '2026-10-15T04:00:00Z', state: 'ok', stale: false,
  } }], notices: [] },
} })

test('A reuses Endfield challenges with each category observation instead of WuWa modes', t => {
  const reports = [
    ['war', '2026-10-14T01:30:00Z'], ['monument', '2026-10-14T02:30:00Z'], ['crisis', '2026-10-14T03:30:00Z'],
  ].map(([kind, fetched_at]) => challengeReport({ kind, fetched_at, records: [],
    stale: kind === 'monument', summary: { highest: 0, challenge_count: 0 },
  }, kind))
  const root = mount(t, Reuse, { input: input('endfield', 'skland', { reports }) })
  for (const expected of ['战争观测时间 2026-10-14 09:30', '丰碑观测时间 2026-10-14 10:30', '危机观测时间 2026-10-14 11:30', '已有资料待更新']) {
    assert.ok(content(root).includes(expected), expected)
  }
  assert.doesNotMatch(content(root), /逆境深塔|战术全息|冥歌海墟/)
  assert.equal(nodes(root, 'button').length, 0)
})

test('A retains all three WuWa combat modes and supplied boss data', t => {
  const payload = {
    tower: { state: 'ok', data: { difficulty_list: [] } },
    hologram: { state: 'ok', data: { challenge_info: { fixture: [
      { boss_name: '回归首领', difficulty: 1, boss_level: 10, pass_time: 20, roles: [] },
    ] } } },
    slash: { state: 'ok', data: { difficulty_list: [] } },
  }
  const root = mount(t, Reuse, { input: input('wuthering_waves', 'kuro', payload) })
  for (const expected of ['逆境深塔', '战术全息', '冥歌海墟', '回归首领', '20']) assert.ok(content(root).includes(expected), expected)
  assert.doesNotMatch(content(root), /战争观测时间|丰碑观测时间|危机观测时间/)
  assert.equal(nodes(root, 'button').length, 0)
})
