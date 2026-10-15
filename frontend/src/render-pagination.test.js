import test from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { paginateContent } from './render-pagination.js'

test('render page query time converts UTC to Beijing across midnight',t=>{
 const previous=globalThis.document,window=new Window();globalThis.document=window.document
 t.after(()=>{globalThis.document=previous;window.happyDOM.abort()})
 const source=document.createElement('div'),target=document.createElement('div')
 source.append(document.createElement('p'));document.body.append(source,target)
 const pages=paginateContent(source,target,{title:'测试',as_of:'2026-10-14T17:20:00Z',next_command:'异环 角色'})
 assert.equal(pages[0].querySelector('.render-page-header p').textContent,'查询时间：2026-10-15 01:20 · 北京时间 UTC+8')
})

test('calendar retains a single complete long image beyond the pagination height', t => {
 const previous=globalThis.document,window=new Window();globalThis.document=window.document
 t.after(()=>{globalThis.document=previous;window.happyDOM.abort()})
 const source=document.createElement('div'),target=document.createElement('div')
 source.innerHTML='<div class="timeline-canvas"><div class="timeline-header">日期轴</div>'+Array.from({length:70},(_,i)=>`<article data-render-id="${i}">活动 ${i}</article>`).join('')+'</div>'
 document.body.append(source,target)
 Object.defineProperty(window.HTMLElement.prototype,'offsetHeight',{configurable:true,get(){return this.matches('.render-page') ? 100 + this.querySelectorAll('article').length*112 : 0}})
 const pages=paginateContent(source,target,{kind:'calendar',title:'日历',as_of:'2026-10-15T08:00:00+08:00',next_command:'日历'},2300)
 assert.equal(pages.length,1)
 assert.equal(pages[0].querySelectorAll('article').length,70)
 assert.equal(pages[0].offsetHeight,7940)
 assert.equal(pages[0].querySelectorAll('.timeline-header').length,1)
 assert.doesNotMatch(pages[0].textContent,/下一页|来源覆盖|第 1/)
})

for (const kind of ['wuwa_role','nte_role','wuwa_gacha','nte_gacha']) test(`${kind} retains the whole shared component as one long image`, t => {
 const previous=globalThis.document,window=new Window();globalThis.document=window.document
 t.after(()=>{globalThis.document=previous;window.happyDOM.abort()})
 const source=document.createElement('div'),target=document.createElement('div')
 source.innerHTML='<div>'+Array.from({length:70},(_,i)=>`<section data-render-block data-render-id="${i}"><h2>完整字段 ${i}</h2><p>值 ${i}</p></section>`).join('')+'</div>'
 document.body.append(source,target)
 Object.defineProperty(window.HTMLElement.prototype,'offsetHeight',{configurable:true,get(){return this.matches('.render-page') ? 100 + this.querySelectorAll('[data-render-id]').length*112 : 0}})
 const pages=paginateContent(source,target,{kind,title:'完整图',as_of:'2026-10-15T08:00:00+08:00',next_command:'角色'},2300)
 assert.equal(pages.length,1)
 assert.equal(pages[0].querySelectorAll('[data-render-id]').length,70)
 assert.equal(pages[0].offsetHeight,7940)
 assert.match(pages[0].textContent,/完整字段 0.*完整字段 69/)
 assert.doesNotMatch(pages[0].textContent,/下一页|第 1/)
})

test('calendar pagination repeats its daily axis while retaining complete game groups and event blocks', t => {
 const previous=globalThis.document,window=new Window();globalThis.document=window.document
 t.after(()=>{globalThis.document=previous;window.happyDOM.abort()})
 const source=document.createElement('div'),target=document.createElement('div')
 source.innerHTML='<div class="timeline-canvas"><div class="timeline-header">10/15 · 四</div><div class="timeline-group"><article data-render-id="a">异环活动一</article></div><div class="timeline-group"><article data-render-id="b">异环活动二</article></div></div>'
 document.body.append(source,target)
 Object.defineProperty(window.HTMLElement.prototype,'offsetHeight',{configurable:true,get(){return this.matches('.render-page') ? 100 + this.querySelectorAll('.timeline-group').length*100 : 0}})
 const pages=paginateContent(source,target,{title:'日历',as_of:'2026-10-15T08:00:00+08:00',next_command:'日历'},250)
 assert.equal(pages.length,2)
 assert.ok(pages.every(page=>page.querySelector('.timeline-header')?.textContent==='10/15 · 四'))
 assert.deepEqual(pages.flatMap(page=>[...page.querySelectorAll('[data-render-id]')].map(row=>row.dataset.renderId)),['a','b'])
})

test('calendar fills the first page with event groups instead of moving a compound window after summary', t => {
 const previous=globalThis.document,window=new Window();globalThis.document=window.document
 t.after(()=>{globalThis.document=previous;window.happyDOM.abort()})
 const source=document.createElement('div'),target=document.createElement('div')
 source.innerHTML='<div><p class="summary" data-render-block>版本摘要</p><section><div class="timeline-canvas"><div class="timeline-header">日期轴</div><div class="timeline-group" data-render-block>活动一</div><div class="timeline-group" data-render-block>活动二</div></div></section></div>'
 document.body.append(source,target)
 Object.defineProperty(window.HTMLElement.prototype,'offsetHeight',{configurable:true,get(){return this.matches('.render-page') ? 100 + this.querySelectorAll('.timeline-group').length*100 + this.querySelectorAll('.summary').length*50 : 0}})
 const pages=paginateContent(source,target,{title:'日历',as_of:'2026-10-15T08:00:00+08:00',next_command:'日历'},300)
 assert.equal(pages.length,2)
 assert.ok(pages[0].querySelector('.timeline-group'),'first page includes actual activities')
 assert.equal(pages[0].querySelector('.timeline-header')?.textContent,'日期轴')
})
