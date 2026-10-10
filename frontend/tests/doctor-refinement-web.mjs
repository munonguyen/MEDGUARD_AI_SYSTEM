import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
import {spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
const port=Number(process.env.MEDGUARD_TEST_PORT||5290);
const server=spawn('npm',['run','dev','--','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:new URL('../',import.meta.url),stdio:'pipe',detached:true});
await new Promise((resolve,reject)=>{server.stdout.on('data',d=>{if(d.toString().includes('Local:'))resolve()});server.on('exit',c=>reject(Error(`Vite exited ${c}`)));setTimeout(()=>reject(Error('Vite startup timed out')),15000).unref();});
const artifactDir=new URL('../../.artifacts/doctor-refinement/',import.meta.url);await mkdir(artifactDir,{recursive:true});
// Two audible segments separated by silence exercise real Web Audio analysis.
const sampleRate=16000,seconds=3.2,n=Math.floor(seconds*sampleRate),wav=Buffer.alloc(44+n*2);
wav.write('RIFF',0);wav.writeUInt32LE(36+n*2,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(sampleRate,24);wav.writeUInt32LE(sampleRate*2,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(n*2,40);
for(let i=0;i<n;i++){const t=i/sampleRate;const level=t<.9||t>2.1?.14:0;wav.writeInt16LE(Math.round(Math.sin(t*2*Math.PI*220)*level*32767),44+i*2);}
let browser;
try{
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{
  class Recognition {
   start(){window.testRecognition=this;queueMicrotask(()=>this.onstart?.());}
   abort(){this.onend?.();}
   stop(){this.onend?.();}
  }
  window.SpeechRecognition=Recognition;
  navigator.mediaDevices.getUserMedia=async()=>({getTracks:()=>[{stop(){}}]});
  window.emitRecognition=(text,final=true)=>{
   const r=[{transcript:text}];r.isFinal=final;
   window.testRecognition.onresult?.({resultIndex:0,results:[r]});
  };
  window.companionTimings=[];window.addEventListener('medguard:companion-latency',e=>window.companionTimings.push(e.detail));
  window.osSpeechCalls=0;window.speechSynthesis.speak=()=>window.osSpeechCalls++;
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function(...args) { window.doctorTestAudio = this; return play.apply(this,args); };
 });
 let replyText='Tôi đã ghi nhận thông tin bạn cung cấp. Bạn hãy cho biết thời điểm triệu chứng bắt đầu để tôi hỗ trợ rõ ràng hơn.';
 const chatRequests=[];
 const requests=[];let holdNext=null;let voiceFails=false; let voiceDelay=0; let profileFails=false;
 await page.route('**/v1/**',async r=>{
  const path=new URL(r.request().url()).pathname;
  if(path==='/v1/companion/status')return r.fulfill({json:{configured:true,mode:'enforced',synchronous:true,background:false,chat_timeout_ms:40000,revision:'doctor-chat-20261008',message:'Đã có cấu hình AI gateway.'}});
  if(path==='/v1/tts/profiles')return profileFails?r.fulfill({status:404,json:{detail:'Not found'}}):r.fulfill({json:{revision:'doctor-voices-20261008',profiles:{dr_tuan:{voice:'vi-VN-NamMinhNeural',rate:'-8%',pitch:'-6Hz'},dr_mai:{voice:'vi-VN-HoaiMyNeural',rate:'-7%',pitch:'-12Hz'}}}});
  if(path==='/v1/tts'){
   assert.equal(r.request().method(),'POST');const body=r.request().postDataJSON();requests.push(body);
   if(holdNext && !body.text.startsWith('Tôi đã ghi nhận'))await holdNext;
   if (voiceDelay) await new Promise(resolve=>setTimeout(resolve,voiceDelay));
   return voiceFails?r.fulfill({status:503,json:{detail:'Voice unavailable'}}):r.fulfill({status:200,contentType:'audio/wav',body:wav});
  }
  if(path==='/v1/chat'){chatRequests.push(r.request().postDataJSON());assert(!r.request().postDataJSON().messages.at(-1).content.includes('Phong cách tư vấn:'));return r.fulfill({json:{reply:replyText}});}
  return r.fulfill({json:{}});
 });
 await page.goto(`http://127.0.0.1:${port}/static/?view=companion`,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded);
 await page.waitForFunction(()=>window.__companionEngine.renderer.info.render.frame>=3);
 assert(await page.evaluate(()=>{const a=document.querySelector('.grok-canvas-stage').getBoundingClientRect(),b=document.querySelector('.grok-dialogue-overlay').getBoundingClientRect();return a.right<=b.left;}),'desktop response panel is beside the avatar canvas, never covering it');
 const waitPersona=p=>page.waitForFunction(p=>{const e=window.__companionEngine;let matched=false;e?.currentVrm?.scene.traverse(n=>{const ms=Array.isArray(n.material)?n.material:[n.material];if(ms.some(m=>m?.name.includes(p==='dr_mai'?'F00_006_01_Tops':'M00_008_03_Tops')))matched=true});return e?.options.persona===p&&e.isVrmLoaded&&matched},p);
 async function captureUniform(name) {
  const data=await page.evaluate(()=>{
   const e=window.__companionEngine;
   const shoulder=e.currentVrm.humanoid.getRawBoneNode('leftUpperArm');
   shoulder.updateWorldMatrix(true,false);
   const y=shoulder.matrixWorld.elements[13]-.205;
   e.camera.position.set(0,y,1.05);e.camera.lookAt(0,y,0);
   e.renderer.render(e.scene,e.camera);
   const png=e.canvas.toDataURL('image/png');
   e.setCameraPreset('waist');return png.split(',')[1];
  });
  await writeFile(new URL(name,artifactDir),Buffer.from(data,'base64'));
  console.log(`${name}: coat fitting ${Math.round(await page.evaluate(()=>window.__companionEngine.doctorAccessories.userData.coatFitMs))} ms`);
 }
 async function send(){await page.getByRole('textbox',{name:'Nhập câu hỏi cho bác sĩ'}).fill('Tôi muốn hỏi về chăm sóc sức khỏe.');await page.locator('.grok-send-action-btn').click();await page.waitForFunction(()=>window.__companionEngine?.isSpeaking);}
 async function preview(persona,voice) {
  const gaze=await page.evaluate(()=>{
   const e=window.__companionEngine,m=e.motion;
   const head=e.currentVrm.humanoid.getRawBoneNode('head');
   const sample=x=>{for(let i=0;i<180;i++)m.update(1/60,{speaking:false,look:{x,y:0}});head.updateWorldMatrix(true,false);return Array.from(head.matrixWorld.elements);};
   const neutral=sample(0),right=sample(1),left=sample(-1);
   const forwardSign=Math.sign(neutral[10]);
   return {right:right[8]*forwardSign,left:left[8]*forwardSign};
  });
  console.log(persona,'gaze',gaze);
  assert(gaze.right>0 && gaze.left<0,'head turns toward the screen pointer on the real rig');

  await page.locator('.grok-settings-btn').click();
  await page.getByText(`Giọng đang cấu hình trên máy chủ: ${voice}`,{exact:false}).waitFor();
  const wristBefore=await page.evaluate(()=>{const n=window.__companionEngine.currentVrm.humanoid.getRawBoneNode('rightHand');n.updateWorldMatrix(true,false);return n.matrixWorld.elements[13];});
  await page.getByRole('button',{name:'Xem thử cử chỉ chào',exact:true}).click();
  await page.waitForFunction(()=>window.__companionEngine.motion.pose==='pose_wave');
  await page.waitForFunction(()=>{const m=window.__companionEngine.motion;return m.time-m.poseStarted>=1.15;});
  const wristAfter=await page.evaluate(()=>{const n=window.__companionEngine.currentVrm.humanoid.getRawBoneNode('rightHand');n.updateWorldMatrix(true,false);return n.matrixWorld.elements[13];});
  assert(wristAfter>wristBefore+.12,'greeting raises the real rig wrist');
  const elbowBend=await page.evaluate(()=>{
   const h=window.__companionEngine.currentVrm.humanoid;
   const position=n=>{const b=h.getRawBoneNode(n);b.updateWorldMatrix(true,false);return [b.matrixWorld.elements[12],b.matrixWorld.elements[13],b.matrixWorld.elements[14]];};
   const s=position('rightUpperArm'),e=position('rightLowerArm'),w=position('rightHand');
   const u=e.map((v,i)=>v-s[i]),v=w.map((x,i)=>x-e[i]);
   return u.reduce((sum,x,i)=>sum+x*v[i],0)/(Math.hypot(...u)*Math.hypot(...v));
  });
  assert(elbowBend<.7,'greeting keeps the real elbow bent rather than a straight lateral arm');

  await page.screenshot({path:new URL(`${persona}-greeting.png`,artifactDir).pathname});
  await page.locator('.grok-settings-btn').click();
  await page.getByRole('button',{name:'Nghe thử giọng bác sĩ',exact:true}).click();
  await page.waitForFunction(()=>window.__companionEngine.isSpeaking);
  assert.equal(requests.at(-1).persona,persona);
  await page.locator('.grok-settings-card button[title="Đóng"]').click();
  await page.locator('.grok-stop-action-btn').click();
 }
 async function verifyQueue(persona) {
  const original=replyText;
  replyText='Tôi đã ghi nhận thông tin bạn cung cấp. '+
   'Bạn hãy cho biết thời điểm bắt đầu, những thay đổi gần đây và các thông tin liên quan để tôi có thể hiểu rõ tình trạng bạn đang trao đổi. '+
   'Bạn cũng hãy ghi lại các thông tin đã cung cấp để trao đổi khi khám, bao gồm thời gian, mức độ và những thay đổi bạn nhận thấy. '+
   'Nếu xuất hiện đau ngực kèm khó thở hoặc ngất, hãy gọi cấp cứu ngay. Không tự tăng liều thuốc đang dùng. Bạn có đang dùng thuốc nào không?';
  let release;holdNext=new Promise(r=>{release=r;});
  const start=requests.length;
  try {
   await send();
   await page.getByText('Nếu xuất hiện đau ngực kèm khó thở hoặc ngất, hãy gọi cấp cứu ngay.',{exact:false}).waitFor();
   assert.equal(requests[start].persona,persona);
   assert(requests.length>=start+2,'next sentence is prepared concurrently');
   assert.equal(await page.evaluate(()=>window.__companionEngine.isSpeaking),true,'plays first while next response remains blocked');
  } finally {release();holdNext=null;}
  await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='Đọc lại');return b && !b.disabled},null,{timeout:20000});
  assert.equal(requests.slice(start).map(r=>r.text).join(' '),replyText);
  const timings=await page.evaluate(()=>window.companionTimings);
  assert(timings.some(t=>t.stage==='first_audio'&&t.persona===persona));
  assert(timings.every(t=>!('text' in t)&&!('question' in t)));
  replyText=original;
  console.log(`${persona}: first audio before next response, complete warning retained and spoken in order PASS`);
 }
 // ASR final without onend must submit once, then play automatically.
 await page.locator('.grok-mic-primary-btn').click();
 await page.waitForFunction(()=>window.__companionEngine.motion.pose==='pose_listening');
 await page.evaluate(()=>window.emitRecognition('Tôi muốn hỏi về giấc ngủ',false));
 assert.equal(chatRequests.length,0,'interim transcription is never submitted');
 await page.evaluate(()=>window.emitRecognition('Tôi muốn hỏi về giấc ngủ.',true));
 await page.waitForFunction(()=>window.__companionEngine.isSpeaking);
 assert.equal(chatRequests.length,1,'ASR final automatically sends without another click');
 assert.equal(chatRequests[0].messages.at(-1).content,'Tôi muốn hỏi về giấc ngủ.');
 await page.evaluate(()=>window.emitRecognition('Tôi muốn hỏi về giấc ngủ.',true));
 assert.equal(chatRequests.length,1,'duplicate final cannot resubmit');
 await page.locator('.grok-stop-action-btn').click();
 await page.locator('.grok-mic-primary-btn').click();
 await page.waitForFunction(()=>window.__companionEngine.motion.pose==='pose_listening');
 await page.locator('.grok-stop-action-btn').click();
 await page.evaluate(()=>window.emitRecognition('Câu nói đã hủy.',true));
 assert.equal(chatRequests.length,1,'stop invalidates late speech callbacks');
 console.log('MIC: interim preview, final auto-submit/play, deduplication and cancellation PASS');
 await preview('dr_tuan','vi-VN-NamMinhNeural');
 await verifyQueue('dr_tuan');
 await send();assert.equal(requests.at(-1).persona,'dr_tuan');
 // A generated tone does not imply one specific vowel. When the native
 // classifier loads, verify opening across the mouth channels rather than aa.
 await page.waitForFunction(()=>['aa','ee','ih','oh','ou'].some(n=>window.__companionEngine.motion.values[n]>.025));
 // Check inside the WAV's silent segment, using media time instead of a wall-clock delay.
 await page.waitForFunction(()=>{
  const t=window.doctorTestAudio?.currentTime;
  return t>1.1 && t<2.05 && window.__companionEngine.isSpeaking && window.__companionEngine.motion.values.aa<.01;
 },null,{timeout:5000});
 await page.locator('.grok-stop-action-btn').click();
 assert.equal(await page.evaluate(()=>window.__companionEngine.isSpeaking),false);
 await page.waitForTimeout(500);
 await page.screenshot({path:new URL('doctor-male.png',artifactDir).pathname});
 await captureUniform('doctor-male-uniform.png');
 await page.getByRole('button',{name:'BS. Thanh Mai',exact:true}).click();await waitPersona('dr_mai');
 await preview('dr_mai','vi-VN-HoaiMyNeural');
 await verifyQueue('dr_mai');
 await send();assert.equal(requests.at(-1).persona,'dr_mai');
 await page.waitForTimeout(500);
 await page.screenshot({path:new URL('doctor-female-speaking.png',artifactDir).pathname});
 await page.getByRole('button',{name:'BS. Minh Tuấn',exact:true}).click();
 await page.getByRole('button',{name:'BS. Thanh Mai',exact:true}).click();await waitPersona('dr_mai');
 assert.equal(await page.evaluate(()=>window.__companionEngine.isSpeaking),false);
 await page.waitForTimeout(700);
 await page.screenshot({path:new URL('doctor-female.png',artifactDir).pathname});
 await captureUniform('doctor-female-uniform.png');
 await page.evaluate(()=>window.__companionEngine.setCameraPreset('full'));
 await page.screenshot({path:new URL('doctor-female-full.png',artifactDir).pathname});
 await page.evaluate(()=>window.__companionEngine.setCameraPreset('waist'));
 // Stop while audio is being synthesized must also cancel later playback.
 voiceDelay=500;
 await page.getByRole('textbox',{name:'Nhập câu hỏi cho bác sĩ'}).fill('Tôi muốn hỏi thêm.');await page.locator('.grok-send-action-btn').click();
 await page.getByText('Đang chuẩn bị giọng…',{exact:true}).waitFor();
 await page.locator('.grok-stop-action-btn').click();
 await page.waitForTimeout(700);
 assert.equal(await page.evaluate(()=>window.__companionEngine.isSpeaking),false);
 await page.getByRole('textbox',{name:'Nhập câu hỏi cho bác sĩ'}).fill('Tôi muốn hỏi thêm.');await page.locator('.grok-send-action-btn').click();
 await page.getByText('Đang chuẩn bị giọng…',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Âm thanh',exact:true}).click();
 await page.waitForTimeout(700);
 assert.equal(await page.evaluate(()=>window.__companionEngine.isSpeaking),false);
 await page.getByRole('button',{name:'Âm thanh',exact:true}).click();
 voiceDelay=0;
 // A failed provider must not silently change the selected voice to the OS default.
 voiceFails=true;
 await page.getByRole('textbox',{name:'Nhập câu hỏi cho bác sĩ'}).fill('Tôi muốn hỏi thêm.');await page.locator('.grok-send-action-btn').click();
 await page.getByRole('alert').filter({hasText:'Giọng bác sĩ chưa phát được'}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Đọc lại',exact:true}).isEnabled(),true);
 assert.equal(await page.evaluate(()=>window.osSpeechCalls),0);
 assert.equal(await page.evaluate(()=>window.__companionEngine.isSpeaking),false);
 profileFails=true;
 await page.locator('.grok-settings-btn').click();
 await page.getByText('Chưa nhận được cấu hình giọng bác sĩ.',{exact:false}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Nghe thử giọng bác sĩ',exact:true}).isDisabled(),true);
 await page.locator('.grok-settings-card button[title="Đóng"]').click();
 await page.setViewportSize({width:393,height:852});
 await page.waitForTimeout(500);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow');
 assert(await page.evaluate(()=>{const a=document.querySelector('.grok-canvas-stage').getBoundingClientRect(),b=document.querySelector('.grok-dialogue-overlay').getBoundingClientRect();return a.bottom<=b.top;}),'mobile text is below the avatar canvas');
 await page.screenshot({path:new URL('doctor-mobile.png',artifactDir).pathname});
 assert.deepEqual(errors,[]);
 console.log('doctor browser: both VRMs, gender-specific audio, RMS silence, stop, rapid persona switch, provider failure, mobile PASS');
}finally{await browser?.close();process.kill(-server.pid,'SIGTERM');}
