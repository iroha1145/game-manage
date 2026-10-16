import { requestResponse, safeDetail } from './http-client.js'
const ROOT='/api/admin/bilibili-source/login'
async function request(path,method='GET',signal,body,root=ROOT) {
  const timeout=AbortSignal.timeout(75000)
  let response
  try {
    response=await requestResponse(root+path,{method,signal:signal?AbortSignal.any([signal,timeout]):timeout,
      ...(body!==undefined?{body}:{})})
  } catch(error) {
    // The 75 s limit aborts with the engine's English TimeoutError text; a caller's own abort passes through.
    if(timeout.aborted&&!signal?.aborted) throw new Error('请求超时，请检查会话状态后重试')
    throw error
  }
  const data=await response.json().catch(()=>null)
  if(!response.ok) {
    const error=new Error(safeDetail(data?.detail,'B站授权暂不可用，请稍后重试'))
    // The raw code stays on detail for callers that branch on it (source_busy, source_backoff).
    Object.assign(error,{status:response.status,state:data?.state,errorCode:data?.error_code,detail:typeof data?.detail==='string'?data.detail.slice(0,256):''})
    throw error
  }
  if(!data||typeof data!=='object'||Array.isArray(data)) throw new Error('B站授权响应异常')
  return data
}
const session=sid=>'/sessions/'+encodeURIComponent(sid)
export const getCloudBilibiliStatus=signal=>request('/status','GET',signal)
export const startCloudBilibiliQr=signal=>request('/sessions','POST',signal,{mode:'qr'})
export const startCloudBilibiliCookie=signal=>request('/sessions','POST',signal,{mode:'cookie'})
export const submitCloudBilibiliSessdata=(sid,sessdata,signal)=>request(session(sid)+'/cookie','POST',signal,{sessdata})
export const pollCloudBilibiliQr=(sid,signal)=>request(session(sid)+'/qr/poll','POST',signal)
export const getCloudBilibiliSession=(sid,signal)=>request(session(sid),'GET',signal)
export const commitCloudBilibiliQr=(sid,signal)=>request(session(sid)+'/commit','POST',signal)
export const cancelCloudBilibiliQr=sid=>request(session(sid),'DELETE')
const COLLECTION='/api/admin/bilibili-source'
export const getCloudBilibiliSources=signal=>request('/status','GET',signal,undefined,COLLECTION)
export const refreshCloudBilibiliSource=(game,backfill,signal)=>request('/'+encodeURIComponent(game)+'/refresh','POST',signal,{backfill},COLLECTION)
