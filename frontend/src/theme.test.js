import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
// Load Vue before installing the minimal document stub; these tests exercise
// reactive theme state and do not mount a browser component.
import 'vue'

const boot = readFileSync(new URL('../public/theme-boot.js', import.meta.url), 'utf8')
let moduleId = 0

function browser(t, { saved = null, light = true, blockedRead = false, blockedWrite = false, mediaSupport = true, legacy = false } = {}) {
  const keys = ['document', 'localStorage', 'matchMedia']
  const previous = keys.map(key => Object.getOwnPropertyDescriptor(globalThis, key))
  t.after(() => keys.forEach((key, index) => {
    if (previous[index]) Object.defineProperty(globalThis, key, previous[index])
    else delete globalThis[key]
  }))
  let stored = saved
  const writes = []
  const listeners = new Set()
  const media = {
    matches: light,
    ...(legacy ? {
      addListener: fn => listeners.add(fn),
      removeListener: fn => listeners.delete(fn),
    } : {
      addEventListener: (event, fn) => { assert.equal(event, 'change'); listeners.add(fn) },
      removeEventListener: (event, fn) => { assert.equal(event, 'change'); listeners.delete(fn) },
    }),
  }
  const env = {
    document: { documentElement: { dataset: {} } },
    localStorage: {
      getItem(key) { assert.equal(key, 'gm-theme'); if (blockedRead) throw new Error('read blocked'); return stored },
      setItem(key, value) { assert.equal(key, 'gm-theme'); writes.push(value); if (blockedWrite) throw new Error('write blocked'); stored = value },
    },
    matchMedia: mediaSupport ? query => { assert.equal(query, '(prefers-color-scheme: light)'); return media } : undefined,
  }
  Object.assign(globalThis, env)
  return {
    env, writes, listeners,
    dataset: env.document.documentElement.dataset,
    stored: () => stored,
    change(light) { media.matches = light; for (const fn of listeners) fn({ matches: light }) },
    load: () => import(`./theme.js?theme-test=${++moduleId}`),
  }
}

test('boot and runtime agree for stored, missing and invalid choices under either browser preference', async t => {
  for (const saved of [null, 'light', 'dark', 'auto', '', 'unknown']) {
    for (const light of [false, true]) {
      await t.test(`${String(saved)} / ${light ? 'light' : 'dark'}`, async t => {
        const b = browser(t, { saved, light })
        vm.runInNewContext(boot, b.env)
        const before = { ...b.dataset }
        const m = await b.load()
        const expectedMode = saved === 'light' || saved === 'dark' ? saved : 'auto'
        assert.equal(m.themeMode.value, expectedMode)
        assert.equal(m.theme.value, expectedMode === 'auto' ? light ? 'light' : 'dark' : expectedMode)
        assert.deepEqual(b.dataset, before)
        assert.deepEqual(b.writes, [], 'initialization must not persist inferred preferences')
      })
    }
  }
})

test('mode cycle, resolver and selection update state, root and storage immediately', async t => {
  const b = browser(t, { saved: 'light', light: false })
  const m = await b.load()
  assert.equal(m.nextThemeMode(), 'dark')
  assert.equal(m.nextThemeMode('dark'), 'auto')
  assert.equal(m.nextThemeMode('auto'), 'light')
  assert.equal(m.resolveThemeMode('auto'), 'dark')
  assert.equal(m.themeMode.value, 'light', 'resolver does not change selection')
  for (const mode of ['dark', 'auto', 'light']) {
    m.setThemeMode(mode)
    assert.equal(m.themeMode.value, mode)
    assert.equal(b.stored(), mode)
    assert.equal(b.dataset.themeMode, mode)
    assert.equal(b.dataset.theme, m.theme.value)
  }
  m.setTheme('dark')
  assert.equal(m.themeMode.value, 'dark', 'old setTheme calls remain supported')
  assert.equal(m.theme.value, 'dark')
})

test('system changes affect auto only, returning to auto reads the current preference, and cleanup removes tracking', async t => {
  const b = browser(t)
  const m = await b.load()
  const stop = m.followSystem()
  assert.equal(b.listeners.size, 1)
  b.change(false)
  assert.equal(m.theme.value, 'dark')
  assert.deepEqual(b.writes, [], 'system changes are never persisted')
  m.setThemeMode('light')
  b.change(false)
  assert.equal(m.theme.value, 'light')
  m.setThemeMode('auto')
  assert.equal(m.theme.value, 'dark')
  b.change(true)
  assert.equal(m.theme.value, 'light')
  assert.deepEqual(b.writes, ['light', 'auto'])
  stop()
  assert.equal(b.listeners.size, 0)
  b.change(false)
  assert.equal(m.theme.value, 'light')
})

test('failed writes cannot let an older stored choice override this session', async t => {
  const b = browser(t, { saved: 'dark', blockedWrite: true, light: true })
  const m = await b.load()
  const stop = m.followSystem()
  m.setThemeMode('auto')
  assert.equal(b.stored(), 'dark')
  b.change(false)
  b.change(true)
  assert.equal(m.theme.value, 'light')
  assert.equal(m.themeMode.value, 'auto')
  m.setThemeMode('dark')
  b.change(true)
  assert.equal(m.theme.value, 'dark')
  stop()
})

test('blocked storage defaults to auto and still preserves a manual session selection', async t => {
  const b = browser(t, { blockedRead: true, blockedWrite: true })
  vm.runInNewContext(boot, b.env)
  assert.equal(b.dataset.themeMode, 'auto')
  const m = await b.load()
  const stop = m.followSystem()
  assert.equal(m.theme.value, 'light')
  m.setThemeMode('light')
  b.change(false)
  assert.equal(m.theme.value, 'light')
  m.setThemeMode('auto')
  assert.equal(m.theme.value, 'dark')
  stop()
})

test('missing or throwing matchMedia uses the same dark fallback in boot and runtime', async t => {
  for (const throwing of [false, true]) {
    await t.test(throwing ? 'throwing' : 'missing', async t => {
      const b = browser(t, { mediaSupport: false })
      if (throwing) b.env.matchMedia = globalThis.matchMedia = () => { throw new Error('unavailable') }
      vm.runInNewContext(boot, b.env)
      const before = { ...b.dataset }
      const m = await b.load()
      assert.equal(m.theme.value, 'dark')
      assert.deepEqual(b.dataset, before)
      assert.doesNotThrow(() => m.followSystem()())
      m.setThemeMode('light')
      assert.equal(m.theme.value, 'light')
      m.setThemeMode('auto')
      assert.equal(m.theme.value, 'dark')
    })
  }
})

test('legacy browser listeners update auto and can be cleaned up', async t => {
  const b = browser(t, { legacy: true })
  const m = await b.load()
  const stop = m.followSystem()
  b.change(false)
  assert.equal(m.theme.value, 'dark')
  stop()
  assert.equal(b.listeners.size, 0)
})
