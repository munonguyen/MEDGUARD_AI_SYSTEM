import assert from 'node:assert/strict';
import {splitSpeech, runSpeechQueue} from '../src/companion/speechQueue.js';

const text = 'Tôi đã ghi nhận thông tin của bạn. '.repeat(8) +
  'Không tự tăng liều 2.5 mg. Nếu đau ngực hoặc khó thở, hãy gọi cấp cứu ngay. Bạn bị từ khi nào?';
const chunks = splitSpeech(text);
assert.equal(chunks.join(' ').replace(/\s+/g, ' '), text.trim());
assert(chunks.every(c => c.length <= 360));
assert(chunks.some(c => c.includes('2.5 mg')));
assert.equal(splitSpeech('')[0], undefined);
assert.deepEqual(splitSpeech('Xin chào. Bạn cần hỗ trợ gì?'), ['Xin chào. Bạn cần hỗ trợ gì?']);
assert.equal(splitSpeech('a'.repeat(1200)).join(''), 'a'.repeat(1200));

const deferred = () => { let resolve; const promise = new Promise(r => {resolve=r;}); return {promise, resolve}; };
const first=deferred(), second=deferred(), playedFirst=deferred(), releaseFirst=deferred();
const prepared=[], played=[];
const controller = new AbortController();
const done = runSpeechQueue(['first', 'second', 'third'], {
  signal: controller.signal,
  synthesize: t => { prepared.push(t); return t==='first'?first.promise:t==='second'?second.promise:Promise.resolve(t); },
  play: async (_, t) => { played.push(t); if(t==='first'){playedFirst.resolve(); await releaseFirst.promise;} },
});
first.resolve('audio first');
await playedFirst.promise;
assert.deepEqual(prepared, ['first', 'second']);
assert.deepEqual(played, ['first']); // first audio does not await the second request
second.resolve('audio second'); releaseFirst.resolve(); await done;
assert.deepEqual(played, ['first', 'second', 'third']);

const cancel = new AbortController();
const queued = runSpeechQueue(['one', 'two'], {
  signal: cancel.signal,
  synthesize: async t => t,
  play: async () => cancel.abort(),
});
await assert.rejects(queued, {name:'AbortError'});
const failure = new Error('provider unavailable');
let read=0;
await assert.rejects(runSpeechQueue(['one','two'], {
  signal:new AbortController().signal,
  synthesize: async t => {if(t==='two')throw failure;return t;},
  play:async()=>{read++;},
}), error=>error===failure);
assert.equal(read,1);
console.log('speech queue: preserved warnings/decimals, early playback, ordered lookahead, cancellation and failure PASS');
