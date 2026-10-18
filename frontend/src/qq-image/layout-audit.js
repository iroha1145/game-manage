export function auditLayout(source,sheet){
 const walker=document.createTreeWalker(source,NodeFilter.SHOW_TEXT),rects=[],issues=[],fonts={},wraps=[]
 let node
 while(node=walker.nextNode()){
  const text=node.textContent.trim(),parent=node.parentElement
  if(!text||!parent||parent.namespaceURI!=='http://www.w3.org/1999/xhtml'||parent.closest('.sr-only,[hidden],svg'))continue
  const style=getComputedStyle(parent)
  if(style.display==='none'||style.visibility==='hidden')continue
  const range=document.createRange();range.selectNodeContents(node)
  const spans=[...range.getClientRects()].filter(r=>r.width>1&&r.height>1)
  if(!spans.length)continue
  fonts[style.fontSize]=(fonts[style.fontSize]||0)+1
  for(const r of spans)rects.push({x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height,text:text.slice(0,32),parent})
  if(parent.clientWidth>0&&parent.scrollWidth>parent.clientWidth+2&&['hidden','clip'].includes(style.overflowX))issues.push({type:'clipped-text',text:text.slice(0,40),class:parent.className})
  if(spans.length>1&&/^[\d,.%/\s]+$/.test(text)&&!parent.closest('.timeline'))issues.push({type:'broken-number',text,class:parent.className})
  if(spans.length>1&&parent.closest('dt,.role-name,.metric-label,.equip-meta span')&&new Set(spans.map(r=>Math.round(r.y))).size>1)issues.push({type:'unwanted-label-wrap',text,class:parent.className})
  if(spans.length>1&&spans.at(-1).width<parseFloat(style.fontSize)*1.5&&text.length>8)wraps.push({text,class:parent.className})
  const ring=parent.closest('.ring-gauge,.donut-ring,.ring')
  if(ring&&parent.closest('.ring-center,.donut-center')){
   const b=ring.getBoundingClientRect(),circle=ring.querySelector('svg circle'),svg=ring.querySelector('svg')
   let radius=Math.min(b.width,b.height)/2-11
   if(circle&&svg){const scale=svg.getBoundingClientRect().width/svg.viewBox.baseVal.width;radius=(Number(circle.getAttribute('r'))-Number(circle.getAttribute('stroke-width'))/2)*scale}
   const cx=b.x+b.width/2,cy=b.y+b.height/2
   for(const r of spans){const furthest=Math.hypot(Math.max(Math.abs(r.x-cx),Math.abs(r.right-cx)),Math.max(Math.abs(r.y-cy),Math.abs(r.bottom-cy)));if(furthest>radius+1)issues.push({type:'text-crosses-ring',text,class:parent.className})}
  }
  let box=parent
  while(box&&box!==sheet){
   const b=box.getBoundingClientRect(),s=getComputedStyle(box)
   if(b.width>2&&b.height>2&&(s.backgroundColor!=='rgba(0, 0, 0, 0)'||parseFloat(s.borderTopWidth)>0)){
    for(const r of spans)if(r.right>b.right+2||r.x<b.x-2||r.y<b.y-2||r.bottom>b.bottom+2)issues.push({type:'outside-surface',text:text.slice(0,40),class:box.className})
    break
   }
   box=box.parentElement
  }
 }
 rects.sort((a,b)=>a.y-b.y)
 for(let i=0;i<rects.length;i++){
  const a=rects[i]
  for(let j=i+1;j<rects.length&&rects[j].y<a.bottom-3;j++){
   const b=rects[j]
   if(a.parent===b.parent||a.parent.contains(b.parent)||b.parent.contains(a.parent))continue
   const width=Math.min(a.right,b.right)-Math.max(a.x,b.x),height=Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)
   if(width>3&&height>3&&width*height>36)issues.push({type:'text-overlap',first:a.text,second:b.text,classes:[a.parent.className,b.parent.className]})
  }
 }
 const unique=[...new Map(issues.map(x=>[JSON.stringify(x),x])).values()]
 return {fontSizes:fonts,issueCount:unique.length,issues:unique.slice(0,100),awkwardWraps:wraps}
}
