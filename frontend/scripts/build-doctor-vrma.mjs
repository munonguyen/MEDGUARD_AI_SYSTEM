// Reproducible original torso/clavicle clips. These are authored keyframes,
// not motion capture. Arms, hips, gaze and face intentionally have no tracks.
import {writeFile,mkdir} from 'node:fs/promises';
import {Quaternion,Euler} from 'three';
const bones=['hips','spine','chest','upperChest','leftShoulder','rightShoulder'];
const nodes=bones.map(name=>({name}));
nodes[0].translation=[0,1,0];nodes[0].children=[1];nodes[1].children=[2];nodes[2].children=[3];nodes[3].children=[4,5];
const gltf={asset:{version:'2.0',generator:'MedGuard authored gesture generator'},scene:0,scenes:[{nodes:[0]}],nodes,
 extensionsUsed:['VRMC_vrm_animation'],extensions:{VRMC_vrm_animation:{specVersion:'1.0',humanoid:{humanBones:Object.fromEntries(bones.map((name,node)=>[name,{node}]))}}},bufferViews:[],accessors:[],animations:[]};
const buffers=[];let offset=0;
function accessor(values,type){const b=Buffer.from(new Float32Array(values).buffer),view=gltf.bufferViews.length;gltf.bufferViews.push({buffer:0,byteOffset:offset,byteLength:b.length});buffers.push(b);offset+=b.length;const size=type==='SCALAR'?1:4;const a={bufferView:view,componentType:5126,count:values.length/size,type};if(type==='SCALAR'){a.min=[Math.min(...values)];a.max=[Math.max(...values)];}gltf.accessors.push(a);return gltf.accessors.length-1;}
const times=[0,.65,1.05,1.5,2.25,3.4],input=accessor(times,'SCALAR');
const styles={greeting:[-.020,.035,.018],explain:[-.012,.045,.012],invite:[-.028,.025,.015],reassure:[-.040,.014,.008],caution:[.008,.014,.004],enumerate:[-.010,.025,.009],compare:[-.012,-.045,.013],guide:[-.020,.032,.010]};
for(const [name,[lean,yaw,roll]] of Object.entries(styles)){
 const animation={name,samplers:[],channels:[]};
 for(let node=1;node<bones.length;node++){
  const values=times.flatMap((t,i)=>{
   const strength=[0,.35,1,.95,.55,0][i],secondary=[0,.12,.75,1,.45,0][i];
   const e=node===1?[lean*.4*strength,-yaw*.3*strength,roll*.45*strength]:node===2?[lean*strength,yaw*strength,-roll*.4*strength]:node===3?[lean*.3*secondary,yaw*.25*secondary,roll*.3*secondary]:[0,(node===4?1:-1)*yaw*.25*secondary,(node===4?1:-1)*.012*secondary];
   return new Quaternion().setFromEuler(new Euler(...e)).toArray();
  });
  const output=accessor(values,'VEC4'),sampler=animation.samplers.length;
  animation.samplers.push({input,output,interpolation:'LINEAR'});animation.channels.push({sampler,target:{node,path:'rotation'}});
 }gltf.animations.push(animation);
}
gltf.buffers=[{byteLength:offset,uri:'data:application/octet-stream;base64,'+Buffer.concat(buffers).toString('base64')}];
const dir=new URL('../public/animations/',import.meta.url);await mkdir(dir,{recursive:true});await writeFile(new URL('doctor-gestures.vrma',dir),JSON.stringify(gltf));
console.log('Generated 8 original VRMA clips (torso/clavicle mask)');
