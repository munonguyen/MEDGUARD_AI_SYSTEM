import assert from 'node:assert/strict';
import {Object3D,Vector3,Quaternion} from 'three';
import {DoctorMotion} from '../src/companion/doctorMotion.js';
import {GESTURE_POOL} from '../src/companion/doctorMotionContext.js';
const seeded=(seed=123)=>()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2**32;};
function fixture(persona='dr_mai') {
 const bones={},values={};
 const vrm={humanoid:{getNormalizedBoneNode:n=>bones[n]??=new Object3D()},expressionManager:{setValue:(n,v)=>values[n]=v},update(){}};
 return {bones,values,motion:new DoctorMotion(vrm,persona,{random:seeded()})};
}
const sample={speaking:false,look:{x:0,y:0}},talking={...sample,speaking:true,hasAudio:true,audioLevel:.15};
const advance=(f,seconds,input=sample)=>{for(let i=0;i<seconds*60;i++)f.motion.update(1/60,input);};
const a=fixture(),rest=a.bones.head.quaternion.clone();
a.motion.setPose('pose_listening');assert.equal(rest.angleTo(a.bones.head.quaternion),0);
a.motion.update(1/60,sample);assert(rest.angleTo(a.bones.head.quaternion)<.01);
const angles=[];for(let i=0;i<420;i++){a.motion.update(1/60,sample);angles.push(a.motion.joints.head[0].position);}
assert(Math.max(...angles)-Math.min(...angles)>.025,'listening contains a damped nod');
advance(a,.15,talking);assert(a.values.aa>.1);
advance(a,.5,{...talking,audioLevel:0});
for(const n of ['aa','oh','ih','ee'])assert(a.values[n]<.001,'all visemes close during silence');
advance(a,.5,{...talking,hasAudio:false});assert(a.values.aa<.001,'no fake speech without audio');
advance(a,1);assert(a.motion.speechWeight<.01);
const one=fixture(),two=fixture();one.motion.setPose('pose_listening');two.motion.setPose('pose_listening');
for(let i=0;i<30;i++)one.motion.update(1/30,{...sample,reducedMotion:true});
for(let i=0;i<120;i++)two.motion.update(1/120,{...sample,reducedMotion:true});
assert(one.bones.rightUpperArm.quaternion.angleTo(two.bones.rightUpperArm.quaternion)<1e-6);
console.log('transitions, listening, silent/offline mouth and reduced motion PASS');
for(const persona of ['dr_tuan','dr_mai']) {
 const f=fixture(persona);f.motion.startUtterance('Xin chào. Đầu tiên hãy ghi lại thông tin. Không tự tăng liều. Bạn có thể chia sẻ thêm không?');
 assert.deepEqual(f.motion.gesturePlan,['greeting','enumerate','caution','invite']);
 const same=fixture(persona);same.motion.startUtterance(f.motion.utteranceText);assert.deepEqual(same.motion.gestureDurations,f.motion.gestureDurations);
 const variants=new Set();let previous='';
 for(let i=0;i<12;i++){
  f.motion.startUtterance('Cơ chế này liên quan đến hoạt động của cơ thể.');const v=f.motion.utterancePlan[0].variant.id;
  assert.notEqual(v,previous,'avoid repeating preceding variant');previous=v;variants.add(v);
 }
 assert(variants.size>=3);
 f.motion.tone='empathetic';f.motion.startUtterance('Không tự tăng liều thuốc.');advance(f,1,talking);
 assert.equal(f.motion.activeGesture,'caution');assert(f.values.happy<.002,'warning overrides friendly face');
 const visual=fixture(persona);visual.motion.startUtterance('Tôi đã ghi nhận thông tin.');visual.motion.setPose('pose_acknowledge');
 const r=visual.bones.rightLowerArm.quaternion.clone(),l=visual.bones.leftLowerArm.quaternion.clone();advance(visual,1.7);
 assert(Math.max(r.angleTo(visual.bones.rightLowerArm.quaternion),l.angleTo(visual.bones.leftLowerArm.quaternion))>.1);
 assert.equal(visual.values.aa,0);advance(visual,5);assert(visual.motion.speechWeight<.01);
}
assert(Object.values(GESTURE_POOL).every(p=>p.length>=3));
console.log('both personas: semantic precedence, anti-repetition and silent acknowledgment PASS');
const aligned=fixture();aligned.motion.startUtterance('Tôi sẽ giải thích cơ chế. Không tự tăng liều thuốc.');aligned.motion.beginSpeechSegment(aligned.motion.utteranceText);
aligned.motion.update(.1,{...talking,playbackTime:.8,playbackDuration:10});assert.equal(aligned.motion.activeGesture,'explain');
aligned.motion.update(.1,{...talking,playbackTime:8,playbackDuration:10});assert.equal(aligned.motion.activeGesture,'caution');
const before=aligned.motion.speechTime;aligned.motion.update(.1,sample);assert.equal(aligned.motion.speechTime,before);
aligned.motion.beginSpeechSegment('Bạn có thể cho biết thêm không?');aligned.motion.update(.1,{...talking,playbackTime:.2,playbackDuration:4});assert.equal(aligned.motion.activeGesture,'invite');assert(aligned.motion.speechTime>before);
const low=fixture(),high=fixture();advance(low,.5,{...talking,spectrum:{low:.9,mid:.1,high:0}});advance(high,.5,{...talking,spectrum:{low:.05,mid:.15,high:.8}});
assert(low.values.oh>high.values.oh&&high.values.ee>low.values.ee);
const gaze=fixture();for(let i=0;i<3;i++)gaze.motion.update(1/60,{...sample,look:{x:1,y:.5}});
assert(gaze.motion.eye.x>gaze.motion.headLook.x*2,'eyes lead head');
gaze.motion.setContext('Tôi lo lắng về tình trạng này.');gaze.motion.setPose('pose_thinking');advance(gaze,2,{...sample,look:{x:1,y:0}});assert(gaze.motion.eye.x<.75);
gaze.motion.setPose('pose_idle');advance(gaze,.1);assert(gaze.values.blink>0);
console.log('media-clock intent, queue continuity, spectrum and eye/head coordination PASS');
const interrupted=fixture();interrupted.motion.startUtterance('Xin chào bạn.');let maxWristStep=0,previousWrist=interrupted.bones.rightHand.quaternion.clone();
for(let i=0;i<900;i++){
 if(i===85)interrupted.motion.setPose('pose_listening');if(i===145)interrupted.motion.setPose('pose_wave');if(i===220)interrupted.motion.setPose('pose_thinking');if(i===340)interrupted.motion.setPose('pose_idle');
 interrupted.motion.update(1/60,{...sample,speaking:i<85,look:{x:Math.sin(i*.02),y:.2}});
 const q=interrupted.bones.rightHand.quaternion;maxWristStep=Math.max(maxWristStep,previousWrist.angleTo(q));previousWrist.copy(q);
 for(const axes of Object.values(interrupted.motion.joints))for(const v of axes){assert(Number.isFinite(v.position)&&Number.isFinite(v.velocity));assert(Math.abs(v.velocity)<3);}
 for(const f of interrupted.motion.fingers){assert(Number.isFinite(f.curl.position));assert(f.curl.position>=0&&f.curl.position<.9);}
}
assert(maxWristStep<.06);assert(interrupted.motion.transitionDuration>=.3&&interrupted.motion.transitionDuration<=.8);
assert(interrupted.bones.leftShoulder.quaternion.angleTo(rest)>0);
assert(interrupted.bones.leftLittleProximal.quaternion.angleTo(rest)>interrupted.bones.leftIndexProximal.quaternion.angleTo(rest));
const partial=new DoctorMotion({humanoid:{getNormalizedBoneNode:n=>n==='head'?new Object3D():null},update(){}},'custom',{random:seeded()});partial.update(1/60,talking);assert.equal(partial.fingers.length,0);
console.log('interruption limits, adaptive transitions, fingers and partial rigs PASS');
const rig={},root=new Object3D();rig.hips=new Object3D();rig.hips.position.y=1;root.add(rig.hips);
for(const side of ['left','right']){
 let parent=rig.hips;
 for(const [part,pos] of [['UpperLeg',[side==='left'?.075:-.075,0,0]],['LowerLeg',[0,-.42,0]],['Foot',[0,-.43,0]]]){
  const b=rig[side+part]=new Object3D();b.position.set(...pos);parent.add(b);parent=b;
 }
}
const legs=new DoctorMotion({humanoid:{getNormalizedBoneNode:n=>rig[n]||null},update(){}},'custom',{random:seeded()});let drift=0;const shifts=new Set();
for(let i=0;i<60*70;i++){
 legs.update(1/60,sample);shifts.add(Math.sign(legs.weight.position));
 for(const l of legs.legs){drift=Math.max(drift,l.foot.getWorldPosition(new Vector3()).distanceTo(l.anchor));assert(Math.abs(l.foot.getWorldQuaternion(new Quaternion()).dot(l.footQ))>.9999);}
}
assert(shifts.has(-1)&&shifts.has(1));assert(drift<.001);
console.log('full-body weight transfer and foot planting PASS',{maxDriftMm:Math.round(drift*100000)/100});
const critical=fixture();critical.motion.setContext('Tôi lo lắng.',{severity:'CRITICAL'});critical.motion.startUtterance('Tôi hiểu bạn đang lo lắng.');advance(critical,1,talking);assert.equal(critical.motion.currentCue.emotion,'cautious');assert(critical.values.happy<.002);
console.log('critical server metadata overrides reassuring smile PASS');
