// Real bundled classifier and DSP, with generated audio. This verifies the
// pipeline/interrupt behavior, NOT Vietnamese lip-sync prediction accuracy.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Processor} from '../public/vendor/headaudio/processor.mjs';
import {Training} from '../public/vendor/headaudio/training.mjs';
const bytes=await readFile(new URL('../public/vendor/headaudio/model-en-mixed.bin',import.meta.url));
const {model}=await new Training().loadModel('data:application/octet-stream;base64,'+bytes.toString('base64'));
assert(model.length>10);const messages=[];
const p=new Processor({sampleRate:48000,processorOptions:{visemeEventsEnabled:true},parameterData:{silMode:0,vadGateActiveDb:-48,vadGateInactiveDb:-55}},{port:{postMessage:m=>messages.push(m)}});
p._onmessage({data:{event:'model',model}});
for(let block=0;block<1200;block++){
 const samples=new Float32Array(128);
 for(let i=0;i<128;i++){const t=(block*128+i)/48000;const voiced=t>.3&&t<2.3;const f=t<1.3?220:330;samples[i]=voiced?.15*(Math.sin(t*Math.PI*2*f)+.3*Math.sin(t*Math.PI*2*f*3)):0;}
 p.process(samples);
}
const visemes=messages.filter(m=>m.event==='viseme');assert(visemes.length>20);assert(visemes.every(m=>Number.isInteger(m.viseme)&&m.viseme>=0&&m.viseme<=14));assert(messages.some(m=>m.event==='started'));assert(messages.some(m=>m.event==='ended'));
p._onmessage({data:{event:'reset'}});assert.equal(p.sampleCount,0);assert.equal(p.isSpeaking,false);assert.equal(p.preemphasisPrevValue,0);
// Exercise the main-thread wrapper's index-0 fix without mocking its algorithm.
globalThis.AudioWorkletNode=class {constructor(){this.port={postMessage(){},close(){}};}};
const {HeadAudio}=await import('../public/vendor/headaudio/headaudio.mjs');
const node=new HeadAudio({});node._onmessage({data:{event:'viseme',viseme:0}});assert.equal(node.visemeActive,0);
let aa=0;node.onvalue=(name,value)=>{if(name==='viseme_aa')aa=value;};node.update(100);assert(aa>.6);
console.log('bundled model/DSP: generated voiced audio, silence, interruption reset and viseme index 0 PASS',{prototypes:model.length,frames:visemes.length});
