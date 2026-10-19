import assert from 'node:assert/strict';
import {chromium} from 'playwright-core';
import {spawn} from 'node:child_process';
import {mkdir,writeFile} from 'node:fs/promises';
const port=Number(process.env.MEDGUARD_TEST_PORT||5293);
const server=spawn('npm',['run','dev','--','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:new URL('../',import.meta.url),stdio:'pipe',detached:true});
await new Promise((resolve,reject)=>{server.stdout.on('data',d=>{if(d.toString().includes('Local:'))resolve()});server.on('exit',c=>reject(Error(`Vite exited ${c}`)));setTimeout(()=>reject(Error('Vite startup timed out')),15000).unref();});
const artifactDir=new URL('../../.artifacts/doctor-refinement/',import.meta.url);await mkdir(artifactDir,{recursive:true});

let browser;
try{
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1200,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/v1/**',r=>r.fulfill({json:{}}));
 let failing=true,fallbackRequests=0;
 await page.route('**/models/*.vrm',r=>{if(r.request().url().includes('Alicia'))fallbackRequests++;return failing?r.fulfill({status:404,body:'Model missing'}):r.continue();});
 await page.goto(`http://127.0.0.1:${port}/static/?view=companion`);
 await page.getByRole('alert').filter({hasText:'Chưa hiển thị được nhân vật 3D'}).waitFor();
 assert.ok((await page.getByRole('alert').innerText()).includes('DoctorTuan.vrm'));
 assert.equal(fallbackRequests,0,'failed doctor load must not silently substitute another character');
 assert.ok((await page.locator('.grok-model-badge').innerText()).includes('Lỗi tải nhân vật'));
 failing=false;await page.getByRole('button',{name:'Thử tải lại nhân vật'}).click();
 await page.waitForFunction(()=>window.__companionEngine?.isVrmLoaded);
 await page.waitForFunction(()=>!document.querySelector('.grok-model-error'));
 const sizes=await page.evaluate(()=>{const e=window.__companionEngine,before=e.canvas.height,aspect=e.camera.aspect;e.resize(0,0);return {before,after:e.canvas.height,aspect,afterAspect:e.camera.aspect};});
 assert.equal(sizes.before,sizes.after);assert.equal(sizes.aspect,sizes.afterAspect,'zero-size layout cannot blank the renderer');
 await page.evaluate(()=>window.__companionEngine.canvas.dispatchEvent(new Event('webglcontextlost',{cancelable:true})));
 await page.getByRole('alert').waitFor();
 await page.evaluate(()=>window.__companionEngine.canvas.dispatchEvent(new Event('webglcontextrestored')));
 await page.waitForFunction(()=>!document.querySelector('.grok-model-error'));
 assert.deepEqual(errors,[]);await page.close();
 const blocked=await browser.newPage();const blockedErrors=[];blocked.on('pageerror',e=>blockedErrors.push(e.message));
 await blocked.route('**/v1/**',r=>r.fulfill({json:{}}));
 await blocked.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:original.call(this,type,...args);};});
 await blocked.goto(`http://127.0.0.1:${port}/static/?view=companion`);
 await blocked.getByRole('alert').filter({hasText:'Chưa hiển thị được nhân vật 3D'}).waitFor();
 assert.deepEqual(blockedErrors,[],'unsupported WebGL is reported without crashing React');
 console.log('doctor loading: missing model, retry, zero-sized canvas, context recovery and unsupported WebGL PASS');
}finally{await browser?.close();process.kill(-server.pid,'SIGTERM');}
