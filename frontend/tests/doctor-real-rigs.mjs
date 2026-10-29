// Headless skeleton/clip verification using the original meshes and rigs.
// Textures are omitted only in this test; this is NOT visual/GPU validation.
import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {VRMLoaderPlugin,VRMUtils,VRMMetaLoaderPlugin} from '@pixiv/three-vrm';
import {Vector3} from 'three';
import {DoctorMotion} from '../src/companion/doctorMotion.js';
import {DoctorAnimationLayer} from '../src/companion/doctorAnimationLayer.js';
import {GESTURE_POOL} from '../src/companion/doctorMotionContext.js';
globalThis.ProgressEvent??=class {constructor(type,options){this.type=type;Object.assign(this,options);}};
const loader=new GLTFLoader();loader.register(p=>new VRMLoaderPlugin(p,{metaPlugin:new VRMMetaLoaderPlugin(p,{needThumbnailImage:false})}));
async function loadRig(file){
 const bytes=await readFile(file),jsonLength=bytes.readUInt32LE(12),json=JSON.parse(bytes.subarray(20,20+jsonLength).toString());
 for(const mesh of json.meshes||[])for(const primitive of mesh.primitives)delete primitive.material;
 json.materials=[];json.textures=[];json.images=[];
 if(json.extensions?.VRM){json.extensions.VRM.materialProperties=[];delete json.extensions.VRM.meta.texture;}
 const binOffset=20+jsonLength,binLength=bytes.readUInt32LE(binOffset);
 json.buffers=[{byteLength:binLength,uri:'data:application/octet-stream;base64,'+bytes.subarray(binOffset+8,binOffset+8+binLength).toString('base64')}];
 const gltf=await loader.parseAsync(JSON.stringify(json),'');const vrm=gltf.userData.vrm;
 if(vrm.meta.metaVersion==='0')VRMUtils.rotateVRM0(vrm);
 vrm.springBoneManager=null;vrm.update(0);return vrm;
}
const asset=await readFile(new URL('../public/animations/doctor-gestures.vrma',import.meta.url),'utf8');
const report=[];
for(const [persona,file] of [['dr_tuan','DoctorTuan.vrm'],['dr_mai','DoctorMai.vrm'],['custom','VRM1_Sample.vrm']]){
 const vrm=await loadRig(new URL('../public/models/'+file,import.meta.url));let seed=123;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2**32;};
 const m=new DoctorMotion(vrm,persona,{random});m.animationLayer=new DoctorAnimationLayer(vrm);
 await m.animationLayer.load('data:model/gltf+json;base64,'+Buffer.from(asset).toString('base64'));
 assert.equal(Object.keys(m.animationLayer.actions).length,8);
 // Propagate the constructor's rest pose before measuring frame-to-frame steps.
 vrm.update(0);
 const armNames=['rightUpperArm','rightLowerArm','rightHand','leftUpperArm','leftLowerArm','leftHand'];
 const previous=armNames.map(n=>vrm.humanoid.getRawBoneNode(n).quaternion.clone());
 const foot=n=>vrm.humanoid.getRawBoneNode(n).getWorldPosition(new Vector3());
 const anchors=['leftFoot','rightFoot'].map(foot);let drift=0,step=0,elapsed=[];const poses=[];
 for(const [intent,pool] of Object.entries(GESTURE_POOL))for(const variant of pool){
  m.setContext('',{severity:intent==='caution'?'HIGH':''});m.startUtterance('Kiểm tra cử chỉ.');m.setPose('pose_idle');
  m.utterancePlan=[{text:'Kiểm tra cử chỉ.',...m.planner.select(intent,'clinical'),variant,side:'right',duration:4.5}];
  for(let i=0;i<270;i++){
   const start=performance.now();m.update(1/60,{speaking:true,hasAudio:true,audioLevel:i%100<80?.1:0,look:{x:.2,y:.1}});if(i>10)elapsed.push(performance.now()-start);
   armNames.forEach((n,k)=>{const q=vrm.humanoid.getRawBoneNode(n).quaternion;step=Math.max(step,previous[k].angleTo(q));previous[k].copy(q);assert(q.toArray().every(Number.isFinite));});
   ['leftFoot','rightFoot'].forEach((n,k)=>drift=Math.max(drift,foot(n).distanceTo(anchors[k])));
   if(intent==='greeting'&&i===100){const pos=n=>vrm.humanoid.getRawBoneNode(n).getWorldPosition(new Vector3());const s=pos('rightUpperArm'),e=pos('rightLowerArm'),w=pos('rightHand');poses.push({variant:variant.id,shoulder:s.toArray(),elbow:e.toArray(),wrist:w.toArray()});assert(s.y-e.y>.12,'upper arm stays down');assert(w.y-e.y>.04,'elbow stays below hand');assert(Math.abs(e.x-s.x)<.15,'elbow close to torso');}
  }
 }
 m.setPose('pose_listening');for(let i=0;i<180;i++)m.update(1/60,{speaking:false});
 assert(drift<.003);assert(step<.10,`arm step ${step}`);assert.equal(m.fingers.length,30);
 elapsed.sort((a,b)=>a-b);report.push({persona,variants:24,clips:8,fingerBones:m.fingers.length,maxFootDriftMm:drift*1000,maxArmStepRad:step,medianMotionMs:elapsed[Math.floor(elapsed.length*.5)],p95MotionMs:elapsed[Math.floor(elapsed.length*.95)],expressions:Object.keys(vrm.expressionManager.expressionMap),greetingPoses:poses});
 console.log(report.at(-1));m.animationLayer.destroy();VRMUtils.deepDispose(vrm.scene);
}
const dir=new URL('../../.artifacts/open-motion/',import.meta.url);await mkdir(dir,{recursive:true});await writeFile(new URL('rig-report.json',dir),JSON.stringify(report,null,2));
console.log('both doctor VRM0 rigs and VRM1: clips, 24 variants, greeting geometry, bounded motion and planted feet PASS');
