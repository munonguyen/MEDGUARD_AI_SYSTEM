import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';
const root=new URL('../../',import.meta.url).pathname;
const server=spawn(process.env.MEDGUARD_TEST_PYTHON||root+'.venv/bin/python',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8466'],{cwd:root,stdio:'pipe',detached:true});
// Opt-in live TTS check: synthetic greetings only; requires Internet, no mocks.
// Backend port 8466 must be free. Screenshots contain no clinical conversation.
let browser;
try{
 await mkdir(root+'.artifacts',{recursive:true});
 for(let i=0;i<100;i++){try{if((await fetch('http://127.0.0.1:8466/v1/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];await page.addInitScript(()=>{const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(...args){window.testLiveAudio=this;return play.apply(this,args);};window.companionTimings=[];window.addEventListener('medguard:companion-latency',e=>window.companionTimings.push(e.detail));});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8466/?view=companion');await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded);
 for(const [persona,button] of [['dr_tuan','BS. Minh Tuấn'],['dr_mai','BS. Thanh Mai']]){
  if(persona==='dr_mai')await page.getByRole('button',{name:button,exact:true}).click();
  await page.waitForFunction(p=>window.__companionEngine?.isVrmLoaded&&window.__companionEngine.options.persona===p,persona);
  await page.locator('.grok-settings-btn').click();await page.getByText('doctor-voices-20261008',{exact:false}).waitFor();
  await page.getByRole('button',{name:'Xem thử cử chỉ chào',exact:true}).click();await page.waitForTimeout(1200);await page.screenshot({path:`${root}.artifacts/${persona}-greeting.png`});
  await page.locator('.grok-settings-btn').click();
  const response=page.waitForResponse(r=>r.url().endsWith('/v1/tts')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Nghe thử giọng bác sĩ',exact:true}).click();
  const audio=await response;assert.equal(audio.status(),200);assert(Number(audio.headers()['content-length'])>1000);assert.equal(audio.headers()['x-doctor-voice'],persona==='dr_tuan'?'vi-VN-NamMinhNeural':'vi-VN-HoaiMyNeural');
  await page.waitForFunction(()=>window.__companionEngine.isSpeaking);await page.locator('.grok-settings-card button[title="Đóng"]').click();
  await page.waitForFunction(()=>['aa','ee','ih','oh','ou'].some(n=>window.__companionEngine.motion.values[n]>.01));
  const timing=await page.evaluate(()=>window.companionTimings.at(-1));
  assert.equal(timing.stage,'first_audio');assert.equal(timing.persona,persona);
  console.log(`${persona}: first audible audio ${timing.ttsMs} ms (single live sample)`);
  await page.screenshot({path:`${root}.artifacts/${persona}-live-speaking.png`});
  const playback=await page.evaluate(()=>({time:window.testLiveAudio.currentTime,muted:window.testLiveAudio.muted,paused:window.testLiveAudio.paused}));
  assert(playback.time>0&&!playback.muted&&!playback.paused,'actual media clock advances with audible playback enabled');
  await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='Đọc lại');return b&&!b.disabled},null,{timeout:60000});
  assert.equal(await page.evaluate(()=>window.__companionEngine.isSpeaking),false);
  console.log(`${persona}: real backend TTS 200, correct voice, real VRM speaking and greeting PASS`);
  // A second interaction must finish on the same backend/audio context.
  await page.locator('.grok-settings-btn').click();
  const secondResponse=page.waitForResponse(r=>r.url().endsWith('/v1/tts')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Nghe thử giọng bác sĩ',exact:true}).click();
  const secondAudio=await secondResponse;assert.equal(secondAudio.status(),200,'second TTS request succeeds');
  await page.waitForFunction(()=>window.__companionEngine.isSpeaking);
  await page.locator('.grok-settings-card button[title="Đóng"]').click();
  await page.waitForFunction(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='Đọc lại');return b&&!b.disabled},null,{timeout:60000});
  console.log(`${persona}: consecutive second voice interaction PASS`);

 }
 const status=await(await fetch('http://127.0.0.1:8466/v1/companion/status')).json();
 console.log('AI gateway configured:',status.configured);
 assert.deepEqual(errors,[]);
}finally{await browser?.close();process.kill(-server.pid,'SIGTERM');}
