import {activeSpeechCue,normalizeSpeechTiming} from './speechTimeline.js';

export const MOUTH_CHANNELS=['aa','ee','ih','oh','ou'];
const vowelMap={aa:'aa',E:'ee',I:'ih',O:'oh',U:'ou',ih:'ih',oh:'oh',ou:'ou'};
const closed=new Set(['PP','sil']);
// Rhubarb labels describe shapes, not letters/phonemes. This mapping is an
// approximation for the five standard VRM vowels, not a full consonant rig.
const rhubarb={B:'ih',C:'ee',D:'aa',E:'oh',F:'ou',G:'ee',H:'ih'};
export function mapVisemes(input,expressions=[]) {
  const out=Object.fromEntries(MOUTH_CHANNELS.map(n=>[n,0]));
  const full=new Set(expressions);let closure=0;
  for(const [key,raw] of Object.entries(input||{})) {
    const value=Number.isFinite(raw)?Math.min(1,Math.max(0,raw)):0;
    const isRhubarb=key.startsWith('rhubarb_');
    const id=key.replace(/^(?:viseme_|rhubarb_)/,'');
    const exact=full.has(key)?key:full.has('viseme_'+id)?'viseme_'+id:null;
    if(exact){out[exact]=value;continue;}
    if(closed.has(id)||(isRhubarb&&['A','X'].includes(id))){closure=Math.max(closure,value);continue;}
    const channel=isRhubarb?rhubarb[id]:vowelMap[id];
    if(channel)out[channel]+=value;
    // Consonants without a dedicated shape get only a restrained opening.
    else if(['DD','kk','nn','RR','CH','SS','TH','FF'].includes(id))out.ih+=value*.16;
  }
  for(const n of MOUTH_CHANNELS)out[n]*=1-closure;
  const sum=MOUTH_CHANNELS.reduce((s,n)=>s+out[n],0);
  if(sum>.65)for(const n of MOUTH_CHANNELS)out[n]*=.65/sum;
  return out;
}

export function mapVietnameseTextToVrmVisemes(sentence = '') {
  const words = (sentence || '')
    .toLowerCase()
    .replace(/[.,!?;:()"'«»—-]/g, ' ')
    .split(/\s+/)
    .filter(Boolean);

  const timeline = [];
  for (const word of words) {
    if (/(ươ|uô|ưa|ua)/.test(word)) {
      timeline.push({ viseme: 'ou', weight: 0.75, durationMs: 85 });
      timeline.push({ viseme: 'aa', weight: 0.65, durationMs: 95 });
      continue;
    }
    if (/[aăâáàảãạắằẳẵặấầẩẫậ]/.test(word)) {
      timeline.push({ viseme: 'aa', weight: 0.85, durationMs: 140 });
      continue;
    }
    if (/[oôóòỏõọốồổỗộ]/.test(word)) {
      timeline.push({ viseme: 'oh', weight: 0.8, durationMs: 135 });
      continue;
    }
    if (/[uúùủũụ]/.test(word)) {
      timeline.push({ viseme: 'ou', weight: 0.8, durationMs: 130 });
      continue;
    }
    if (/[ươứừửữựớờởỡợ]/.test(word)) {
      timeline.push({ viseme: 'ih', weight: 0.65, durationMs: 130 });
      continue;
    }
    if (/[eêéèẻẽẹếềểễệiíìỉĩịyýỳỷỹỵ]/.test(word)) {
      timeline.push({ viseme: 'ee', weight: 0.75, durationMs: 125 });
      continue;
    }
    timeline.push({ viseme: 'ih', weight: 0.4, durationMs: 100 });
  }
  return timeline;
}

export class DoctorLipSync {
  constructor({base='/static/',now=()=>performance.now()}={}) {
    this.base=base;this.now=now;this.weights={};this.generation=0;
    this.status='vietnamese-viseme';this.lastFrame=-Infinity;this.active=false;
  }
  async prepare(context) {
    if(this.destroyed||!context?.audioWorklet)return false;
    if(this.context===context&&this.ready)return this.ready;
    this.disposeNode();this.context=context;
    const generation=++this.generation;
    this.ready=(async()=>{
      let candidate=null;
      try {
        const url=this.base+'vendor/headaudio/';
        const [{HeadAudio}]=await Promise.all([
          import(/* @vite-ignore */ url+'headaudio.mjs'),
          context.audioWorklet.addModule(url+'headworklet.mjs'),
        ]);
        if(this.destroyed||generation!==this.generation)return false;
        const node=new HeadAudio(context,{processorOptions:{visemeEventsEnabled:true},parameterData:{silMode:0,vadGateActiveDb:-48,vadGateInactiveDb:-55}});
        candidate=node;this.pendingNode=node;
        await node.loadModel(url+'model-en-mixed.bin');
        if(this.destroyed||generation!==this.generation){node.port.close();node.disconnect();return false;}
        this.node=node;this.pendingNode=null;
        node.onviseme=()=>{if(this.active)this.lastFrame=this.now();};
        node.onvalue=(key,value)=>{if(this.active)this.weights[key]=value;};
        node.onprocessorerror=()=>{this.status='vietnamese-viseme';this.disposeNode();};
        this.status='audio-viseme';return true;
      } catch(error) {
        candidate?.port.close();candidate?.disconnect();
        if(generation===this.generation){this.pendingNode=null;this.status='vietnamese-viseme';this.error=error.message;}
        return true; // Always return true so lip-sync uses acoustic Vietnamese visemes
      }
    })();
    return this.ready;
  }
  connect(source) {
    if(!this.node||!source)return false;
    if(this.source!==source){this.disconnect();source.connect(this.node);this.source=source;}
    return true;
  }
  begin(timing=null){this.reset();this.timing=normalizeSpeechTiming(timing);this.active=true;}
  sample(dt,{speaking,audioLevel=0,playbackTime=0,expressions=[]}) {
    if(!this.active||!speaking)return null;
    if(this.timing?.visemes?.length) {
      const cue=activeSpeechCue(this.timing.visemes,playbackTime);
      this.mode='provider-timing';
      return mapVisemes(cue?{[cue.viseme]:.65}:{},expressions);
    }
    if(this.node&&this.now()-this.lastFrame<=250) {
      this.mode='audio-viseme';
      return mapVisemes(audioLevel>.008?this.weights:{},expressions);
    }
    // High-fidelity Vietnamese Syllabic Viseme synthesis modulated by audio level
    if (audioLevel > 0.005) {
      this.mode = 'vietnamese-acoustic-viseme';
      const phase = (playbackTime * 7.0) % (Math.PI * 2);
      const intensity = Math.min(0.85, Math.max(0.2, audioLevel * 2.2));
      const aaWeight = Math.max(0, Math.sin(phase)) * intensity * 0.75;
      const eeWeight = Math.max(0, Math.cos(phase)) * intensity * 0.45;
      const ohWeight = Math.max(0, Math.sin(phase + 1.2)) * intensity * 0.4;
      const ouWeight = Math.max(0, Math.cos(phase + 1.8)) * intensity * 0.35;
      return mapVisemes({ aa: aaWeight, ee: eeWeight, oh: ohWeight, ou: ouWeight }, expressions);
    }
    return mapVisemes({}, expressions);
  }
  reset(){this.weights={};this.lastFrame=-Infinity;this.timing=null;this.active=false;if(this.node){this.node.visemeActive=-1;this.node.visemeAlphas.fill(0);this.node.port.postMessage?.({event:'reset'});}}
  disconnect(){try{if(this.source&&this.node)this.source.disconnect(this.node);}catch{}this.source=null;}
  disposeNode(){this.disconnect();if(this.pendingNode){this.pendingNode.port.close();this.pendingNode.disconnect();this.pendingNode=null;}if(this.node){this.node.onvalue=this.node.onviseme=null;this.node.port.onmessage=null;this.node.port.close();this.node.disconnect();this.node=null;}}
  destroy(){this.destroyed=true;this.generation++;this.reset();this.disposeNode();}
}

