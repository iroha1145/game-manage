import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
const Component = await loadVue(new URL('./EsportsTeams.vue', import.meta.url))
test('a team with missing roster has an explicit missing state', t => {
  const root = mount(t, Component, { filters: { teamId: 'a' }, payload: { teams: [{ id: 'a', name: 'EDG' }] } })
  assert.match(content(root), /EDG/); assert.match(content(root), /阵容资料暂缺/); assert.match(content(root), /当前阵容/)
})
test('team profile shares compact score rows and preserves a zero score', t => {
  const root = mount(t, Component, { filters: { teamId: 'a' }, payload: {
    teams: [{ id: 'a', name: 'EDG' }], matches: [{ id: 'm', team_a_id: 'a', team_b_id: 'b', team_a_name: 'EDG', team_b_name: 'TBD', status: 'completed', score_a: 0, score_b: 3 }],
  } })
  assert.match(content(root), /0 : 3/)
  assert.ok(nodes(root, 'button').some(n => n.props['data-open-match'] === 'm'))
})

test('a team page lists its recent confirmed results as labelled letters and its roster as a rail of lettered portraits', t => {
  const root = mount(t, Component, { filters: { teamId: 'a' }, payload: {
    teams: [{ id: 'a', name: 'EDG', short_name: 'EDG' }, { id: 'b', name: 'TBD' }], players: [{ id: 'p', nickname: 'Knight' }],
    roster_memberships: [{ team_id: 'a', player_id: 'p', scope: 'source_current', position: '中单' }],
    matches: [
      { id: 'm1', team_a_id: 'a', team_b_id: 'b', team_a_name: 'EDG', team_b_name: 'TBD', status: 'completed', winner_team_id: 'a', start_at: '2026-10-01T10:00:00Z' },
      { id: 'm2', team_a_id: 'b', team_b_id: 'a', team_a_name: 'TBD', team_b_name: 'EDG', status: 'completed', winner_team_id: 'b', start_at: '2026-10-02T10:00:00Z' },
    ],
  } })
  const form = nodes(root, 'ul').find(n => String(n.props.class) === 'es-form')
  assert.deepEqual(nodes(form, 'li').map(content), ['胜', '负'])
  const tiles = nodes(root, 'span').filter(n => String(n.props.class ?? '').includes('es-logo'))
  // The profile tile, then the roster portrait; the related match rows draw their own tiles after them.
  assert.deepEqual(tiles.slice(0, 2).map(n => n.props['data-letter']), ['EDG', 'KN'])
})
