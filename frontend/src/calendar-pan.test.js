import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { Window } from 'happy-dom'
import { createCalendarPan } from './calendar-pan.js'
const window = new Window()
after(() => window.happyDOM.close())
function setup(t) {
  const root=window.document.createElement('div')
  root.innerHTML='<div class="timeline-scroll"><div class="timeline-label">游戏</div><button class="timeline-event">活动</button></div><section><button>未定位活动</button></section>'
  window.document.body.append(root)
  Object.defineProperties(root,{scrollWidth:{value:1000,configurable:true},clientWidth:{value:300,configurable:true}})
  root.scrollLeft=100;root.scrollTop=80
  let captured=null
  root.setPointerCapture=id=>{captured=id}
  root.hasPointerCapture=id=>captured===id
  root.releasePointerCapture=()=>{captured=null}
  const controller=createCalendarPan(root)
  const button=root.querySelector('.timeline-event')
  const pointer=(type,target=button,extra={})=>{
    const event=new window.PointerEvent(type,{bubbles:true,cancelable:true,pointerType:'mouse',pointerId:1,isPrimary:true,button:0,buttons:type==='pointerup'?0:1,clientX:100,clientY:50,...extra})
    target.dispatchEvent(event);return event
  }
  const click=(detail=1)=>{const event=new window.MouseEvent('click',{bubbles:true,cancelable:true,detail});button.dispatchEvent(event);return event}
  t.after(()=>{controller.destroy();root.remove()})
  return {root,button,controller,pointer,click,captured:()=>captured}
}
test('horizontal mouse drag pans in both directions with hard bounds and leaves vertical position untouched',t=>{
  const {root,pointer,captured}=setup(t)
  assert.equal(pointer('pointerdown').defaultPrevented,false)
  assert.equal(captured(),null)
  const move=pointer('pointermove',window,{clientX:40})
  assert.equal(move.defaultPrevented,true)
  assert.equal(root.scrollLeft,160)
  assert.equal(root.scrollTop,80)
  assert.equal(captured(),1)
  assert.ok(root.classList.contains('is-panning'))
  pointer('pointermove',window,{clientX:-5000});assert.equal(root.scrollLeft,700)
  pointer('pointermove',window,{clientX:5000});assert.equal(root.scrollLeft,0)
  pointer('pointerup',window)
  assert.equal(captured(),null)
  assert.ok(!root.classList.contains('is-panning'))
})
test('short clicks open activities, a horizontal drag blocks its generated click, and keyboard clicks remain available',t=>{
  const {button,pointer,click}=setup(t)
  let opened=0;button.addEventListener('click',()=>opened++)
  pointer('pointerdown');pointer('pointermove',window,{clientX:97});pointer('pointerup',window)
  assert.equal(click().defaultPrevented,false);assert.equal(opened,1)
  pointer('pointerdown');pointer('pointermove',window,{clientX:60});pointer('pointerup',window)
  button.parentElement.parentElement.dispatchEvent(new window.Event('lostpointercapture'))
  assert.equal(click().defaultPrevented,true);assert.equal(opened,1)
  pointer('pointerdown');pointer('pointermove',window,{clientX:60});pointer('pointerup',window)
  assert.equal(click(0).defaultPrevented,false);assert.equal(opened,2)
  pointer('pointerdown');pointer('pointerup',window);click();assert.equal(opened,3)
})
test('touch, vertical intent, wheel, nonprimary buttons and non-timeline content stay native',t=>{
  const {root,pointer,captured}=setup(t)
  root.style.touchAction='auto'
  for(const extra of [{pointerType:'touch'},{pointerType:'pen'},{button:2},{isPrimary:false}]) {
    assert.equal(pointer('pointerdown',undefined,extra).defaultPrevented,false)
    assert.equal(pointer('pointermove',window,{...extra,clientX:10}).defaultPrevented,false)
  }
  pointer('pointerdown');assert.equal(pointer('pointermove',window,{clientX:95,clientY:90}).defaultPrevented,false)
  pointer('pointermove',window,{clientX:10,clientY:90})
  pointer('pointerdown',root.querySelector('section button'));pointer('pointermove',window,{clientX:10})
  const wheel=new window.WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:50});root.dispatchEvent(wheel)
  assert.equal(wheel.defaultPrevented,false)
  assert.equal(root.scrollLeft,100);assert.equal(root.scrollTop,80)
  assert.equal(captured(),null);assert.equal(root.style.touchAction,'auto')
})
test('cancel, reset, blur, lost capture and disposal release state without retaining click suppression or handlers',t=>{
  const {root,pointer,controller,captured,click}=setup(t)
  for(const stop of [()=>pointer('pointercancel',window),()=>controller.reset(),()=>window.dispatchEvent(new window.Event('blur')),()=>root.dispatchEvent(new window.Event('lostpointercapture'))]) {
    pointer('pointerdown');pointer('pointermove',window,{clientX:40});stop()
    assert.equal(captured(),null);assert.ok(!root.classList.contains('is-panning'))
    const left=root.scrollLeft;pointer('pointermove',window,{clientX:10});assert.equal(root.scrollLeft,left)
    assert.equal(click().defaultPrevented,false)
  }
  pointer('pointerdown');pointer('pointermove',window,{clientX:40});pointer('pointerup',window)
  controller.destroy();assert.equal(click().defaultPrevented,false)
  const left=root.scrollLeft;pointer('pointerdown');pointer('pointermove',window,{clientX:10});assert.equal(root.scrollLeft,left)
})
test('bot images and nonoverflowing calendars have no mouse interaction',t=>{
  const {root,pointer}=setup(t)
  root.classList.add('image-mode');pointer('pointerdown');pointer('pointermove',window,{clientX:10})
  assert.equal(root.scrollLeft,100)
  root.classList.remove('image-mode');Object.defineProperty(root,'scrollWidth',{value:300})
  pointer('pointerdown');assert.equal(pointer('pointermove',window,{clientX:10}).defaultPrevented,false)
  assert.equal(root.scrollLeft,100)
})

test('the generated-click guard expires even when the pointer produces no click',async t=>{
  const {pointer,click}=setup(t)
  pointer('pointerdown');pointer('pointermove',window,{clientX:60});pointer('pointerup',window)
  await new Promise(resolve=>window.setTimeout(resolve,5))
  assert.equal(click().defaultPrevented,false)
})
