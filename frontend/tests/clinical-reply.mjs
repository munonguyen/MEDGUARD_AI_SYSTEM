import assert from 'node:assert/strict';
import {clinicalReply, verificationNotice, awaitReviewedReply} from '../src/companion/clinicalReply.js';
const full=clinicalReply({reply:'Đánh giá ban đầu.',answer:{next_steps:['Theo dõi triệu chứng.'],safety_notes:['Nếu khó thở hãy gọi cấp cứu.'],questions:['Bạn bị từ khi nào?']}});
assert(full.includes('Theo dõi triệu chứng.'));assert(full.includes('Nếu khó thở'));assert(full.includes('Bạn bị từ khi nào?'));
assert.equal(clinicalReply({reply:'summary',verification_status:'verified',answer:{narrative:[{text:'Câu trả lời theo câu hỏi.'}]}}),'Câu trả lời theo câu hỏi.');
assert(verificationNotice({verification_status:'unavailable'}).includes('quy tắc'));
let polls=0;
const data={request_id:'current',verification_status:'shadow_pending'};
const reviewed=await awaitReviewedReply(data,async()=>({messages:[{role:'assistant',request_id:'other',verification_status:'verified',content:'wrong'},
 {role:'assistant',request_id:'current',verification_status:++polls===2?'verified':'shadow_pending',content:'final'}]}),{signal:new AbortController().signal,intervalMs:1,maxWaitMs:1000});
assert.equal(reviewed.reply,'final');assert.equal(polls,2);
const controller=new AbortController();const pending=awaitReviewedReply(data,async()=>({messages:[]}),{signal:controller.signal});controller.abort();
await assert.rejects(pending,{name:'AbortError'});
console.log('clinical response: full warning/follow-up, verified narrative, exact request promotion and cancellation PASS');
