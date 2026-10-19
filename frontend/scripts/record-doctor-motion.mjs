// Opt-in visual review, NOT a clinical/voice integration test. No patient data,
// no AI calls, simulated audio envelope and a permanent visible fixture label.
import {chromium} from 'playwright-core';
import {spawn,execFileSync} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
const root=new URL('../../',import.meta.url).pathname,front=new URL('../',import.meta.url).pathname;
const dir=root+'.artifacts/holistic-recording',port=5294;
await mkdir(dir,{recursive:true});await mkdir(front+'.artifacts',{recursive:true});
const reference=process.env.MEDGUARD_MOTION_REFERENCE||'7fc4b9c';
await writeFile(front+'.artifacts/motion-before.js',execFileSync('git',['show',reference+':frontend/src/companion/doctorMotion.js'],{cwd:root}));
const server=spawn('npm',['run','dev','--','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:front,stdio:'pipe',detached:true});
await new Promise((resolve,reject)=>{server.stdout.on('data',d=>{if(d.toString().includes('Local:'))resolve()});server.on('exit',c=>reject(Error('Vite '+c)));setTimeout(()=>reject(Error('Vite timeout')),15000).unref();});
let browser,context;
try {
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox']});
 context=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir,size:{width:1440,height:1000}}});
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/v1/**',r=>r.fulfill({json:{}}));
 await page.goto(`http://127.0.0.1:${port}/static/?view=companion`);await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded);
 await page.evaluate(async()=>{
  window.reviewNew=(await import('/static/src/companion/doctorMotion.js')).DoctorMotion;
  window.reviewOld=(await import('/static/.artifacts/motion-before.js')).DoctorMotion;
  const box=document.createElement('div');box.id='review-banner';
  Object.assign(box.style,{position:'fixed',pointerEvents:'none',top:'112px',left:'24px',right:'24px',zIndex:1000,padding:'14px 22px',borderRadius:'12px',background:'#082e39',color:'#e9fcfc',font:'600 23px system-ui',border:'1px solid #51b8a9'});document.body.append(box);
  const note=document.createElement('div');note.textContent='KIỂM TRA CHUYỂN ĐỘNG · Khẩu hình mô phỏng · Video không có âm thanh';
  Object.assign(note.style,{position:'fixed',bottom:'12px',left:'24px',zIndex:1000,padding:'8px 16px',borderRadius:'8px',background:'#082e39',color:'#b8d6d8',font:'15px system-ui'});document.body.append(note);
 });
 const cases=[
  {name:'Chào hỏi',pose:'pose_idle',question:'Chào bác sĩ.',text:'Xin chào bạn. Tôi đang lắng nghe.'},
  {name:'Lắng nghe',pose:'pose_listening',question:'Tôi cần chia sẻ.',text:'Đang lắng nghe người dùng…'},
  {name:'Suy nghĩ và nhìn lại người dùng',pose:'pose_thinking',question:'Tôi muốn hiểu rõ cơ chế.',text:'Đang phân tích câu hỏi…'},
  {name:'Giải thích',pose:'pose_idle',question:'Tôi muốn hiểu rõ cơ chế.',text:'Tôi sẽ giải thích cơ chế và các thông tin liên quan.'},
  {name:'Trấn an',pose:'pose_idle',question:'Tôi lo lắng.',text:'Tôi hiểu bạn đang lo lắng và luôn sẵn sàng lắng nghe.'},
  {name:'Cảnh báo',pose:'pose_idle',question:'Tôi hỏi về an toàn dùng thuốc.',text:'Không tự tăng liều thuốc. Hãy trao đổi với bác sĩ điều trị.'},
  {name:'So sánh hai lựa chọn',pose:'pose_idle',question:'Hai nhóm khác nhau thế nào?',text:'Hai nhóm này khác nhau. Tôi sẽ giải thích từng điểm.'},
  {name:'Hướng dẫn theo bước',pose:'pose_idle',question:'Tôi cần ghi lại những gì?',text:'Đầu tiên hãy ghi lại thông tin. Tiếp theo hãy theo dõi những thay đổi.'},
 ];
 const markers=[];
 for(const persona of ['dr_tuan','dr_mai']) {
  if(persona==='dr_mai'){await page.getByRole('button',{name:'BS. Thanh Mai',exact:true}).click();await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded&&window.__companionEngine.options.persona==='dr_mai');}
  for(const before of [true,false]) {
   const scenes=before?cases.filter(c=>['Chào hỏi','Giải thích','Trấn an'].includes(c.name)):cases;
   for(const scene of scenes) {
    await page.evaluate(({scene,before,persona})=>{
     const e=window.__companionEngine;e.stopSpeaking();e.currentVrm.humanoid.resetNormalizedPose();
     e.currentVrm.lookAt.reset();e.currentVrm.lookAt.autoUpdate=before;
     let seed=713;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2**32;};
     e.motion=new (before?window.reviewOld:window.reviewNew)(e.currentVrm,persona,{random});
     e.motion.tone='clinical';e.motion.setContext?.(scene.question);e.motion.startUtterance(scene.text);e.motion.setPose(scene.pose);
     const original=e.motion.update.bind(e.motion);
     e.motion.update=(dt,input)=>{const talking=e.isSpeaking;const t=e.motion.time;original(dt,{...input,hasAudio:talking,audioLevel:talking&&t%1.4<1.05?.12:0,spectrum:{low:.45,mid:.4,high:.15}});};
     e.mouseTarget={x:.15,y:.10};e.setCameraPreset('waist');e.isSpeaking=scene.pose==='pose_idle';
     document.querySelector('#review-banner').textContent=`${before?'TRƯỚC':'SAU'} · ${persona==='dr_tuan'?'Bác sĩ Minh Tuấn':'Bác sĩ Thanh Mai'} · ${scene.name}`;
     document.querySelector('.grok-bubble-text').textContent=`Bối cảnh: ${scene.question}\n\n${scene.text}`;
    },{scene,before,persona});
    markers.push({persona,before,scene:scene.name,at:await page.evaluate(()=>performance.now()/1000)});
    await page.waitForTimeout(before?3500:4500);
    await page.evaluate(()=>{const e=window.__companionEngine;e.isSpeaking=false;e.motion.setPose('pose_idle');});await page.waitForTimeout(650);
   }
  }
  console.log(`${persona}: before/after visual review recorded`);
 }
 if(errors.length)throw Error(errors.join('\n'));
 const video=page.video();await context.close();context=null;
 await writeFile(dir+'/video-path.txt',await video.path());await writeFile(dir+'/scenes.json',JSON.stringify({reference,fixture:true,markers},null,2));
 console.log('Recorded',await video.path());
}finally{await context?.close();await browser?.close();process.kill(-server.pid,'SIGTERM');}
