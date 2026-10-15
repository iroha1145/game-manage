import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue, mount, content, nodes } from '../test-utils/vue.js'
const Assessment=await loadVue(new URL('./RoleAssessment.vue',import.meta.url))
const Details=await loadVue(new URL('./NteEquippedDetails.vue',import.meta.url))

test('rich equipped descriptions are escaped and source grouping plus unknowns visible',t=>{
 const root=mount(t,Details,{role:{group_type:'unknown',awaken_effects:['<img src=x onerror=alert(1)>'],suit:{id:'set',core:[{id:'i1',main_properties:[{id:'m'}]}],pie:[]}}})
 assert.match(content(root),/未提供/)
 assert.match(content(nodes(root,'details')[0]),/core.*i1/)
 assert.equal(nodes(root,'img').length,0)
 assert.match(content(root),/装备品质、面积、完整副词条完成标记未得到来源验证/)
})

test('image mode shows shared assessment content without input actions or requests',t=>{
 const root=mount(t,Assessment,{game:'nte',characterId:'c1',imageMode:true,initialAssessment:{status:'scored',value:'0.00',source:'user_configured',model_version:'v1',weight_version:'w1',formula:'nte-custom-weighting-v1',contributions:[{item_id:'i1',contribution_id:'sub:attack',weight:'0',value:'0'}]}})
 assert.match(content(root),/已评分.*0.00/)
 assert.doesNotMatch(content(root),/用户配置|sub:attack|nte-custom-weighting-v1/)
 assert.equal(nodes(root,'button').length,0);assert.equal(nodes(root,'textarea').length,0)
})

test('website configuration UI saves weights/config and compares scoped pairs',async t=>{
 const previous=globalThis.fetch;const calls=[]
 t.after(()=>{globalThis.fetch=previous})
 const cfg={id:'id1',revision:1,data:{name:'saved',items:[]}}
 globalThis.fetch=async(path,options)=>{calls.push({path,options});return {ok:true,status:200,json:async()=>path.endsWith('/compare')?{model_version:'v1',a:{status:'scored',value:'1'},b:{status:'scored',value:'2'},delta:'1',percent_delta:'100.00'}:options.method==='POST'?{id:'id2'}:{model:{version:'unconfigured'},configurations:[cfg,{...cfg,id:'id2'}]}}}
 const props=reactive({game:'wuthering_waves',characterId:'c1',scopeKey:'a'})
 const root=mount(t,Assessment,props)
 const click=async label=>{const button=nodes(root,'button').find(b=>content(b)===label);await button.props.onClick();await nextTick()}
 await click('配置权重与 A/B 对比')
 const select=async(label,value)=>{nodes(root,'select').find(n=>n.props['aria-label']===label).props.onChange({target:{value}});await nextTick()}
 const input=async(label,value)=>{nodes(root,'input').find(n=>n.props['aria-label']===label).props.onInput({target:{value}});await nextTick()}
 await select('新增权重词条','attack_flat');await click('添加权重词条');await input('攻击平值权重','0.1')
 await click('添加装备');await click('添加词条')
 await select('装备1词条1','attack_flat');await input('装备1词条值1','100');await select('装备1词条单位1','flat')
 nodes(root,'input').find(n=>n.props.type==='checkbox').props.onChange({target:{checked:true}});await nextTick()
 for(const text of ['攻击平值','偏好权重','词条值','已核对完整主副词条'])assert.ok(content(root).includes(text))
 await click('保存权重模型');await click('保存配置');await click('同模型重新计算并对比')
 assert.match(content(root),/变化 100.00%/)
 assert.ok(calls.some(c=>c.path.endsWith('/model')&&c.options.method==='PUT'))
 assert.ok(calls.some(c=>c.path.endsWith('/configurations')&&c.options.method==='POST'))
 const body=JSON.parse(calls.find(c=>c.path.endsWith('/configurations')&&c.options.method==='POST').options.body)
 assert.equal(body.items[0].stats_complete,true);assert.equal(body.items[0].stats[0].canonical_id,'attack_flat');assert.equal(body.items[0].stats[0].value,'100')
 props.scopeKey='b';await nextTick();assert.equal(nodes(root,'textarea').length,0);assert.doesNotMatch(content(root),/变化 100.00%/)
})

test('persisted empty NTE model opens as unconfigured structured fields',async t=>{
 const previous=globalThis.fetch;t.after(()=>{globalThis.fetch=previous})
 globalThis.fetch=async()=>({ok:true,status:200,json:async()=>({model:{game:'nte',character_id:'c1',version:'empty-v1',source:'user_configured',nte_profile:null,nte_spec:null},configurations:[]})})
 const root=mount(t,Assessment,{game:'nte',characterId:'c1'})
 await nodes(root,'button').find(b=>content(b)==='配置权重与 A/B 对比').props.onClick();await nextTick()
 assert.match(content(root),/自定义品质因子.*卡带主属性参考值.*添加装备/)
})
