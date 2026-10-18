import test from 'node:test'
import assert from 'node:assert/strict'
import { nextTick, reactive } from 'vue'
import { loadVue, mount, nodes } from '../test-utils/vue.js'
const ArtworkImage=await loadVue(new URL('./ArtworkImage.vue',import.meta.url))
test('artwork tries safe candidates in order and removes broken pictures; new inputs reset the fallback', async t => {
  const exhausted=[]
  const props=reactive({candidates:['javascript:bad','https://example.com/first.jpg','https://example.com/second.jpg'],decorative:true,onExhausted:()=>exhausted.push(true)})
  const root=mount(t,ArtworkImage,props)
  let img=nodes(root,'img')[0]
  assert.equal(img.props.src,'https://example.com/first.jpg')
  assert.equal(img.props.alt,'')
  assert.equal(img.props['aria-hidden'],'true')
  assert.equal(img.props.referrerpolicy,'no-referrer')
  img.props.onError(); await nextTick()
  img=nodes(root,'img')[0]
  assert.equal(img.props.src,'https://example.com/second.jpg')
  img.props.onError(); await nextTick()
  assert.equal(nodes(root,'img').length,0)
  assert.equal(exhausted.length,1)
  props.candidates=['https://example.com/new.jpg'];await nextTick()
  assert.equal(nodes(root,'img')[0].props.src,'https://example.com/new.jpg')
})
test('empty or unsafe artwork has no image request', t => {
  const root=mount(t,ArtworkImage,{candidates:['data:image/png,bad']})
  assert.equal(nodes(root,'img').length,0)
})


test('an unchanged candidate retries only when an explicit snapshot boundary changes', async t => {
  const url='https://i0.hdslb.com/bfs/new_dyn/142523d4e14d0798078580892d98674d1955897084.jpg'
  const props=reactive({candidates:[url],retryKey:{fetched_at:'same-cached-source'}})
  const root=mount(t,ArtworkImage,props)
  nodes(root,'img')[0].props.onError();await nextTick()
  assert.equal(nodes(root,'img').length,0)
  props.candidates=[url];await nextTick()
  assert.equal(nodes(root,'img').length,0,'ordinary parent renders do not retry exhausted URLs')
  props.retryKey={fetched_at:'same-cached-source'};await nextTick()
  assert.equal(nodes(root,'img')[0].props.src,url,'an explicit snapshot reread retries even when its timestamp is unchanged')
  nodes(root,'img')[0].props.onError();await nextTick()
  props.retryKey.fetched_at='mutated-in-place';await nextTick()
  assert.equal(nodes(root,'img').length,0,'the retry boundary watches snapshot replacement, not nested changes')
})
