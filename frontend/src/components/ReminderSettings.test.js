import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick } from 'vue'
import { Window } from 'happy-dom'
import { loadVue, mount, nodes, content, choose } from '../test-utils/vue.js'
import { configureHttpClient } from '../http-client.js'

const ReminderSettings = await loadVue(new URL('./ReminderSettings.vue', import.meta.url))
const GroupSettings = await loadVue(new URL('./QqGroupSettings.vue', import.meta.url))
const flush = async () => { await new Promise(resolve => setTimeout(resolve, 15)); await nextTick() }
const dom = new Window()
globalThis.Document = dom.Document; globalThis.ShadowRoot = dom.ShadowRoot

test('per-role reminder form saves actual configuration and reads inbox without refresh or sends', async t => {
  configureHttpClient({mode:'cloud'}); t.after(() => configureHttpClient({mode:'local'}))
  const calls = []
  t.mock.method(globalThis,'fetch',async (url, options={}) => {
    calls.push([url, options])
    const body = url.endsWith('/csrf') ? {csrf_token:'fixture'} : url.endsWith('/inbox') ? {messages:[{id:1,title:'体力已满',body:'读取时间 fixture'}]} : {rule:{enabled:false,notify_full:false,threshold_percent:null,city_threshold_percent:null,cooldown_seconds:3600,daily_cap:3,quiet_start:null,quiet_end:null,max_source_age_seconds:600,timezone:'Asia/Shanghai'}}
    return new Response(JSON.stringify(body))
  })
  const root = mount(t, ReminderSettings, {account:{account_id:'a',game:'nte',state:'active',roles:[{role_id:'r',display_name:'角色甲',is_default:true},{role_id:'s',display_name:'角色乙'}]}})
  await flush()
  assert.match(content(root), /站内提醒|QQ 主动推送未支持/)
  assert.match(content(root), /都市活力/)
  const checkbox = nodes(root, 'input').find(n=>n.props['aria-label']==='启用本人角色提醒')
  checkbox.props['onUpdate:modelValue'](true)
  await nodes(root,'form')[0].props.onSubmit({preventDefault(){}})
  await flush()
  const saved=calls.find(([url, opt])=>url==='/api/accounts/a/roles/r/reminders' && opt.method==='PUT')
  assert.equal(JSON.parse(saved[1].body).enabled, true)
  assert.match(content(root), /体力已满|读取时间/)
  choose(root,'提醒角色','s'); await flush()
  assert.ok(calls.some(([url])=>url==='/api/accounts/a/roles/s/reminders'))
  assert.ok(calls.every(([url])=> !/refresh|internal|send/.test(url)))
})

test('group form consumes administrator route and labels public subscription delivery unsupported', async t => {
  configureHttpClient({mode:'cloud'}); t.after(() => configureHttpClient({mode:'local'}))
  const calls=[]
  t.mock.method(globalThis,'fetch',async (url,options={})=> {calls.push([url,options]);return new Response(JSON.stringify(url.endsWith('/csrf')?{csrf_token:'fixture'}:{settings:{allowed_games:['nte'],public_topics:[],image_preference:false,requests_per_minute:20,timezone:'Asia/Shanghai',quiet_start:null,quiet_end:null},external_delivery:'unsupported'}))})
  const root = mount(t,GroupSettings)
  assert.match(content(root), /管理员|主动推送未支持|配置/)
  nodes(root,'input').find(n=>n.props['aria-label']==='QQ 群标识').props['onUpdate:modelValue']('group-a')
  await nodes(root,'button').find(n=>content(n)==='读取群设置').props.onClick(); await flush()
  await nodes(root,'form')[0].props.onSubmit({preventDefault(){}}); await flush()
  assert.ok(calls.some(([url,opt])=>url==='/api/admin/qq/groups/group-a/settings' && opt.method==='PUT'))
})

test('group form offers supported controls while saving preserves hidden subscription and quiet-time values', async t => {
  configureHttpClient({ mode: 'cloud' }); t.after(() => configureHttpClient({ mode: 'local' }))
  const calls = []
  t.mock.method(globalThis, 'fetch', async (url, options = {}) => {
    calls.push([url, options])
    return new Response(JSON.stringify(url.endsWith('/csrf') ? { csrf_token: 'fixture' } : { settings: { allowed_games: ['nte'], public_topics: ['events'], image_preference: false, requests_per_minute: 20, timezone: 'Asia/Shanghai', quiet_start: '23:00', quiet_end: '07:00' }, external_delivery: 'unsupported' }))
  })
  const root = mount(t, GroupSettings)
  nodes(root, 'input').find(node => node.props['aria-label'] === 'QQ 群标识').props['onUpdate:modelValue']('group-existing')
  await nodes(root, 'button').find(node => content(node) === '读取群设置').props.onClick(); await flush()
  assert.equal(nodes(root, 'fieldset').some(node => content(node).includes('公共订阅')), false)
  assert.equal(nodes(root, 'input').some(node => node.props.type === 'time'), false)
  assert.doesNotMatch(content(root), /不实现|兼容保留|不生效|群静默/)
  assert.match(content(root), /允许查询的游戏.*使用图片回复查询结果.*群查询每分钟上限/)
  nodes(root, 'input').find(node => node.props.type === 'number').props['onUpdate:modelValue'](25)
  await nodes(root, 'form')[0].props.onSubmit({ preventDefault() {} }); await flush()
  const saved = JSON.parse(calls.find(([url, options]) => url === '/api/admin/qq/groups/group-existing/settings' && options.method === 'PUT')[1].body)
  assert.equal(saved.requests_per_minute, 25)
  assert.deepEqual(saved.public_topics, ['events'])
  assert.equal(saved.quiet_start, '23:00'); assert.equal(saved.quiet_end, '07:00')
  assert.deepEqual(saved.allowed_games, ['nte']); assert.equal(saved.image_preference, false)
})
