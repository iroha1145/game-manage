import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue,mount,content,nodes } from '../test-utils/vue.js'
const Profile=await loadVue(new URL('./CloudSklandProfile.vue',import.meta.url))
test('skland summary shows named profile sections, real zero and optional source diagnostics',t=>{
  const root=mount(t,Profile,{payload:{base:{name:'管理员甲',level:0},stamina:{current:0,maximum:100},progress:[],operators:[{id:'source-1',name:'干员甲',level:1}],regions:[{name:'四号谷地',level:0}],ship:[],achievements:{count:null}}})
  assert.match(content(root),/管理员甲/);assert.match(content(root),/干员甲/);assert.match(content(root),/区域探索/);assert.match(content(root),/帝江号/);assert.match(content(root),/未提供/)
  assert.ok(nodes(root,'details').find(n=>content(n).includes('查看来源字段')))
})
