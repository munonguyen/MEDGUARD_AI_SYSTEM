import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {randomUUID} from 'node:crypto';
import {chromium} from 'playwright-core';
const root=new URL('../../',import.meta.url).pathname;
const temp=await mkdtemp(`${tmpdir()}/medguard-auth-proxy-`);
const port=5295;
const env={...process.env,MEDGUARD_ENVIRONMENT:'development',MEDGUARD_AUTH_DATABASE:`${temp}/accounts.sqlite3`};
for(const key of ['MEDGUARD_PUBLIC_ORIGIN','MEDGUARD_SMTP_HOST','MEDGUARD_REQUIRE_VERIFIED_EMAIL'])delete env[key];
const processes=[];let browser;
function launch(cmd,args,cwd){const p=spawn(cmd,args,{cwd,env,stdio:'pipe',detached:true});processes.push(p);return p;}
async function ready(url){for(let i=0;i<100;i++){try{const r=await fetch(url,{signal:AbortSignal.timeout(500)});if(r.ok)return;}catch{}await new Promise(r=>setTimeout(r,100));}throw Error(`Startup failed: ${url}`);}
try{
 launch(process.env.MEDGUARD_TEST_PYTHON||'python3',['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-proxy-headers'],root);
 await ready('http://127.0.0.1:8000/v1/health');
 launch('npm',['run','dev','--','--host','127.0.0.1','--port',String(port),'--strictPort'],`${root}/frontend`);
 await ready(`http://127.0.0.1:${port}/static/`);
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH,headless:true,args:['--no-sandbox']});
 if(process.argv.includes('--expect-origin-rejection')){
  const context=await browser.newContext();const page=await context.newPage();await page.goto(`http://localhost:${port}/static/`);
  const status=await page.evaluate(async()=>{const r=await fetch('/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'synthetic@example.com',password:'synthetic test password'})});return {status:r.status,code:await r.json().then(d=>d.detail?.error_code||d.error_code)};});
  assert.deepEqual(status,{status:403,code:'cross_origin_request'});console.log('Reproduced real Vite proxy login rejection PASS');await context.close();
 }else{
  for(const host of ['localhost','127.0.0.1']){
   const url=`http://${host}:${port}/static/`,context=await browser.newContext(),page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(()=>{if(!sessionStorage.getItem('seeded')){localStorage.setItem('medguard.auth.remember',JSON.stringify({email:'legacy@example.com',password:'obsolete synthetic secret'}));sessionStorage.setItem('seeded','1');}});
   let logins=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/auth/login'))logins++;});
   await page.goto(url);await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor();
   assert.equal(logins,0,'must not replay cached passwords');assert.equal(await page.evaluate(()=>localStorage.getItem('medguard.auth.remember')),null);
   await page.getByRole('button',{name:'Đăng ký',exact:true}).click();
   const email=`proxy-${randomUUID()}@example.com`,password='Synthetic secure test password 31!';
   await page.getByLabel('Email',{exact:true}).fill(email);await page.getByLabel('Mật khẩu',{exact:true}).fill(password);await page.getByRole('checkbox').check();
   await page.getByRole('button',{name:'Tạo tài khoản',exact:true}).click();await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor();
   await page.getByLabel('Mật khẩu',{exact:true}).fill(password);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
   await page.locator('.account-topbar-pill').waitFor();
   const cookie=(await context.cookies()).find(c=>c.name==='medguard_session');assert(cookie?.httpOnly&&cookie.sameSite==='Strict');
   assert.equal(await page.evaluate(()=>document.cookie.includes('medguard_session')),false);
   assert.equal(await page.evaluate(p=>Object.values(localStorage).some(v=>v.includes(p)),password),false);
   await page.reload();await page.locator('.account-topbar-pill').waitFor();
   const csrf=(await (await page.request.get(new URL('/v1/auth/csrf',url).href)).json()).csrf_token;
   for(const headers of [ {'Origin':'https://attacker.invalid','X-CSRF-Token':csrf}, {'Origin':`http://${host}:${port}`}, {'Origin':`http://${host}:${port}`,'Sec-Fetch-Site':'cross-site','X-CSRF-Token':csrf} ]){
    const response=await page.request.post(new URL('/v1/auth/logout',url).href,{headers});assert.equal(response.status(),403);
   }
   assert.equal((await page.request.get(new URL('/v1/auth/me',url).href)).status(),200,'rejected logout must leave session valid');
   await page.locator('.account-topbar-pill').click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor();
   assert.equal((await page.request.get(new URL('/v1/auth/me',url).href)).status(),401);assert.deepEqual(errors,[]);
   await context.close();console.log(`Real proxy ${host}: registration/login/reload/logout, cookie, cache migration, CSRF and cross-origin rejection PASS`);
  }
 }
}finally{await browser?.close();for(const p of processes){try{process.kill(-p.pid,'SIGTERM');}catch{}}await rm(temp,{recursive:true,force:true});}
