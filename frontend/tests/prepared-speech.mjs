import assert from 'node:assert/strict';
import {preparedSpeechPlan, validateSpeechBlob, optionalAudioContext, optionalLipSync} from '../src/companion/preparedSpeech.js';
import {splitSpeech} from '../src/companion/speechQueue.js';
import {clinicalReply} from '../src/companion/clinicalReply.js';
const ticket='a'.repeat(32), text='Bạn cần đo nhiệt độ. Nếu khó thở, cần hỗ trợ khẩn cấp.';
const prepared={ticket,text:'Bạn cần đo nhiệt độ.',persona:'dr_tuan'};
const plan=preparedSpeechPlan(text,'dr_tuan',prepared,splitSpeech);
assert.equal(plan.ticket,ticket); assert.equal(plan.chunks.join(' '),text);
for(const invalid of [{...prepared,persona:'dr_mai'},{...prepared,text:'Nội dung đã sửa.'},{...prepared,ticket:'../unsafe'},
  {...prepared,text:'Bạn cần đo nhiệ'}]) assert.equal(preparedSpeechPlan(text,'dr_tuan',invalid,splitSpeech).ticket,null);
assert.equal(clinicalReply({spoken_reply:text,reply:'old',answer:{next_steps:['old duplicate']}}),text);
assert.throws(()=>validateSpeechBlob(new Blob()),/No playable/);
assert.throws(()=>validateSpeechBlob(new Blob(['error'],{type:'application/json'})),/No playable/);
assert.equal(validateSpeechBlob(new Blob(['ID3audio'],{type:'audio/mpeg'})).size,8);
assert.equal(optionalAudioContext(()=>{throw Error('unsupported audio context')}),null);
await optionalLipSync({prepareLipSync:async()=>{throw Error('classifier unavailable')}},{});
console.log('prepared speech: exact turn/persona prefix, preserved warnings, no-audio checks and optional lip-sync PASS');
