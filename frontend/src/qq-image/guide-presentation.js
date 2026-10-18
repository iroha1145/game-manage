// Group presentation units without changing source wording or punctuation.
export function guideLines(panel){
 const separators=panel.sectionKey==='teams'?/[；;\n]/: ['stats','echo_stats'].includes(panel.sectionKey)?/[；;。\n]/:null
 if(!separators)return [panel.text]
 const lines=[];let start=0
 for(let i=0;i<panel.text.length;i++)if(separators.test(panel.text[i])){lines.push(panel.text.slice(start,i+1));start=i+1}
 if(start<panel.text.length)lines.push(panel.text.slice(start))
 return lines.length?lines:[panel.text]
}
export function guideAtoms(tokens){
 const result=[]
 for(const source of tokens){
  const token={...source},previous=result.at(-1)
  if(!token.entity&&previous?.entity){
   const punctuation=token.text.match(/^[，、。；：！？,.;:!?／/＞>]+/)?.[0]
   if(punctuation){previous.trailing=punctuation;token.text=token.text.slice(punctuation.length)}
  }
  if(token.text)result.push(token)
 }
 return result
}
