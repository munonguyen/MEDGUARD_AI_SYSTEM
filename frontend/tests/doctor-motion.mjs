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
