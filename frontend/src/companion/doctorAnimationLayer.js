import {AnimationMixer,Quaternion} from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {VRMAnimationLoaderPlugin,createVRMAnimationClip} from '@pixiv/three-vrm-animation';

// Explicit ownership: VRMA adds torso/clavicle deltas only. Arms/fingers remain
// in DoctorMotion/IK; eyes and mouth remain in their dedicated controllers.
const MASK=['spine','chest','upperChest','leftShoulder','rightShoulder'];
export class DoctorAnimationLayer {
 constructor(vrm){this.vrm=vrm;this.mixer=new AnimationMixer(vrm.scene);this.actions={};this.samples=MASK.map(name=>({name,bone:vrm.humanoid.getNormalizedBoneNode(name),saved:new Quaternion(),delta:new Quaternion(),current:new Quaternion()})).filter(x=>x.bone);this.weight=0;this.identity=new Quaternion();}
 async load(url){
  const loader=new GLTFLoader();loader.register(p=>new VRMAnimationLoaderPlugin(p));
  const gltf=await loader.loadAsync(url);if(this.destroyed)return;
  const names=gltf.parser.json.animations.map(a=>a.name);
  (gltf.userData.vrmAnimations||[]).forEach((animation,i)=>{
   const clip=createVRMAnimationClip(animation,this.vrm);
   const allowed=new Set(this.samples.map(s=>s.bone.name+'.quaternion'));
   clip.tracks=clip.tracks.filter(t=>allowed.has(t.name));
   const action=this.mixer.clipAction(clip);action.clampWhenFinished=true;action.play();action.enabled=false;
   action.mask=new Set(clip.tracks.map(t=>t.name));
   this.actions[names[i]]=action;
  });this.loaded=true;
 }
 apply(dt,{cue,phase,duration,active,reducedMotion}){
  if(!this.loaded||this.destroyed)return;
  const action=this.actions[cue?.intent];
  const target=active&&!reducedMotion&&action ? .35 : 0;
  this.weight+=(target-this.weight)*(1-Math.exp(-dt*8));
  for(const sample of this.samples)sample.saved.copy(sample.bone.quaternion);
  for(const a of Object.values(this.actions))a.enabled=a===action;
  if(action){this.mixer.setTime(Math.min(action.getClip().duration-.0001,Math.max(0,phase/duration)*action.getClip().duration));}
  for(const s of this.samples){
   s.delta.copy(action&&(!action.mask||action.mask.has(s.bone.name+'.quaternion'))?s.bone.quaternion:this.identity);
   if(cue?.side==='left'){s.delta.y*=-1;s.delta.z*=-1;}
   s.bone.quaternion.copy(s.saved);
   s.current.rotateTowards(s.delta,dt*.45);
   s.delta.identity().slerp(s.current,this.weight);
   s.bone.quaternion.multiply(s.delta);
  }
 }
 destroy(){this.destroyed=true;this.mixer.stopAllAction();this.mixer.uncacheRoot(this.vrm.scene);this.actions={};}
}
