export const schemes = [
 {id:'dossier',name:'A 看板复用',description:'直接复用现有云端 Vue 模组；仅适配图片排版、内容筛选与名称。可共用快照、素材及成图缓存。',palette:['#f7f6f3','#ffffff','#26282e','#4263b6'],label:'看板'},
]
export function imageWidth(c){
 if(c.snapshot.display_data.panels?.some(p=>p.capability==='teams'))return 1080
 if(c.snapshot.kind==='calendar'||c.snapshot.kind.includes('role')||c.snapshot.kind==='guide'||c.snapshot.kind==='nte_gacha')return 1080
 const caps=c.snapshot.display_data.panels?.map(p=>p.capability)||[]
 if(caps.some(x=>['events','recent_events','combat','news','exploration','roles','vehicles','training','regions','ship','honor','operator_detail','gacha'].includes(x)))return 1080
 if(caps.length>2||c.id.includes('help')||c.snapshot.kind==='guide_index')return 1020
 return 960
}
