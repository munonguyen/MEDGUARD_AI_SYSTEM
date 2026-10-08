import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
import {spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
const root=new URL('../../',import.meta.url).pathname,port=5293;
const dir=root+'.artifacts/holistic-motion';await mkdir(dir,{recursive:true});
const server=spawn('npm',['run','dev','--','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:new URL('../',import.meta.url),stdio:'pipe',detached:true});
await new Promise((resolve,reject)=>{server.stdout.on('data',d=>{if(d.toString().includes('Local:'))resolve()});server.on('exit',c=>reject(Error('Vite '+c)));setTimeout(()=>reject(Error('Vite startup timeout')),15000).unref();});
let browser;
try {
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/v1/**',r=>r.fulfill({json:{}}));
 await page.goto(`http://127.0.0.1:${port}/static/?view=companion`);
 await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded);
 const report=[];
 for(const persona of ['dr_tuan','dr_mai']) {
  if(persona==='dr_mai'){await page.getByRole('button',{name:'BS. Thanh Mai',exact:true}).click();await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded&&window.__companionEngine.options.persona==='dr_mai');}
  // Pause RAF so sampling has a reproducible simulation clock, using actual
  // loaded humanoids, morphs and garment meshes; no fake bone fixture here.
  await page.evaluate(()=>{const e=window.__companionEngine;cancelAnimationFrame(e.rafId);e.currentVrm.update(0);e.setCameraPreset('full');});
  const result=await page.evaluate(async()=>{
   const e=window.__companionEngine,m=e.motion,h=e.currentVrm.humanoid;
   const {GESTURE_POOL}=await import('/static/src/companion/doctorMotionContext.js');
   const rawPosition=n=>{const b=h.getRawBoneNode(n);b.updateWorldMatrix(true,false);return [b.matrixWorld.elements[12],b.matrixWorld.elements[13],b.matrixWorld.elements[14]];};
   const footAnchors=['leftFoot','rightFoot'].map(rawPosition);
   let maxFootDrift=0,minBend=1,maxHeadStep=0,minFingerAngle=10,maxArmStep=0;
   const armNames=['rightUpperArm','rightLowerArm','rightHand','leftUpperArm','leftLowerArm','leftHand'];
   const previousArms=armNames.map(n=>h.getRawBoneNode(n).quaternion.clone());
   const previous=h.getRawBoneNode('head').quaternion.clone(),used=[],poses=[];
   for(const [intent,pool] of Object.entries(GESTURE_POOL))for(const variant of pool) {
    m.setContext('',{severity:intent==='caution'?'HIGH':''});
    m.startUtterance('Kiểm tra cử chỉ.');
    m.utterancePlan=[{text:'Kiểm tra cử chỉ.',...m.planner.select(intent,intent==='caution'?'cautious':intent==='reassure'?'empathetic':'clinical'),variant,side:'right',duration:4.5}];
    m.setPose('pose_idle');
    for(let i=0;i<270;i++) {
     m.update(1/60,{speaking:true,look:{x:.3,y:.1},hasAudio:true,audioLevel:i%110<85?.1:0});
     const head=h.getRawBoneNode('head');maxHeadStep=Math.max(maxHeadStep,previous.angleTo(head.quaternion));previous.copy(head.quaternion);
     armNames.forEach((n,k)=>{const q=h.getRawBoneNode(n).quaternion;maxArmStep=Math.max(maxArmStep,previousArms[k].angleTo(q));previousArms[k].copy(q);});
     const feet=['leftFoot','rightFoot'].map(rawPosition);
     feet.forEach((p,k)=>{maxFootDrift=Math.max(maxFootDrift,Math.hypot(...p.map((v,j)=>v-footAnchors[k][j])));});
     if(i===100){const s=rawPosition('rightUpperArm'),a=rawPosition('rightLowerArm'),w=rawPosition('rightHand'),u=a.map((v,j)=>v-s[j]),v=w.map((x,j)=>x-a[j]);minBend=Math.min(minBend,u.reduce((sum,x,j)=>sum+x*v[j],0)/(Math.hypot(...u)*Math.hypot(...v)));poses.push({variant:variant.id,shoulder:s,elbow:a,wrist:w,chest:rawPosition('chest')});}
     for(const f of m.fingers)if(!Number.isFinite(f.bone.quaternion.w))throw Error('Invalid finger quaternion');
    }
    used.push(variant.id);
   }
   // Isolate eye yaw from head yaw on the real rig, preserving VRM0 mapping.
   const eye=h.getRawBoneNode('leftEye'),head=h.getRawBoneNode('head');
   const direction=()=>{head.updateWorldMatrix(true,true);return {eye:Array.from(eye.matrixWorld.elements).slice(8,11),head:Array.from(head.matrixWorld.elements).slice(8,11)};};
   for(let i=0;i<180;i++)m.update(1/60,{speaking:false,look:{x:0,y:0}});const neutral=direction();
   for(let i=0;i<180;i++)m.update(1/60,{speaking:false,look:{x:1,y:0}});const right=direction();
   for(let i=0;i<180;i++)m.update(1/60,{speaking:false,look:{x:0,y:1}});const up=direction();
   minFingerAngle=Math.min(...m.fingers.filter(f=>f.finger==='Little'&&f.segment===0).map(f=>f.curl.position));
   // Interrupt a held gesture, switch to listening, then warn and stop again.
   armNames.forEach((n,k)=>previousArms[k].copy(h.getRawBoneNode(n).quaternion));
   for(let i=0;i<360;i++) {
    if(i===0){m.startUtterance('Tôi hiểu bạn đang lo lắng.');m.setPose('pose_idle');}
    if(i===90)m.setPose('pose_listening');
    if(i===150){m.startUtterance('Không tự tăng liều thuốc.');m.setPose('pose_idle');}
    if(i===225)m.setPose('pose_thinking');
    m.update(1/60,{speaking:i<90||i>=150&&i<225,look:{x:0,y:0},hasAudio:true,audioLevel:.1});
    armNames.forEach((n,k)=>{const q=h.getRawBoneNode(n).quaternion;maxArmStep=Math.max(maxArmStep,previousArms[k].angleTo(q));previousArms[k].copy(q);});
   }
   return {persona:e.options.persona,used,maxFootDrift,minBend,maxHeadStep,maxArmStep,fingerBones:m.fingers.length,legs:m.legs.length,minFingerAngle,
    poses,normalizedRightForearm:Array.from(h.getNormalizedBoneNode('rightLowerArm').position.toArray()),
    eyes:{neutral,right,up},expressions:Object.keys(e.currentVrm.expressionManager.expressionMap)};
  });
  report.push(result);console.log(result.persona,{variants:result.used.length,fingers:result.fingerBones,footDriftMm:result.maxFootDrift*1000,maxArmStep:result.maxArmStep,maxHeadStep:result.maxHeadStep});
  assert.equal(result.used.length,24);assert.equal(new Set(result.used).size,24);
  assert.equal(result.fingerBones,30);assert.equal(result.legs,2);
  assert(result.maxFootDrift<.003,'real rig feet remain planted within 3mm');
  assert(result.maxHeadStep<.025);assert(result.minBend<.7);
  assert(result.maxArmStep<.10,'real arms/wrists stay continuous through interruption');
  const sign=Math.sign(result.eyes.neutral.head[2]);
  assert((result.eyes.right.eye[0]-result.eyes.right.head[0])*sign>.004,'eyes look right with the head');
  assert((result.eyes.up.eye[1]-result.eyes.up.head[1])*sign>.004,'eyes look up with the head');
  for(const [name,text,context] of [['greeting','Xin chào bạn.','clinical'],['explain','Tôi sẽ giải thích cơ chế.','clinical'],['reassure','Tôi hiểu bạn đang lo lắng.','empathetic'],['caution','Không tự tăng liều thuốc.','cautious'],['invite','Bạn có thể chia sẻ thêm không?','clinical'],['compare','Hai nhóm này khác nhau.','clinical']]){
   const png=await page.evaluate(({text,context})=>{const e=window.__companionEngine,m=e.motion;m.setContext('',{severity:context==='cautious'?'HIGH':''});m.tone=context;m.startUtterance(text);m.setPose('pose_idle');e.setCameraPreset('waist');for(let i=0;i<105;i++)m.update(1/60,{speaking:true,look:{x:0,y:0},hasAudio:true,audioLevel:.1});e.renderer.render(e.scene,e.camera);return e.canvas.toDataURL().split(',')[1];},{text,context});
   await writeFile(`${dir}/${persona}-${name}.png`,Buffer.from(png,'base64'));
  }
 }
 await page.evaluate(()=>window.__companionEngine.loadModel('/static/models/VRM1_Sample.vrm'));
 await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded&&window.__companionEngine.currentVrm.meta.metaVersion==='1');
 const modern=await page.evaluate(()=>{const e=window.__companionEngine,m=e.motion,h=e.currentVrm.humanoid;cancelAnimationFrame(e.rafId);h.resetNormalizedPose();e.currentVrm.update(0);const head=h.getRawBoneNode('head'),localForward=m.forward.clone().applyQuaternion(head.getWorldQuaternion(m.q.clone()).invert());m.setPose('pose_idle');for(let i=0;i<180;i++)m.update(1/60,{speaking:false,look:{x:1,y:1}});const pos=n=>{const b=h.getRawBoneNode(n);b.updateWorldMatrix(true,false);return b.matrixWorld.elements[13];};return {modern:m.modernAxes,wrist:pos('rightHand'),shoulder:pos('rightUpperArm'),head:localForward.applyQuaternion(head.getWorldQuaternion(m.q.clone())).toArray()};});
 assert(modern.modern&&modern.wrist<modern.shoulder-.15);assert(modern.head[0]>0&&modern.head[1]>0,'VRM1 also looks right/up');
 console.log('VRM1 axes and optional-rig compatibility PASS',modern);
 await writeFile(dir+'/rig-report.json',JSON.stringify(report,null,2));assert.deepEqual(errors,[]);
 console.log('24 variants on BOTH real VRMs, fingers, head limits and feet PASS');
}finally{await browser?.close();process.kill(-server.pid,'SIGTERM');}
