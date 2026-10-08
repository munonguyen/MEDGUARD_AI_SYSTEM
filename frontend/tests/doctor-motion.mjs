import assert from 'node:assert/strict';
import { Object3D } from 'three';
import { DoctorMotion } from '../src/companion/doctorMotion.js';
function fixture() {
  const bones={};const values={};
  const vrm={humanoid:{getNormalizedBoneNode:n=>bones[n]??=(new Object3D())},expressionManager:{setValue:(n,v)=>values[n]=v},update:()=>{}};
  return {bones,values,motion:new DoctorMotion(vrm,'dr_mai')};
}
const sample={speaking:false,look:{x:0,y:0}};
const a=fixture();const rest=a.bones.head.quaternion.clone();
a.motion.setPose('pose_listening');assert.equal(rest.angleTo(a.bones.head.quaternion),0,'pose switches must not snap');
a.motion.update(1/60,sample);assert.ok(rest.angleTo(a.bones.head.quaternion)<.01);
for(let i=0;i<120;i++)a.motion.update(1/60,sample);
assert.ok(rest.angleTo(a.bones.head.quaternion)>.02);
a.motion.update(1/30,{...sample,speaking:true,hasAudio:true,audioLevel:.15});
assert.ok(a.values.aa>.1,'audible speech opens the mouth');
for(let i=0;i<30;i++)a.motion.update(1/60,{...sample,speaking:true,hasAudio:true,audioLevel:0});
assert.ok(a.values.aa<.001,'silence closes the mouth');
for(let i=0;i<60;i++)a.motion.update(1/60,sample);
assert.ok(a.motion.speechWeight<.01,'gestures settle after speech ends');
const one=fixture(),two=fixture();one.motion.setPose('pose_listening');two.motion.setPose('pose_listening');
for(let i=0;i<30;i++)one.motion.update(1/30,{...sample,reducedMotion:true});
for(let i=0;i<120;i++)two.motion.update(1/120,{...sample,reducedMotion:true});
assert.ok(one.bones.rightUpperArm.quaternion.angleTo(two.bones.rightUpperArm.quaternion)<1e-6);
console.log('doctor motion: transitions, silence, settling and frame-rate independence PASS');

for(const persona of ['dr_tuan','dr_mai']) {
 const model=fixture();model.motion.persona=persona;
 model.motion.startUtterance('Xin chào bạn. Bạn cần hỗ trợ gì?');
 const used=new Set(),maxStep={value:0};let previous=model.bones.head.quaternion.clone();
 for(let i=0;i<60*20;i++){
  model.motion.update(1/60,{...sample,speaking:true,hasAudio:true,audioLevel:.12});
  used.add(model.motion.activeGesture);
  maxStep.value=Math.max(maxStep.value,previous.angleTo(model.bones.head.quaternion));
  previous.copy(model.bones.head.quaternion);
 }
 assert(used.has('greeting')&&used.has('explain')&&used.has('invite'));
 assert(maxStep.value<.02,'head/body transitions remain damped');
 model.motion.startUtterance('Khó thở tăng lên cần gọi 115.');
 model.motion.update(1/60,{...sample,speaking:true});assert.equal(model.motion.activeGesture,'caution');
}
console.log('both personas: greeting, invitation, explanation and caution plans PASS');

const visual=fixture();visual.motion.startUtterance('Tôi đã ghi nhận thông tin.');visual.motion.setPose('pose_acknowledge');
const arm=visual.bones.rightLowerArm.quaternion.clone();
const leftArm=visual.bones.leftLowerArm.quaternion.clone();
for(let i=0;i<90;i++)visual.motion.update(1/60,sample);
assert(Math.max(arm.angleTo(visual.bones.rightLowerArm.quaternion),leftArm.angleTo(visual.bones.leftLowerArm.quaternion))>.1,'written reply reacts even without audio');
assert.equal(visual.values.aa,0,'visual acknowledgment never pretends to have audible speech');
for(let i=0;i<300;i++)visual.motion.update(1/60,sample);
assert(visual.motion.speechWeight<.01,'visual acknowledgment settles on its own');
console.log('written reply gestures independently of TTS, mouth stays closed PASS');

const continuous=fixture();continuous.motion.startUtterance('Xin chào. Tôi sẽ giải thích các bước.');
for(let i=0;i<180;i++)continuous.motion.update(1/60,{...sample,speaking:true});
const age=continuous.motion.speechTime;
continuous.motion.update(.05,sample);
assert.equal(continuous.motion.speechTime,age,'audio gap preserves the utterance timeline');
continuous.motion.update(.1,{...sample,speaking:true});
assert(continuous.motion.speechTime>age+.09,'low frame rates do not slow the speech clock');
const expressive=fixture();expressive.motion.startUtterance('Tôi sẽ giải thích.');
const actions=new Set();
for(let i=0;i<1800;i++){expressive.motion.update(1/60,{...sample,speaking:true,look:{x:.8,y:.4}});actions.add(expressive.motion.activeGesture);}
assert(actions.has('present')&&actions.has('enumerate'));
assert(expressive.bones.neck.quaternion.angleTo(rest)>.02,'neck follows gaze with head');
assert(expressive.values.lookRight>0&&expressive.values.lookUp>0);
console.log('continuous speech clock, multi-joint gestures and facial gaze PASS');

// Rapid stop / listen / greet transitions must retain finite bounded velocity.
const interrupted=fixture();interrupted.motion.startUtterance('Xin chào bạn.');
let maxWristStep=0, previousWrist=interrupted.bones.rightHand.quaternion.clone();
for(let i=0;i<900;i++){
 if(i===85)interrupted.motion.setPose('pose_listening');
 if(i===145)interrupted.motion.setPose('pose_wave');
 if(i===220)interrupted.motion.setPose('pose_thinking');
 if(i===340)interrupted.motion.setPose('pose_idle');
 interrupted.motion.update(1/60,{...sample,speaking:i<85,look:{x:Math.sin(i*.02),y:.2}});
 const q=interrupted.bones.rightHand.quaternion;
 maxWristStep=Math.max(maxWristStep,previousWrist.angleTo(q));previousWrist.copy(q);
 for(const axes of Object.values(interrupted.motion.joints))for(const axis of axes){assert(Number.isFinite(axis.position)&&Number.isFinite(axis.velocity));assert(Math.abs(axis.velocity)<8,'joint speed stays bounded during interruptions');}
}
assert(maxWristStep<.06,'wrist does not snap during interruption');
const shoulders=fixture();
for(let i=0;i<120;i++)shoulders.motion.update(1/60,sample);
assert(shoulders.bones.leftShoulder.quaternion.angleTo(rest)>0,'idle breathing includes shoulders');
console.log('spring transition continuity, bounded joints and idle shoulder motion PASS');

const semantic=fixture();semantic.motion.startUtterance('Xin chào. Đầu tiên hãy ghi lại thông tin. Không tự tăng liều. Bạn có thể chia sẻ thêm không?');
assert.deepEqual(semantic.motion.gesturePlan.slice(0,4),['greeting','enumerate','caution','invite']);
const same=fixture();same.motion.startUtterance('Xin chào. Đầu tiên hãy ghi lại thông tin. Không tự tăng liều. Bạn có thể chia sẻ thêm không?');
assert.deepEqual(same.motion.gestureDurations,semantic.motion.gestureDurations,'variation is stable, never random per frame');
console.log('sentence intent drives distinct greeting, explanation, warning and invitation gestures PASS');
