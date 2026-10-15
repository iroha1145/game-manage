import { requestResponse } from './http-client.js'
const ROOT='/api/admin/bilibili-source/login'
async function request(path,method='GET',signal,body,root=ROOT) {
  const timeout=AbortSignal.timeout(75000)
  const response=await requestResponse(root+path,{method,signal:signal?AbortSignal.any([signal,timeout]):timeout,
    ...(body!==undefined?{body}:{})})
  const data=await response.json().catch(()=>null)
  if(!response.ok) {
    const error=new Error(typeof data?.detail==='string'?data.detail.slice(0,256):'B站授权暂不可用，请稍后重试')
    Object.assign(error,{status:response.status,state:data?.state,errorCode:data?.error_code})
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
