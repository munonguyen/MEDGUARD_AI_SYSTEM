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
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox','--autoplay-policy=no-user-gesture-required']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];await page.addInitScript(()=>{window.companionTimings=[];window.addEventListener('medguard:companion-latency',e=>window.companionTimings.push(e.detail));});page.on('pageerror',e=>errors.push(e.message));
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
  await page.waitForFunction(()=>window.__companionEngine.motion.values.aa>.02);
  const timing=await page.evaluate(()=>window.companionTimings.at(-1));
  assert.equal(timing.stage,'first_audio');assert.equal(timing.persona,persona);
  console.log(`${persona}: first audible audio ${timing.ttsMs} ms (single live sample)`);
  await page.screenshot({path:`${root}.artifacts/${persona}-live-speaking.png`});
  await page.locator('.grok-stop-action-btn').click();console.log(`${persona}: real backend TTS 200, correct voice, real VRM speaking and greeting PASS`);
 }
 assert.deepEqual(errors,[]);
}finally{await browser?.close();process.kill(-server.pid,'SIGTERM');}
