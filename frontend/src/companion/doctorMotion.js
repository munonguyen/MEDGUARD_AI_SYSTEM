import { Euler, Matrix4, Quaternion, Vector3, Object3D } from 'three';
import { GesturePlanner, motionContext, phraseIntent, splitMotionPhrases } from './doctorMotionContext.js';
import { choreograph } from './gestureChoreography.js';
import { normalizeSpeechTiming, activeSpeechCue } from './speechTimeline.js';
import { MOUTH_CHANNELS } from './doctorLipSync.js';

// AIRI Eye Saccade Interval Distribution Matrix
const EYE_SACCADE_INT_STEP = 400;
const EYE_SACCADE_INT_P = [
  [0.075, 800],
  [0.110, 0],
  [0.125, 0],
  [0.140, 0],
  [0.125, 0],
  [0.050, 0],
  [0.040, 0],
  [0.030, 0],
  [0.020, 0],
  [1.000, 0],
];
for (let i = 1; i < EYE_SACCADE_INT_P.length; i++) {
  EYE_SACCADE_INT_P[i][0] += EYE_SACCADE_INT_P[i - 1][0];
  EYE_SACCADE_INT_P[i][1] = EYE_SACCADE_INT_P[i - 1][1] + EYE_SACCADE_INT_STEP;
}

export function randomSaccadeInterval(rng = Math.random) {
  const r = rng();
  for (let i = 0; i < EYE_SACCADE_INT_P.length; i++) {
    if (r <= EYE_SACCADE_INT_P[i][0]) {
      return EYE_SACCADE_INT_P[i][1] + rng() * EYE_SACCADE_INT_STEP;
    }
  }
  return EYE_SACCADE_INT_P.at(-1)[1] + rng() * EYE_SACCADE_INT_STEP;
}

// AIRI Cubic Easing for facial expressions
const easeInOutCubic = t => t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;

// AIRI Orthonormal Pole Vector
function orthonormalizePole(dir, pole) {
  const poleOrtho = pole.clone().addScaledVector(dir, -pole.dot(dir));
  if (poleOrtho.lengthSq() <= 1e-12) return null;
  return poleOrtho.normalize();
}

const REST = {
  hips:[0,0,0], spine:[0,0,0], chest:[0,0,0], upperChest:[0,0,0], neck:[0,0,0], head:[0,0,0],
  leftShoulder:[0,0,0], rightShoulder:[0,0,0],
  leftUpperArm:[.06,.02,1.42], rightUpperArm:[.06,-.02,-1.42],
  leftLowerArm:[.08,0,0], rightLowerArm:[.08,0,0],
  leftHand:[.02,0,0], rightHand:[.02,0,0],
};
const clamp = (v,min=0,max=1) => Math.max(min,Math.min(max,v));
const damp = (rate,dt) => 1-Math.exp(-rate*dt);
const ease = x => { x=clamp(x);return x*x*x*(x*(x*6-15)+10); };
const pulse = (t,start,duration) => {const x=(t-start)/duration;return x>0&&x<1?Math.sin(Math.PI*x)**2:0;};
const envelope = (t,delay,duration) => {const x=(t-delay)/duration;return x<=0||x>=1?0:ease(x/.27)*(1-ease((x-.58)/.42));};
// Bounded critically damped springs preserve velocity when a user interrupts.
function spring(state,target,omega,dt,maxSpeed) {
  const count=Math.max(1,Math.ceil(dt*120)),h=dt/count;
  for(let i=0;i<count;i++) {
    const acceleration=clamp(omega*omega*(target-state.position)-2*omega*state.velocity,-maxSpeed*5,maxSpeed*5);
    const velocity=clamp(state.velocity+acceleration*h,-maxSpeed,maxSpeed);
    state.position+=(state.velocity+velocity)*.5*h;state.velocity=velocity;
  }
}
const state = position => ({position,velocity:0});
const fingerNames = ['Thumb','Index','Middle','Ring','Little'];
const segments = finger => finger==='Thumb'?['Metacarpal','Proximal','Distal']:['Proximal','Intermediate','Distal'];
const SPLAY_AXIS = new Vector3(0,1,0);

export class DoctorMotion {
  constructor(vrm,persona,{random=Math.random}={}) {
    this.vrm=vrm;this.persona=persona;this.random=random;this.planner=new GesturePlanner(random);
    this.pose='pose_idle';this.poseStarted=0;this.tone='empathetic';this.expression='neutral';
    this.time=0;this.speechTime=0;this.speechWeight=0;this.pauseAge=10;this.audioAccent=0;
    this.values={};this.euler=new Euler();this.q=new Quaternion();this.q2=new Quaternion();
    const expressions=Object.keys(vrm.expressionManager?.expressionMap||{});
    const aliases=terms=>expressions.filter(n=>terms.includes(n.toLowerCase().replace(/[^a-z]/g,'')));
    this.faceDetails={browUp:aliases(['browinnerup']),browDown:aliases(['browdownleft','browdownright']),
      cheeks:aliases(['cheeksquintleft','cheeksquintright','cheekraise'])};
    this.surpriseName=vrm.expressionManager?.getExpression?.('Surprised')&&!vrm.expressionManager?.getExpression?.('surprised')?'Surprised':'surprised';
    this.bones=Object.fromEntries(Object.keys(REST).map(n=>[n,vrm.humanoid?.getNormalizedBoneNode(n)]));
    this.modernAxes=vrm.meta?.metaVersion==='1' || (vrm.humanoid?.getNormalizedBoneNode('rightLowerArm')?.position.x??0)<-.01;
    this.rest=Object.fromEntries(Object.entries(REST).map(([n,xyz])=>[n,xyz.map((v,i)=>this.modernAxes&&i!==1?-v:v)]));
    this.joints=Object.fromEntries(Object.entries(this.rest).map(([n,xyz])=>[n,xyz.map(state)]));
    this.targets=Object.fromEntries(Object.entries(REST).map(([n,xyz])=>[n,[...xyz]]));
    this.transitionFrom=Object.fromEntries(Object.keys(REST).map(n=>[n,new Quaternion()]));
    this.pendingTransition=false;this.transitionAt=-10;this.transitionDuration=.3;
    for(const [n,xyz] of Object.entries(this.rest)) this.bones[n]?.quaternion.setFromEuler(this.euler.set(...xyz));
    this.armOutput=Object.fromEntries(Object.entries(this.bones).filter(([n,b])=>b&&(n.includes('Arm')||n.endsWith('Hand'))).map(([n,b])=>[n,b.quaternion.clone()]));
    this.blinkAt=2.2+random()*2;this.blinkStarted=-10;
    this.doubleBlinkAt=0;this.pendingDoubleBlink=false;this.wasThinking=false;
    this.eye={x:0,y:0};this.headLook={x:0,y:0};this.saccade={x:0,y:0};this.saccadeAt=0;
    this.nextSaccadeAfter=randomSaccadeInterval(random)/1000;
    this.timeSinceLastSaccade=0;
    this.fixationTarget=new Vector3();
    this.glanceOffset={x:0,y:0};this.glanceNext=3.5+random()*2.5;this.glanceTimer=0;
    this.thinkSide=random()<.5?-1:1;
    this.weight=state(0);this.weightFrom=0;this.weightTarget=.6;this.weightAt=0;this.weightNext=15+random()*10;
    this.breathRecovery=0;this.quietFor=0;this.speakingFor=0;this.previousAudible=false;this.beatAt=-10;
    this.breathPhase=0;this.breathPeriod=4.1;this.voicedRun=0;this.breathPauseHandled=true;
    this.fingers=[];this.handStates={left:{openness:0,pose:'soft'},right:{openness:0,pose:'soft'}};
    for(const side of ['left','right'])for(const [index,finger] of fingerNames.entries()) {
      const names=segments(finger);
      for(const [segment,part] of names.entries()) {
        const name=side+finger+part,bone=vrm.humanoid?.getNormalizedBoneNode(name);
        if(!bone)continue;
        const child=vrm.humanoid?.getNormalizedBoneNode(side+finger+names[segment+1]);
        const direction=child?.position.clone() || bone.position.clone();
        if(direction.lengthSq()<1e-8)direction.set(side==='left'?1:-1,0,0);
        const axis=direction.normalize().cross(new Vector3(0,-1,0)).normalize();
        const idle=(finger==='Thumb'?.28:.32+index*.055)*(segment===0?1:segment===1?.72:.5);
        this.fingers.push({name,bone,finger,index,segment,side,axis,idle,curl:state(idle),splay:state(0),q:new Quaternion()});
      }
    }
    // Use the model's gaze applier (bone or expression) instead of competing
    // look blendshapes that VRM.update may overwrite. Public angles are degrees.
    if(vrm.lookAt){
      vrm.lookAt.autoUpdate=false;
      if(!vrm.lookAt.target) vrm.lookAt.target = new Object3D();
    }
    this.forward=vrm.lookAt?.faceFront?.clone() || new Vector3(0,0,vrm.meta?.metaVersion==='0'?-1:1);
    this.legs=this.captureLegs();
    this.arms=this.captureArms();
    this.armGoals=Object.fromEntries(['left','right'].map(side=>[side,{weight:0,target:0,x:.2,y:.04,z:.21,tx:.2,ty:.04,tz:.21,ny:1,nz:.12,twist:state(0)}]));
    this.hipRest=this.bones.hips?.position.clone();
    this.startUtterance('');
  }
  samplePoissonBlinkInterval(cautious,think){
    const mean=cautious?4.4:think?4.8:3.4;
    const u=clamp(this.random(),.02,.98);
    return clamp(-Math.log(1-u)*mean,2.0,6.2);
  }
  captureLegs() {
    const legs=[];
    for(const side of ['left','right']) {
      const upper=this.vrm.humanoid?.getNormalizedBoneNode(side+'UpperLeg');
      const lower=this.vrm.humanoid?.getNormalizedBoneNode(side+'LowerLeg');
      const foot=this.vrm.humanoid?.getNormalizedBoneNode(side+'Foot');
      if(!upper||!lower||!foot)continue;
      const a=upper.getWorldPosition(new Vector3()),b=lower.getWorldPosition(new Vector3()),c=foot.getWorldPosition(new Vector3());
      const l1=a.distanceTo(b),l2=b.distanceTo(c);
      if(l1<.01||l2<.01)continue;
      legs.push({upper,lower,foot,l1,l2,anchor:c,footQ:foot.getWorldQuaternion(new Quaternion()),
        a:new Vector3(),b:new Vector3(),c:new Vector3(),direction:new Vector3(),pole:new Vector3(),knee:new Vector3(),delta:new Quaternion(),worldQ:new Quaternion(),parentQ:new Quaternion()});
    }
    return legs;
  }
  captureArms() {
    const arms=[];
    for(const side of ['left','right']) {
      const upper=this.bones[side+'UpperArm'],lower=this.bones[side+'LowerArm'],hand=this.bones[side+'Hand'];
      if(!upper||!lower||!hand)continue;
      const a=upper.getWorldPosition(new Vector3()),b=lower.getWorldPosition(new Vector3()),c=hand.getWorldPosition(new Vector3());
      const l1=a.distanceTo(b),l2=b.distanceTo(c);
      if(l1<.01||l2<.01)continue;
      arms.push({side,upper,lower,hand,l1,l2,a:new Vector3(),b:new Vector3(),c:new Vector3(),target:new Vector3(),chest:new Vector3(),
        direction:new Vector3(),pole:new Vector3(),elbow:new Vector3(),delta:new Quaternion(),worldQ:new Quaternion(),parentQ:new Quaternion(),from:new Quaternion(),
        palm:new Vector3(),normal:new Vector3(),axisX:new Vector3(),axisY:new Vector3(),axisZ:new Vector3(),matrix:new Matrix4(),
        fingerSign:Math.sign(this.vrm.humanoid?.getNormalizedBoneNode(side+'IndexProximal')?.position.x||lower.position.x)});
    }
    return arms;
  }
  setPose(pose) {
    if(pose===this.pose&&pose!=='pose_wave')return;
    this.pose=pose;this.poseStarted=this.time;this.pendingTransition=true;
    if(pose==='pose_thinking')this.thinkSide=this.random()<.5?-1:1;
    if(pose==='pose_wave')this.previewCue=this.planner.select('greeting',this.tone);
  }
  setExpression(expression) {this.expression=expression;}
  setContext(question='',metadata={}) {
    // A server severity tag can make the motion serious; it never changes care.
    this.questionContext=motionContext(question,'clinical');
    this.severe=['HIGH','CRITICAL'].includes(String(metadata.severity||'').toUpperCase());
    this.pendingTransition=true;
  }
  startUtterance(text='') {
    this.utteranceText=text;this.speechTime=0;this.segmentTime=0;this.segmentOffset=0;this.segmentPlan=null;this.segmentTiming=null;
    const context=this.severe?'cautious':this.questionContext||this.tone||'clinical';
    this.utterancePlan=this.planner.plan(text,context);
    this.gesturePlan=this.utterancePlan.map(p=>p.intent);
    this.gestureDurations=this.utterancePlan.map(p=>p.duration);
    this.currentCue=null;this.currentCueKey='';this.freeCue=null;this.pendingTransition=true;
  }
  beginSpeechSegment(text='',timing=null) {
    this.segmentTiming=normalizeSpeechTiming(timing);
    const phrases=splitMotionPhrases(text),context=this.severe?'cautious':this.questionContext||this.tone;
    this.segmentPlan=phrases.map((phrase,i)=>{
      const existing=this.utterancePlan[this.segmentOffset+i];
      // Normalization may alter whitespace/numbers in TTS. Only reuse a cue
      // when the actual spoken phrase has the same semantic intent.
      const intent=phraseIntent(phrase,context);
      return {...(existing?.intent===intent?existing:this.planner.select(intent,context==='cautious'?context:motionContext(phrase,context))),text:phrase};
    });
    if(!this.segmentPlan.length)this.segmentPlan=this.utterancePlan;
    this.segmentOffset+=phrases.length;this.segmentTime=0;this.currentCueKey='';
  }
  cueAt(speaking,responding,playbackTime,playbackDuration) {
    if(this.pose==='pose_wave')return {cue:this.previewCue,phase:this.time-this.poseStarted,duration:3.4,key:'preview-'+this.poseStarted};
    const plan=this.segmentPlan||this.utterancePlan;
    if(speaking&&this.segmentTiming?.phrases.length) {
      const phrase=activeSpeechCue(this.segmentTiming.phrases,playbackTime);
      if(!phrase)return {cue:plan[0],phase:0,duration:1,key:'timed-rest',rest:true};
      const key='timed-'+phrase.start;
      if(this.currentCueKey!==key){
        const context=this.severe?'cautious':motionContext(phrase.text,this.questionContext||this.tone);
        this.freeCue=this.planner.select(phraseIntent(phrase.text,context),context);this.currentCueKey=key;this.pendingTransition=true;
      }
      // One meaningful stroke per phrase, then settle during long explanation.
      const duration=Math.min(5,Math.max(1.2,phrase.end-phrase.start));
      return {cue:this.freeCue,phase:playbackTime-phrase.start,duration,key,rest:playbackTime-phrase.start>duration};
    }
    if(speaking&&this.segmentPlan&&Number.isFinite(playbackDuration)&&playbackDuration>0) {
      // Character weights estimate sentence boundaries inside an audio file.
      // Real media time prevents drift through stalls and queued TTS gaps.
      const total=plan.reduce((n,p)=>n+Math.max(12,p.text.length),0);
      let start=0;
      for(let i=0;i<plan.length;i++) {
        const span=playbackDuration*Math.max(12,plan[i].text.length)/total;
        if(playbackTime<start+span||i===plan.length-1) {
          const age=clamp(playbackTime-start,0,span),duration=Math.min(5.3,span);
          const key=`${this.segmentOffset}:${i}`;
          if(key!==this.currentCueKey) {
            this.freeCue=plan[i];
            this.currentCueKey=key;this.pendingTransition=true;
          }
          return {cue:this.freeCue,phase:age,duration:Math.max(1.2,duration),key,rest:age>duration};
        }
        start+=span;
      }
    }
    let phase=responding?this.time-this.poseStarted:this.speechTime;
    for(let i=0;i<plan.length;i++) {
      if(phase<plan[i].duration)return {cue:plan[i],phase,duration:plan[i].duration,key:'plan-'+i};
      phase-=plan[i].duration;
    }
    // Long speech stays within the last sentence intent, with a new alternative
    // each phrase. A greeting is performed once, never looped across the answer.
    const last=plan.at(-1),intent=last.intent==='greeting'?'explain':last.intent;
    if(!this.freeCue||this.freeCueAt===undefined||this.speechTime-this.freeCueAt>=this.freeCue.duration) {
      this.freeCue=this.planner.select(intent,last.emotion);this.freeCueAt=this.speechTime;
    }
    return {cue:this.freeCue,phase:Math.max(0,this.speechTime-(this.freeCueAt||0)),duration:this.freeCue.duration,key:'tail-'+this.freeCueAt};
  }
  update(dt,{speaking=false,look={x:0,y:0},audioLevel=0,hasAudio=false,spectrum=null,visemes=null,playbackTime,playbackDuration,reducedMotion=false}={}) {
    dt=clamp(dt,0,.15);this.time+=dt;if(speaking){this.speechTime+=dt;this.segmentTime+=dt;}
    const time=this.time,replyAge=time-this.poseStarted;
    const responding=this.pose==='pose_acknowledge'&&replyAge<3.8;
    const listen=this.pose==='pose_listening',think=this.pose==='pose_thinking';
    this.pauseAge=speaking?0:this.pauseAge+dt;
    this.speechWeight+=((speaking||responding||this.pauseAge<.18?1:0)-this.speechWeight)*damp(7,dt);
    this.audioAccent+=(clamp(audioLevel*5)-this.audioAccent)*damp(9,dt);
    const audible=speaking&&hasAudio&&audioLevel>.012;
    this.quietFor=audible?0:this.quietFor+dt;this.speakingFor=audible?this.speakingFor+dt:0;
    if(audible){this.voicedRun+=dt;this.breathPauseHandled=false;}
    if(this.quietFor>.18&&!this.breathPauseHandled){if(this.voicedRun>2.5)this.breathRecovery=.15;this.voicedRun=0;this.breathPauseHandled=true;}
    if(audible&&!this.previousAudible&&time-this.beatAt>.65)this.beatAt=time;
    this.previousAudible=audible;this.breathRecovery*=Math.exp(-dt*.8);
    this.breathPhase+=dt*2*Math.PI/this.breathPeriod;
    if(this.breathPhase>=2*Math.PI){this.breathPhase-=2*Math.PI;this.breathPeriod=3.5+this.random();}
    const action=this.cueAt(speaking,responding,playbackTime??this.segmentTime,playbackDuration);
    if(action.key!==this.lastActionKey){this.lastActionKey=action.key;this.pendingTransition=true;}
    this.currentCue=action.cue;
    this.activeGesture=speaking||responding||this.pose==='pose_wave'?action.cue.intent:'idle';
    this.activeVariant=action.cue.variant.id;
    const emotion=this.severe?'cautious':(speaking||responding||this.pose==='pose_wave')?action.cue.emotion:this.questionContext||this.tone;
    this.contextState=think?'thinking':listen?'listening':emotion;
    const cautious=emotion==='cautious',empathetic=emotion==='empathetic';
    const targets=this.targets;
    this.armGoals.left.target=this.armGoals.right.target=0;
    for(const [n,xyz] of Object.entries(REST))for(let i=0;i<3;i++)targets[n][i]=xyz[i];
    if(this.glanceTimer>0){
      this.glanceTimer-=dt;
      if(this.glanceTimer<=0){this.glanceOffset.x=0;this.glanceOffset.y=0;this.glanceNext=time+3.8+this.random()*3.0;}
    } else if(time>=this.glanceNext&&!think&&!listen&&Math.abs(look.x)<0.35){
      this.glanceOffset.x=(this.random()<.5?-1:1)*(0.11+this.random()*0.07);
      this.glanceOffset.y=(this.random()-.25)*0.08;
      this.glanceTimer=0.75+this.random()*0.40;
      if(time-this.blinkStarted>1.8&&this.random()<.55){
        this.blinkStarted=time;
        this.blinkAt=time+this.samplePoissonBlinkInterval(cautious,think);
      }
    }
    const glanceX=(!think&&!listen&&Math.abs(look.x)<0.35)?this.glanceOffset.x:0;
    const glanceY=(!think&&!listen&&Math.abs(look.y)<0.35)?this.glanceOffset.y:0;
    const eyeTarget={x:clamp(look.x+glanceX,-1,1),y:clamp(look.y+glanceY,-1,1)};
    if(think){eyeTarget.x=eyeTarget.x*.35+this.thinkSide*.34;eyeTarget.y=eyeTarget.y*.35+.25;}
    this.eye.x+=(eyeTarget.x-this.eye.x)*damp(22,dt);this.eye.y+=(eyeTarget.y-this.eye.y)*damp(22,dt);
    this.headLook.x+=(this.eye.x-this.headLook.x)*damp(4,dt);this.headLook.y+=(this.eye.y-this.headLook.y)*damp(4,dt);
    this.timeSinceLastSaccade+=dt;
    if(this.timeSinceLastSaccade>=this.nextSaccadeAfter||time>=this.saccadeAt){
      this.saccade={x:(this.random()-.5)*.018,y:(this.random()-.5)*.012};
      this.timeSinceLastSaccade=0;
      this.nextSaccadeAfter=randomSaccadeInterval(this.random)/1000;
      this.saccadeAt=time+this.nextSaccadeAfter;
    }
    if(this.vrm.lookAt?.target){
      const headNode=this.bones.head||this.vrm.humanoid?.getNormalizedBoneNode('head');
      const headPos=headNode?headNode.getWorldPosition(new Vector3()):new Vector3(0,1.35,0);
      this.fixationTarget.set(headPos.x+this.eye.x*.8+this.saccade.x*2,headPos.y+this.eye.y*.6+this.saccade.y*2,headPos.z+(this.forward.z<0?-1.5:1.5));
      this.vrm.lookAt.target.position.lerp(this.fixationTarget,1);
    }
    const gazeX=this.eye.x,gazeY=this.eye.y;
    if(!reducedMotion) {
      const breath=Math.sin(this.breathPhase),breathScale=1+this.breathRecovery+(speaking?clamp(this.utteranceText.length/800)*.1:0);
      if(time>=this.weightNext){this.weightFrom=this.weight.position;this.weightTarget=-Math.sign(this.weightTarget||1)*(.45+this.random()*.25);this.weightAt=time;this.weightNext=time+15+this.random()*10;}
      const weightTarget=this.weightFrom+(this.weightTarget-this.weightFrom)*ease((time-this.weightAt)/1.8);
      spring(this.weight,weightTarget,5,dt,1);
      const shift=this.weight.position;
      targets.hips[2]=shift*.007;targets.spine[2]=-shift*.012;targets.chest[2]=shift*.006;
      targets.spine[0]=breath*.004*breathScale;targets.chest[0]=breath*.007*breathScale;
      targets.upperChest[0]=Math.sin(this.breathPhase-.13)*.003*breathScale;
      // AIRI natural clavicle rise during inhalation
      targets.leftShoulder[0]=Math.sin(this.breathPhase-.2)*.0035*breathScale;
      targets.rightShoulder[0]=Math.sin(this.breathPhase-.2)*.0035*breathScale;
      targets.leftShoulder[2]=Math.sin(this.breathPhase-.3)*.005*breathScale-shift*.004;
      targets.rightShoulder[2]=-Math.sin(this.breathPhase-.1)*.005*breathScale-shift*.004;
      targets.leftLowerArm[2]+=Math.sin(time*.41)*.008;
      targets.rightLowerArm[2]-=Math.sin(time*.37+.8)*.008;
      // AIRI living subconscious postural micro-sway and respiratory head bob
      const swayCoronal=Math.sin(time*1.38)*.0022;
      const swaySagittal=Math.cos(time*1.07)*.0018;
      targets.spine[1]+=swayCoronal;
      targets.head[1]+=swayCoronal*1.15;
      targets.spine[0]+=swaySagittal;
      targets.head[0]-=Math.sin(this.breathPhase)*.004*breathScale;
      if(listen){const nod=pulse((time-this.poseStarted)%7.3,1.15,1.3);targets.spine[0]-=.013;targets.neck[0]+=.018*nod;targets.head[0]+=.035*nod;}
      if(think){
        // Thoughtful contemplative posture: head tilt + subtle chest shift, arms stay naturally relaxed
        targets.chest[1] -= this.thinkSide * .014;
        targets.head[1] += this.thinkSide * .045;
        targets.head[2] += this.thinkSide * .022;
        targets.head[0] -= .015;
        this.handStates.left = { openness: 0, pose: 'soft' };
        this.handStates.right = { openness: 0, pose: 'soft' };
      }
      if(responding){const ack=pulse(replyAge,.1,1.3);targets.head[0]+=ack*.042;targets.neck[0]+=ack*.020;targets.chest[0]+=ack*.015;}
      targets.head[0]+=this.headLook.y*.09+(listen?-.025:think?.02:0);
      targets.head[1]+=this.headLook.x*.22;targets.head[2]+=listen?.022:0;
      targets.neck[0]+=this.headLook.y*.035;targets.neck[1]+=this.headLook.x*.055;
      targets.chest[1]+=this.headLook.x*.022;
      const {cue,phase,duration}=action;
      const active=!action.rest&&(speaking||responding||this.pose==='pose_wave');
      const weight=(this.pose==='pose_wave'?1:this.speechWeight)*cue.energy;
      const strength=active?weight:0;
      this.applyGesture(targets,cue,phase,duration,strength);
      const beat=pulse(time-this.beatAt,.06,.55)*strength;
      targets.head[0]+=beat*.024;targets.neck[0]+=beat*.012;
      if(empathetic){targets.chest[0]-=.018;targets.head[0]-=.014;targets.leftShoulder[2]-=.006;targets.rightShoulder[2]+=.006;}
      if(cautious){targets.chest[0]+=.006;targets.head[2]*=.35;}
      targets.spine[1]+=Math.sin(time*.53)*.005;targets.head[1]+=Math.sin(time*.42)*.005;
    }
    this.applyJoints(dt,reducedMotion);
    this.animationLayer?.apply(dt,{...action,active:!action.rest&&(speaking||responding||this.pose==='pose_wave'),reducedMotion});
    if(this.hipRest&&this.legs.length) {
      // Millimetre-scale weight transfer plus two-bone IK preserves planted feet.
      const hip=this.bones.hips;
      hip.position.copy(this.hipRest);if(!reducedMotion){hip.position.x+=this.weight.position*.004;hip.position.y-=.0006;}
      this.plantFeet();
    }
    this.placeHands(dt,reducedMotion);
    // IK corrections obey the same final angular speed budget as authored
    // gestures, including an interruption halfway through a held hand pose.
    for(const [name,previous] of Object.entries(this.armOutput)) {
      const bone=this.bones[name];previous.rotateTowards(bone.quaternion,dt*(name.endsWith('Hand')?2.1:3.2));bone.quaternion.copy(previous);
    }
    this.updateFingers(dt,reducedMotion);
    this.updateFace(dt,{speaking,hasAudio,audioLevel,spectrum,visemes,cautious,empathetic,think,listen,reducedMotion,gazeX,gazeY});
    this.vrm.update(dt);
  }
  applyGesture(targets,cue,phase,duration,strength) {
    const style=cue.variant,arm=cue.side,other=arm==='left'?'right':'left',sign=arm==='left'?-1:1;
    const shoulder=envelope(phase,.06,Math.max(.8,duration-.18))*strength;
    const elbow=envelope(phase,0,Math.max(.8,duration-.08))*strength;
    const wrist=envelope(phase,.17,Math.max(.8,duration-.25))*strength;
    const arc=Math.sin(phase*1.6+.4)*wrist*(style.arc||.016);
    targets[arm+'Shoulder'][1]-=sign*shoulder*.025;targets[arm+'Shoulder'][2]+=sign*shoulder*.018;
    targets[arm+'UpperArm'][0]+=shoulder*.17;targets[arm+'UpperArm'][1]-=sign*shoulder*style.yaw;
    targets[arm+'UpperArm'][2]+=sign*shoulder*style.lift;
    targets[arm+'LowerArm'][0]-=elbow*.20;targets[arm+'LowerArm'][2]+=sign*elbow*style.bend;
    targets[arm+'LowerArm'][1]+=sign*arc*.6;
    targets[arm+'Hand'][0]+=wrist*.09+arc+this.audioAccent*wrist*.018;
    targets[arm+'Hand'][1]-=sign*wrist*style.turn;targets[arm+'Hand'][2]-=sign*wrist*.10;
    const secondary=envelope(phase,.28,Math.max(.8,duration-.4))*strength*(style.secondary||.065);
    targets[other+'UpperArm'][0]+=secondary*.11;targets[other+'UpperArm'][1]+=sign*secondary*.10;
    targets[other+'UpperArm'][2]-=sign*secondary*style.lift*.78;
    targets[other+'LowerArm'][2]-=sign*secondary*(style.bend*.83);
    targets[other+'LowerArm'][0]-=secondary*.13;
    targets[other+'Hand'][1]+=sign*secondary*style.turn*.8;
    targets[other+'Hand'][0]+=secondary*.07;
    targets.hips[1]-=sign*shoulder*.009;targets.spine[1]-=sign*shoulder*.012;
    targets.chest[1]+=sign*shoulder*.026;targets.chest[0]+=shoulder*style.lean;
    targets.spine[2]+=sign*shoulder*.010;targets.head[2]-=sign*wrist*.016;
    targets.head[0]+=pulse(phase,.9,Math.max(.8,duration*.4))*strength*.022;
    if(cue.intent==='greeting') {
      // AIRI dignified clinical greeting: polite subtle head/chest bow + soft hand gesture
      targets.head[0] += pulse(phase, 0.2, 1.4) * strength * 0.038;
      targets.chest[0] += pulse(phase, 0.2, 1.4) * strength * 0.016;
      targets[arm+'Hand'][2]+=Math.sin(phase*4.2)*envelope(phase,.55,Math.min(1.8,duration-.55))*strength*(style.wave * 0.6);
      targets.head[2]-=shoulder*.012;
    }
    this.handStates[arm]={openness:wrist,pose:style.fingers};
    this.handStates[other]={openness:secondary,pose:'soft'};
    // Task-space goals bring gestures in FRONT of the patient, not sideways.
    // FK still supplies preparation, articulation and wrist twist; IK gently
    // guides the upper/lower arm without straightening the elbow.
    if(cue.intent==='greeting') {
      // Compact gesture in front of the upper chest, elbow below the hand.
      const wave=envelope(phase,.55,Math.min(1.8,duration-.55));
      Object.assign(this.armGoals[arm],{target:shoulder,tx:.135+Math.sin(phase*4.2)*wave*.007,
        ty:.065,tz:.21,palm:'offer'});
    } else {
      const compact=cue.intent==='caution'||cue.intent==='enumerate';
      const heart=style.id==='hand-near-heart';
      Object.assign(this.armGoals[arm],{target:shoulder,tx:heart?.065:compact?.15:cue.intent==='compare'?.23:.18,
        ty:heart?.04:compact?.065:cue.intent==='reassure'?.015:.035,
        tz:heart?.17:compact?.19:.22+(style.arc||0)*Math.sin(phase*1.3),palm:heart?'heart':style.id==='compact-stop'?'stop':'offer'});
      if(style.secondary)Object.assign(this.armGoals[other],{target:secondary,tx:cue.intent==='compare'?.22:.17,ty:.015,tz:.20,palm:'offer'});
    }
    const point=choreograph(cue.intent,phase,duration,style);
    // Scale adult reference-space paths for a different-sized custom rig.
    const chain=this.arms.find(a=>a.side===arm);
    const scale=chain?clamp((chain.l1+chain.l2)/.52,.65,1.3):1;
    Object.assign(this.armGoals[arm],{tx:point[0]*scale,ty:point[1]*scale,tz:point[2]*scale});
    if(style.secondary){const secondaryPoint=choreograph(cue.intent,Math.max(0,phase-.2),duration,style);Object.assign(this.armGoals[other],{tx:secondaryPoint[0]*.94*scale,ty:secondaryPoint[1]*.6*scale,tz:secondaryPoint[2]*.9*scale});}
  }
  applyJoints(dt,reducedMotion) {
    // The shipped VRM0 rigs author +X on the right arm. Modern +Z-facing
    // normalized rigs need the corresponding 180° Y-frame conversion.
    if(this.modernAxes)for(const xyz of Object.values(this.targets)){xyz[0]*=-1;xyz[2]*=-1;}
    if(this.pendingTransition) {
      let angle=0;
      for(const [n,xyz] of Object.entries(this.targets)) {
        const from=this.transitionFrom[n].setFromEuler(this.euler.set(...this.joints[n].map(v=>v.position)));
        angle=Math.max(angle,from.angleTo(this.q.setFromEuler(this.euler.set(...xyz))));
      }
      this.transitionDuration=clamp(.3+angle*.18,.3,.8);this.transitionAt=this.time;this.pendingTransition=false;
    }
    const blend=ease((this.time-this.transitionAt)/this.transitionDuration);
    for(const [n,xyz] of Object.entries(this.targets)) {
      this.q.setFromEuler(this.euler.set(...xyz));
      if(blend<1){this.q2.copy(this.transitionFrom[n]).slerp(this.q,blend);this.euler.setFromQuaternion(this.q2);xyz[0]=this.euler.x;xyz[1]=this.euler.y;xyz[2]=this.euler.z;}
      const hand=n.endsWith('Hand'),arm=n.includes('Arm');
      const response=(hand?10:n.endsWith('LowerArm')?12:n.endsWith('UpperArm')?10:11)*(n.startsWith('left')?.94:1.02);
      const speed=hand?2.1:arm?2.4:1.2;
      for(let i=0;i<3;i++)spring(this.joints[n][i],xyz[i],response,dt,speed);
      this.bones[n]?.quaternion.setFromEuler(this.euler.set(...this.joints[n].map(v=>v.position)));
    }
    if(reducedMotion){this.handStates.left.openness=0;this.handStates.right.openness=0;}
  }
  updateFingers(dt,reducedMotion) {
    for(const f of this.fingers) {
      const hand=this.handStates[f.side],open=reducedMotion?0:hand.openness;
      // Actual time-delay lines: thumb then index through little, 60ms apart.
      f.history??=[];f.history.push({time:this.time,open});
      const before=this.time-f.index*.06;
      while(f.history.length>2&&f.history[1].time<=before)f.history.shift();
      const delayed=f.history[0].open;
      // AIRI natural relaxed curvature: fingers retain gentle human flex, avoiding flat claw rigidity
      let curl=f.idle*(1-delayed*.42);
      if(hand.pose==='point'&&f.finger!=='Thumb')curl=f.finger==='Index'?.035:f.idle+delayed*.45;
      if(hand.pose==='two'&&f.finger!=='Thumb')curl=['Index','Middle'].includes(f.finger)?.035:f.idle+delayed*.40;
      curl=clamp(curl,0,f.segment===0?.85:.65);
      const splay=(f.finger==='Thumb'?.04:(1.8-f.index)*.008)*delayed*(f.side==='left'?-1:1);
      spring(f.curl,curl,10*(f.side==='left'?.94:1.02),dt,1.8);spring(f.splay,splay,8,dt,.65);
      f.q.setFromAxisAngle(f.axis,f.curl.position);
      if(f.segment===0)f.q.multiply(this.q.setFromAxisAngle(SPLAY_AXIS,f.splay.position));
      f.bone.quaternion.copy(f.q);
    }
  }
  plantFeet() {
    for(const leg of this.legs) {
      const {upper,lower,foot,l1,l2,a,b,c,direction,pole,knee,delta,worldQ,parentQ}=leg;
      upper.getWorldPosition(a);direction.subVectors(leg.anchor,a);
      const distance=clamp(direction.length(),Math.abs(l1-l2)+.00001,l1+l2-.00001);direction.normalize();
      pole.copy(this.forward); // VRM0 authors the forward direction as -Z.
      const root=this.bones.hips;root?.getWorldQuaternion(worldQ);pole.applyQuaternion(worldQ);
      pole.addScaledVector(direction,-pole.dot(direction)).normalize();
      const along=(l1*l1-l2*l2+distance*distance)/(2*distance),height=Math.sqrt(Math.max(0,l1*l1-along*along));
      knee.copy(a).addScaledVector(direction,along).addScaledVector(pole,height);
      lower.getWorldPosition(b);delta.setFromUnitVectors(b.sub(a).normalize(),c.subVectors(knee,a).normalize());
      upper.getWorldQuaternion(worldQ);upper.parent.getWorldQuaternion(parentQ).invert();
      upper.quaternion.copy(parentQ.multiply(delta.multiply(worldQ)));upper.updateWorldMatrix(true,true);
      lower.getWorldPosition(b);foot.getWorldPosition(c);delta.setFromUnitVectors(c.sub(b).normalize(),a.subVectors(leg.anchor,b).normalize());
      lower.getWorldQuaternion(worldQ);lower.parent.getWorldQuaternion(parentQ).invert();
      lower.quaternion.copy(parentQ.multiply(delta.multiply(worldQ)));lower.updateWorldMatrix(true,true);
      foot.parent.getWorldQuaternion(parentQ).invert();foot.quaternion.copy(parentQ.multiply(leg.footQ));
    }
  }
  placeHands(dt,reducedMotion) {
    const chest=this.bones.chest||this.bones.spine;
    if(!chest)return;
    for(const arm of this.arms) {
      const goal=this.armGoals[arm.side];goal.weight+=((reducedMotion?0:goal.target)-goal.weight)*damp(9,dt);
      for(const axis of ['x','y','z'])goal[axis]+=(goal['t'+axis]-goal[axis])*damp(6,dt);
      goal.ny+=((goal.palm==='stop'||goal.palm==='heart'?.06:1)-goal.ny)*damp(6,dt);
      goal.nz+=((goal.palm==='heart'?-1:goal.palm==='stop'?1:.12)-goal.nz)*damp(6,dt);
      const weight=ease(clamp(goal.weight));if(weight<.0001)continue;
      const {upper,lower,hand,l1,l2,a,b,c,target,direction,pole,elbow,delta,worldQ,parentQ,from}=arm;
      chest.getWorldPosition(arm.chest);upper.getWorldPosition(a);
      const side=Math.sign(a.x-arm.chest.x)|| (arm.side==='left'?1:-1);
      target.copy(arm.chest);target.x+=side*goal.x;target.y+=goal.y;target.z+=goal.z;
      direction.subVectors(target,a);
      const distance=clamp(direction.length(),Math.abs(l1-l2)+.003,l1+l2-.025);direction.normalize();
      if(arm.lastDirection&&arm.lastDirection.dot(direction)<-0.2)return;
      arm.lastDirection=direction.clone();
      // Elbow stays naturally close to the ribcage and lower than the hand, pointing down-backwards
      pole.set(side*.20,-.88,-.16);
      const poleOrtho=orthonormalizePole(direction,pole);
      if(poleOrtho)pole.copy(poleOrtho);
      const along=(l1*l1-l2*l2+distance*distance)/(2*distance),height=Math.sqrt(Math.max(0,l1*l1-along*along));
      elbow.copy(a).addScaledVector(direction,along).addScaledVector(pole,height);
      lower.getWorldPosition(b);delta.setFromUnitVectors(b.sub(a).normalize(),c.subVectors(elbow,a).normalize());
      upper.getWorldQuaternion(worldQ);upper.parent.getWorldQuaternion(parentQ).invert();
      from.copy(upper.quaternion);upper.quaternion.copy(from.slerp(parentQ.multiply(delta.multiply(worldQ)),weight));upper.updateWorldMatrix(true,true);
      lower.getWorldPosition(b);hand.getWorldPosition(c);delta.setFromUnitVectors(c.sub(b).normalize(),a.subVectors(target,b).normalize());
      lower.getWorldQuaternion(worldQ);lower.parent.getWorldQuaternion(parentQ).invert();
      from.copy(lower.quaternion);lower.quaternion.copy(from.slerp(parentQ.multiply(delta.multiply(worldQ)),weight));lower.updateWorldMatrix(true,true);
      // Pronation belongs mostly to the forearm, constrained to natural human range
      lower.getWorldPosition(b);hand.getWorldPosition(c);direction.subVectors(c,b).normalize();
      arm.normal.set(0,goal.ny,goal.nz).normalize();
      lower.getWorldQuaternion(worldQ);arm.palm.set(0,-1,0).applyQuaternion(worldQ);
      arm.palm.addScaledVector(direction,-arm.palm.dot(direction)).normalize();
      arm.axisY.copy(arm.normal).addScaledVector(direction,-arm.normal.dot(direction)).normalize();
      arm.axisZ.crossVectors(arm.palm,arm.axisY);
      const twistTarget=clamp(Math.atan2(direction.dot(arm.axisZ),arm.palm.dot(arm.axisY)),-.22,.22);
      spring(goal.twist,twistTarget,7,dt,1.5);
      const twist=goal.twist.position*weight;
      delta.setFromAxisAngle(direction,twist);lower.parent.getWorldQuaternion(parentQ).invert();
      lower.quaternion.copy(parentQ.multiply(delta.multiply(worldQ)));lower.updateWorldMatrix(true,true);
      // Hand naturally extends from forearm following authored gesture Euler targets;
      // never override with inverted coordinate basis to prevent unnatural 180° twists.
    }
  }
  updateFace(dt,{speaking,hasAudio,audioLevel,spectrum,visemes,cautious,empathetic,think,listen,reducedMotion,gazeX,gazeY}) {
    const alpha=damp(7,dt),time=this.time;
    // AIRI Stochastic Poisson Auto-Blink Engine with Double-Blink & Asymmetric Kinetics
    if(time>=this.blinkAt){
      this.blinkStarted=time;
      this.pendingDoubleBlink=this.random()<0.14;
      this.blinkAt=time+this.samplePoissonBlinkInterval(cautious,think);
    }
    if(this.wasThinking&&!think){
      this.blinkStarted=time;
      this.pendingDoubleBlink=false;
      this.blinkAt=time+this.samplePoissonBlinkInterval(cautious,think);
    }
    this.wasThinking=think;
    const age=time-this.blinkStarted;
    const closeDur=0.065,openDur=0.145,totalDur=closeDur+openDur;
    let blink=0;
    if(age>=0&&age<totalDur){
      blink=age<closeDur?ease(age/closeDur):1-ease((age-closeDur)/openDur);
    } else if(this.pendingDoubleBlink&&age>=totalDur+0.08){
      this.doubleBlinkAt=time;
      this.pendingDoubleBlink=false;
    }
    if(this.doubleBlinkAt&&time>=this.doubleBlinkAt){
      const dAge=time-this.doubleBlinkAt;
      if(dAge>=0&&dAge<totalDur){
        blink=Math.max(blink,dAge<closeDur?ease(dAge/closeDur):1-ease((dAge-closeDur)/openDur));
      } else if(dAge>=totalDur){
        this.doubleBlinkAt=0;
      }
    }
    this.setValue('blink',Math.max(0,blink),1);
    const noise=reducedMotion?0:(Math.sin(time*.73+.4)+Math.sin(time*1.13))*.005;
    const happy=cautious?0:think?.018:this.activeGesture==='greeting'?.12:empathetic?.075:this.contextState==='encouraging'?.17:.028;
    const cheekLift=speaking&&hasAudio&&!cautious?clamp((audioLevel-.012)*3.8,0,.55)*.025:0;
    this.setValue('happy',happy+(cautious?0:noise+cheekLift),alpha);
    this.setValue('sad',empathetic?.055+Math.abs(noise)*1.5:0,alpha);
    this.setValue('angry',cautious?.045+Math.abs(noise):think?.015:0,alpha);
    this.setValue('relaxed',(think?.045:listen?.06:.025)+noise*.4,alpha);
    this.setValue(this.surpriseName,this.expression==='surprised'&&!cautious?.06:!cautious&&think?Math.max(0,noise)*.5:0,alpha);
    const browAccent=speaking&&hasAudio?this.audioAccent*.018:0;
    for(const n of this.faceDetails.browUp)this.setValue(n,(empathetic?.035:think?.02:0)+Math.max(0,noise)+browAccent,alpha);
    for(const n of this.faceDetails.browDown)this.setValue(n,(cautious?.04:0)+Math.max(0,-noise),alpha);
    const ex=reducedMotion?0:gazeX*.13+this.saccade.x,ey=reducedMotion?0:gazeY*.09+this.saccade.y;
    if(this.vrm.lookAt){
      // Bone and expression appliers use opposite signs for screen-right/up.
      // The bone applier itself compensates for VRM0's authored faceFront.
      const sign=this.vrm.lookAt.applier?.constructor?.type==='expression'?-1:1;
      this.vrm.lookAt.yaw=sign*ex*180/Math.PI;this.vrm.lookAt.pitch=-ey*180/Math.PI;
      try{this.vrm.lookAt.update(dt);}catch{}
    }
    else for(const [n,v] of Object.entries({lookRight:ex,lookLeft:-ex,lookUp:ey,lookDown:-ey}))this.setValue(n,Math.max(0,v),damp(22,dt));
    // Spectral band ratios diversify vowels only. They do not identify phonemes,
    // especially m/b/p; exact visemes require provider timestamps or alignment.
    const opening=speaking&&hasAudio?clamp((audioLevel-.012)*3.8,0,.55):0;
    for(const n of this.faceDetails.cheeks)this.setValue(n,opening*.10,alpha);
    const low=spectrum?.low??.5,high=spectrum?.high??.15,mid=spectrum?.mid??.35;
    const round=clamp(.10+low*.24,0,.38),wide=clamp(.08+high*.24+mid*.10,0,.32);
    const mouthAlpha=damp(opening>0?24:35,dt);
    const fallback={aa:opening*(1-round-wide*.5),oh:opening*round,ih:opening*wide*.55,ee:opening*wide*.45,ou:0};
    const mouth=speaking&&hasAudio?(visemes||fallback):{};
    for(const name of MOUTH_CHANNELS)this.setValue(name,mouth[name]||0,mouthAlpha);
    this.extraVisemes??=Object.keys(this.vrm.expressionManager?.expressionMap||{}).filter(n=>n.startsWith('viseme_'));
    for(const name of this.extraVisemes)this.setValue(name,mouth[name]||0,mouthAlpha);
  }
  setValue(name,target,alpha) {
    this.values[name]=(this.values[name]??0)+(clamp(target)-(this.values[name]??0))*alpha;
    this.vrm.expressionManager?.setValue(name,this.values[name]);
  }
}
