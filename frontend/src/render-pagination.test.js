import test from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { CHAT_PAGE_HEIGHT, paginateContent } from './render-pagination.js'
import { chatFontSize, prepareChatLayout } from './render-layout.js'
function fixture(t, html, measure = () => 0) {
 const window = new Window(), document = window.document
 t.after(() => window.happyDOM.abort())
 const source = document.createElement('div'), target = document.createElement('div')
 source.innerHTML = html; document.body.append(source, target)
 Object.defineProperty(window.HTMLElement.prototype, 'offsetHeight', {configurable:true,get(){return this.matches('.render-page') ? measure(this) : 0}})
 return {source,target,window}
}
const input = {title:'活动日历',as_of:'2026-10-14T17:20:00Z',next_command:'异环 日历'}
test('chat header uses Beijing time and footer contains a valid continuation command', t => {
 const {source,target} = fixture(t,'<p>内容</p>')
 const pages = paginateContent(source,target,input)
 assert.equal(CHAT_PAGE_HEIGHT,1440)
 assert.equal(pages[0].querySelector('.render-page-header p').textContent,'2026-10-15 01:20 · 北京时间')
 assert.equal(pages[0].querySelector('.render-page-footer').textContent,'第 1 / 1 页已到末页')
})
for (const kind of ['calendar','wuwa_role','nte_role','wuwa_gacha','nte_gacha','game_snapshot','notice']) test(`${kind} paginates complete records and retains every first and last value`, t => {
 const {source,target} = fixture(t,'<section><h2>游戏分组</h2>'+Array.from({length:70},(_,i)=>`<article data-render-block data-render-id="${i}"><h3>记录 ${i}</h3><p>完整字段 ${i}</p></article>`).join('')+'</section>',page=>140+page.querySelectorAll('article').length*112)
 const pages = paginateContent(source,target,{...input,kind})
 assert.ok(pages.length > 1)
 assert.ok(pages.every(page=>page.offsetHeight<=1440))
 assert.deepEqual(pages.flatMap(page=>[...page.querySelectorAll('article')].map(row=>row.dataset.renderId)),Array.from({length:70},(_,i)=>String(i)))
 assert.ok(pages.every(page=>page.querySelector('h2')?.textContent==='游戏分组'))
 assert.match(pages[0].textContent,/下一页：异环 日历 2/)
 assert.match(pages.at(-1).textContent,/完整字段 69/)
})
test('large compound cards split by complete table rows and repeat their heading and table header', t => {
 const {source,target} = fixture(t,'<section data-render-block data-render-id="panel"><h2>抽卡记录</h2><table><thead><tr><th>名称</th></tr></thead><tbody>'+Array.from({length:8},(_,i)=>`<tr data-render-id="${i}"><td>物品${i}</td><td>${i}</td></tr>`).join('')+'</tbody></table></section>',page=>100+page.querySelectorAll('tbody > tr').length*100)
 const pages=paginateContent(source,target,input,450)
 assert.equal(pages.length,3)
 assert.ok(pages.every(page=>page.querySelector('thead')?.textContent==='名称'))
 assert.ok(pages.every(page=>page.querySelector('h2')?.textContent==='抽卡记录'))
 assert.equal(pages.flatMap(page=>[...page.querySelectorAll('tbody > tr')]).length,8)
})
test('oversized Chinese description is continued without truncating or duplicating characters',t=>{
 const text='天地玄黄宇宙洪荒'.repeat(100)+'完整末尾'
 const {source,target}=fixture(t,`<section data-render-block><h3>技能说明</h3><p class="description">${text}</p></section>`,page=>100+[...page.querySelectorAll('.description')].reduce((sum,p)=>sum+Math.ceil(p.textContent.length/20)*30,0))
 const pages=paginateContent(source,target,input,400)
 assert.ok(pages.length>1)
 assert.equal(pages.flatMap(page=>[...page.querySelectorAll('.description')].map(p=>p.textContent)).join(''),text)
 assert.ok(pages.every(page=>page.offsetHeight<=400 && page.querySelector('h3')?.textContent==='技能说明'))
})
test('mixed inline text survives recursive splitting and pages never exceed the hard limit',t=>{
 const {source,target}=fixture(t,'<section>前置文字<article data-render-block>A</article><article data-render-block>B</article>后置文字</section>',page=>100+page.querySelectorAll('article').length*180)
 const pages=paginateContent(source,target,input,300)
 assert.match(pages.map(page=>page.querySelector('.render-page-body').textContent).join(''),/前置文字AB后置文字/)
 const huge=fixture(t,'<div>'+Array.from({length:101},()=>'<article data-render-block>内容</article>').join('')+'</div>',page=>100+page.querySelectorAll('article').length*180)
 assert.throws(()=>paginateContent(huge.source,huge.target,input,300),/render_page_limit/)
})
test('chat typography raises small text without double scaling nested runs or changing content', t => {
 const {source}=fixture(t,'<p style="font-size:13px">正文 <b>数值</b><small style="font-size:11px">来源</small></p><div class="qq-calendar"><h3 style="font-size:28px">专用日历</h3></div>')
 const before=source.textContent
 prepareChatLayout(source)
 assert.equal(source.querySelector('p').style.fontSize,'26px')
 assert.equal(source.querySelector('b').style.fontSize,'26px')
 assert.equal(source.querySelector('small').style.fontSize,'22px')
 assert.equal(source.querySelector('h3').style.fontSize,'28px')
 assert.equal(source.textContent,before)
 assert.deepEqual([10,13,17,24,32].map(chatFontSize),[22,26,30,34,42])
})

test('section headings stay with their own first record and never move later headings before earlier values', t => {
 const {source,target}=fixture(t,'<section><h2>抽卡进度</h2><article data-render-block>垫抽 24</article><h3>第三方五星汇总</h3><article data-render-block>汇总 120</article><h3>说明尾注</h3></section>',page=>100+page.querySelectorAll('article').length*180)
 const pages=paginateContent(source,target,input,300)
 assert.equal(pages.length,2)
 assert.doesNotMatch(pages[0].textContent,/第三方|尾注/)
 assert.match(pages[0].textContent,/抽卡进度.*垫抽 24/)
 assert.match(pages[1].textContent,/抽卡进度.*第三方五星汇总.*汇总 120.*说明尾注/)
})
