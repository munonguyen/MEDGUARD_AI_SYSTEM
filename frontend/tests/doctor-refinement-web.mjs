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
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox','--autoplay-policy=no-user-gesture-required']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{
  window.osSpeechCalls=0;window.speechSynthesis.speak=()=>window.osSpeechCalls++;
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function(...args) { window.doctorTestAudio = this; return play.apply(this,args); };
 });
 const requests=[];let voiceFails=false; let voiceDelay=0;
 await page.route('**/v1/**',async r=>{
  const path=new URL(r.request().url()).pathname;
  if(path==='/v1/tts'){
   assert.equal(r.request().method(),'POST');requests.push(r.request().postDataJSON());
   if (voiceDelay) await new Promise(resolve=>setTimeout(resolve,voiceDelay));
   return voiceFails?r.fulfill({status:503,json:{detail:'Voice unavailable'}}):r.fulfill({status:200,contentType:'audio/wav',body:wav});
  }
  if(path==='/v1/chat')return r.fulfill({json:{reply:'Tôi đã ghi nhận thông tin bạn cung cấp. Bạn hãy cho biết thời điểm triệu chứng bắt đầu để tôi hỗ trợ rõ ràng hơn.'}});
  return r.fulfill({json:{}});
 });
 await page.goto(`http://127.0.0.1:${port}/static/?view=companion`,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded);
 await page.waitForFunction(()=>window.__companionEngine.renderer.info.render.frame>=3);
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
 await send();assert.equal(requests.at(-1).persona,'dr_tuan');
 await page.waitForFunction(()=>window.__companionEngine.motion.values.aa>.05);
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
 await page.getByText('Giọng bác sĩ tạm thời chưa sẵn sàng.',{exact:false}).waitFor();
 assert.equal(await page.evaluate(()=>window.osSpeechCalls),0);
 assert.equal(await page.evaluate(()=>window.__companionEngine.isSpeaking),false);
 await page.setViewportSize({width:393,height:852});
 await page.waitForTimeout(500);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'no horizontal overflow');
 await page.screenshot({path:new URL('doctor-mobile.png',artifactDir).pathname});
 assert.deepEqual(errors,[]);
 console.log('doctor browser: both VRMs, gender-specific audio, RMS silence, stop, rapid persona switch, provider failure, mobile PASS');
}finally{await browser?.close();process.kill(-server.pid,'SIGTERM');}
