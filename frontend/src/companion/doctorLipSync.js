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

export class DoctorLipSync {
  constructor({base='/static/',now=()=>performance.now()}={}) {
    this.base=base;this.now=now;this.weights={};this.generation=0;
    this.status='fallback';this.lastFrame=-Infinity;this.active=false;
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
        node.onprocessorerror=()=>{this.status='fallback';this.disposeNode();};
        this.status='audio-viseme';return true;
      } catch(error) {candidate?.port.close();candidate?.disconnect();if(generation===this.generation){this.pendingNode=null;this.status='fallback';this.error=error.message;}return false;}
    })();
    return this.ready;
  }
  connect(source) {
    if(!this.node||!source)return false;
    if(this.source!==source){this.disconnect();source.connect(this.node);this.source=source;}
    return true;
  }
  begin(timing=null){this.reset();this.timing=normalizeSpeechTiming(timing);this.active=true;}
  sample(dt,{speaking,audioLevel,playbackTime,expressions=[]}) {
    if(!this.active||!speaking)return null;
    if(this.timing?.visemes.length) {
      const cue=activeSpeechCue(this.timing.visemes,playbackTime);
      this.mode='provider-timing';
      return mapVisemes(cue?{[cue.viseme]:.65}:{},expressions);
    }
    this.node?.update(dt*1000);
    if(!this.node||this.now()-this.lastFrame>250){this.mode='spectrum-fallback';return null;}
    this.mode='audio-viseme';
    // A quiet/pause gate prevents the classifier's last prediction hanging on.
    return mapVisemes(audioLevel>.008?this.weights:{},expressions);
  }
  reset(){this.weights={};this.lastFrame=-Infinity;this.timing=null;this.active=false;if(this.node){this.node.visemeActive=-1;this.node.visemeAlphas.fill(0);this.node.port.postMessage?.({event:'reset'});}}
  disconnect(){try{if(this.source&&this.node)this.source.disconnect(this.node);}catch{}this.source=null;}
  disposeNode(){this.disconnect();if(this.pendingNode){this.pendingNode.port.close();this.pendingNode.disconnect();this.pendingNode=null;}if(this.node){this.node.onvalue=this.node.onviseme=null;this.node.port.onmessage=null;this.node.port.close();this.node.disconnect();this.node=null;}}
  destroy(){this.destroyed=true;this.generation++;this.reset();this.disposeNode();}
}
