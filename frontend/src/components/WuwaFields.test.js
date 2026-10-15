import test from 'node:test'
import assert from 'node:assert/strict'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
const Fields = await loadVue(new URL('./WuwaFields.vue', import.meta.url))
const fixture = {role_name:'合成角色',level:0,role_id:'synthetic-character',role_attribute_list:[
  {attribute_name:'攻击',attribute_value:'1234'},{attribute_name:'防御',attribute_value:null}]}

test('website raw source fields remain in a marked collapsed diagnostic section', t => {
  const root=mount(t,Fields,{data:fixture})
  const raw=nodes(root,'details').find(node=>content(node).includes('role_id'))
  assert.ok(raw)
  assert.ok(!raw.props.open)
  assert.notEqual(raw.props['data-render-collapsed'],undefined)
})

test('image fields omit raw metadata and keep labelled real attributes, zero and unknown', t => {
  const root=mount(t,Fields,{data:fixture,imageMode:true})
  assert.match(content(root),/等级 0/)
  assert.match(content(root),/攻击.*1234.*防御.*未知/)
  assert.doesNotMatch(content(root),/来源补充字段|role_id|role_attribute_list|attribute_name|synthetic-character/)
})
