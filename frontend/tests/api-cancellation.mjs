import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
import {createApiClient} from '../src/api.js';
globalThis.crypto ??= webcrypto;
globalThis.window = {setTimeout,clearTimeout};
const api=createApiClient({tenantId:'test',apiKey:'test',consentToken:'test'});
const pending = signal => new Promise((_,reject)=>{
  const abort=()=>reject(new DOMException('cancelled','AbortError'));
  if(signal.aborted)abort();else signal.addEventListener('abort',abort,{once:true});
});
// Timeout must cover body consumption and still work with an external signal.
globalThis.fetch = async (_,o)=>({ok:true,headers:new Headers({'content-type':'audio/mpeg'}),blob:()=>pending(o.signal)});
await assert.rejects(api.request('/v1/tts',{responseType:'blob',timeoutMs:20,signal:new AbortController().signal}),e=>e.code==='response_timeout');
const controller=new AbortController();
const cancelled=api.request('/v1/tts',{responseType:'blob',timeoutMs:1000,signal:controller.signal});
controller.abort();await assert.rejects(cancelled,{name:'AbortError'});
globalThis.fetch=async(_,o)=>{assert.equal(o.credentials,'same-origin');return {ok:true,headers:new Headers({'content-type':'application/json'}),json:async()=>({reply:'safe'})};};
assert.deepEqual(await api.request('/v1/chat',{timeoutMs:1000}),{reply:'safe'});
console.log('API: combined cancellation/deadline, response body timeout, credentials retained PASS');
