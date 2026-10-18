import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { createCalendarDefaultPosition } from './calendar-position.js'

const window = new Window()
after(() => window.happyDOM.close())
function fixture(t, { width=1304, label=184, total=3024, dayOffset=1144, enabled=()=>true } = {}) {
  const root=window.document.createElement('div')
  root.innerHTML='<div class="header-label"></div><div class="date-cell is-today"></div>'
  window.document.body.append(root)
  let resize, disconnected=false
  window.ResizeObserver=class {
    constructor(callback) { resize=callback }
    observe() {}
    disconnect() { disconnected=true }
  }
  Object.defineProperties(root,{clientWidth:{get:()=>width},scrollWidth:{get:()=>total}})
  root.scrollLeft=100;root.scrollTop=80
  root.getBoundingClientRect=()=>({left:50,width})
  root.querySelector('.header-label').getBoundingClientRect=()=>({left:50,width:label})
  root.querySelector('.date-cell').getBoundingClientRect=()=>({left:50+dayOffset-root.scrollLeft,width:40})
  const controller=createCalendarDefaultPosition(root,enabled)
  t.after(()=>{controller.destroy();root.remove()})
  return {root,controller,resize:()=>resize(),setWidth:value=>{width=value},setDay:value=>{dayOffset=value},disconnected:()=>disconnected,
    fraction:()=>((dayOffset-root.scrollLeft+20)-label)/(width-label)}
}

test('opening desktop and phone calendars puts today one third into the visible date area', t => {
  for (const width of [1304,390,277]) {
    const view=fixture(t,{width,label:width<760?124:184})
    assert.ok(Math.abs(view.fraction()-1/3)<1e-9)
    assert.equal(view.root.scrollTop,0)
  }
})

test('late layout and menu width changes settle the default position', t => {
  const view=fixture(t,{width:0})
  assert.equal(view.root.scrollLeft,0)
  for (const width of [1440,1304]) {
    view.setWidth(width);view.resize()
    assert.ok(Math.abs(view.fraction()-1/3)<1e-9)
  }
})

test('pointer, wheel and keyboard interaction stop automatic repositioning until a new range is opened', t => {
  for (const event of ['pointerdown','wheel','keydown']) {
    const view=fixture(t)
    view.root.dispatchEvent(new window.Event(event))
    view.root.scrollLeft=321;view.root.scrollTop=90
    view.setWidth(900);view.resize()
    assert.deepEqual([view.root.scrollLeft,view.root.scrollTop],[321,90])
    view.controller.reset()
    assert.ok(Math.abs(view.fraction()-1/3)<1e-9)
    assert.equal(view.root.scrollTop,0)
  }
})

test('range edges clamp to the available dates and a range without today starts at its origin', t => {
  const view=fixture(t,{dayOffset:184})
  assert.equal(view.root.scrollLeft,0)
  view.setDay(2984);view.controller.reset()
  assert.equal(view.root.scrollLeft,3024-1304)
  view.root.querySelector('.date-cell').classList.remove('is-today')
  view.controller.reset();assert.equal(view.root.scrollLeft,0)
  const fitting=fixture(t,{width:1304,total:1304})
  assert.equal(fitting.root.scrollLeft,0)
})

test('image mode and disposed controllers do not alter scrolling', t => {
  const view=fixture(t,{enabled:()=>false})
  view.resize();view.controller.reset()
  assert.deepEqual([view.root.scrollLeft,view.root.scrollTop],[100,80])
  view.controller.destroy();assert.equal(view.disconnected(),true)
  view.root.scrollLeft=55;view.resize();view.controller.reset()
  assert.equal(view.root.scrollLeft,55)
})
