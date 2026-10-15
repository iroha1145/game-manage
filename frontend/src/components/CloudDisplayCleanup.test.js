import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
import { nextTick } from 'vue'
const Overview = await loadVue(new URL('./OverviewPage.vue', import.meta.url))
const Module = await loadVue(new URL('./NteModuleCard.vue', import.meta.url))
const Assessment = await loadVue(new URL('./RoleAssessment.vue', import.meta.url))
const visible = n => n.type === 'details' && !n.props.open ? '' : [n.text, ...n.children.map(visible)].filter(Boolean).join(' ')

test('overview keeps useful values and update times without source diagnostics or raw errors', t => {
  const root = mount(t, Overview, { games: [{game_id:'nte',display_name:'异环',capabilities:['stamina'],credentials_configured:true}],
    snapshots:{nte:{stamina:{payload:{schema_version:1,current:100,maximum:100},fetched_at:'2026-10-15T01:00:00Z'}}},
    readErrors:{nte:'private_exception_code'}, collection:[{game_id:'nte',capability:'stamina',state:'invalid_data',error:'private_exception_code'}],now:Date.parse('2026-10-15T12:00:00+08:00') })
  assert.match(content(root), /体力已满/)
  assert.match(content(root), /更新于/)
  assert.doesNotMatch(content(root), /private_exception_code|快照|同步延迟|来源数据/)
})

test('NTE module failure is a useful retry message without exposing raw collector errors', t => {
  const root = mount(t, Module, {capability:'stamina',snap:{error:'source_error_412',payload:{schema_version:1,current:null,maximum:100},fetched_at:'2026-10-15T01:00:00Z'}})
  assert.match(content(root), /稍后.*重试/)
  assert.doesNotMatch(content(root), /source_error_412|来源：|不准确|同步延迟/)
})

test('assessment keeps the score visible and folds model details; images omit technical evidence', async t => {
  const initialAssessment={status:'scored',value:'0.00',model_version:'technical-model',weight_version:'technical-weights',source:'equipped_snapshot',formula:'technical-formula',contributions:[]}
  const web=mount(t,Assessment,{game:'nte',characterId:'c1',initialAssessment})
  const previous=globalThis.fetch;t.after(()=>{globalThis.fetch=previous})
  globalThis.fetch=async path=>({ok:true,status:200,json:async()=>path.endsWith('/score')?initialAssessment:{model:null,configurations:[]}})
  await nodes(web,'button').find(node=>content(node)==='配置权重与 A/B 对比').props.onClick();await nextTick()
  await nodes(web,'button').find(node=>content(node)==='评价当前输入').props.onClick();await nextTick()
  assert.match(visible(web), /已评分.*0.00/)
  assert.doesNotMatch(visible(web), /technical-model|technical-formula|equipped_snapshot/)
  assert.ok(nodes(web,'details').some(node => content(node).includes('technical-model')))
  const image=mount(t,Assessment,{game:'nte',characterId:'c1',initialAssessment,imageMode:true})
  assert.match(content(image), /已评分.*0.00/)
  assert.doesNotMatch(content(image), /technical-model|technical-formula|equipped_snapshot/)
})
