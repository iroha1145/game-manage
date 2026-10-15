import { requestJson } from './http-client.js'
export function generateQqLinkCode(){return requestJson('/api/qq/link-codes',{method:'POST'})}
export function listQqLinks(){return requestJson('/api/qq/link-attempts')}
export function unlinkQqLink(linkId){return requestJson(`/api/qq/links/${encodeURIComponent(linkId)}`,{method:'DELETE'})}
