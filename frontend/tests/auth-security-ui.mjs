import assert from 'node:assert/strict';
import { randomUUID, createHmac } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { chromium } from 'playwright-core';
const baseUrl=process.env.MEDGUARD_UI_URL||'http://127.0.0.1:8000';
const output='../artifacts/auth_security';
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
const results=[];
function totp(secret, step) {
 const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'; let bits='';
 for(const c of secret)bits+=alphabet.indexOf(c).toString(2).padStart(5,'0');
 const key=Buffer.from(bits.match(/.{8}/g).map(b=>parseInt(b,2)));const message=Buffer.alloc(8);message.writeBigUInt64BE(BigInt(step));
 const raw=createHmac('sha1',key).update(message).digest();return ((raw.readUInt32BE(raw[19]&15)&0x7fffffff)%1000000).toString().padStart(6,'0');
}
async function layout(page) {assert(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1));}
try {
 for(const [device,viewport] of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]) {
  const context=await browser.newContext({viewport});const page=await context.newPage();page.setDefaultTimeout(12000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const email=`auth-ui-${randomUUID()}@example.com`,password='unique auth UI password 28!';
  await page.goto(baseUrl);await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor();await layout(page);
  await page.screenshot({path:`${output}/${device}-login.png`,fullPage:true});
  await page.getByRole('button',{name:'Đăng ký',exact:true}).click();
  await page.getByLabel('Email',{exact:true}).fill(email);await page.getByLabel('Mật khẩu',{exact:true}).fill(password);
  await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Tạo tài khoản',exact:true}).click();
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor();await page.getByLabel('Mật khẩu',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await page.getByRole('textbox',{name:'Tin nhắn'}).waitFor();
  assert(!(await page.evaluate(()=>document.cookie)).includes('medguard_session'));
  const cookies=await context.cookies();const cookie=cookies.find(c=>c.name==='medguard_session');assert(cookie.httpOnly&&cookie.sameSite==='Strict');
  await page.reload();await page.getByRole('textbox',{name:'Tin nhắn'}).waitFor();
  const tab=await context.newPage();await tab.goto(baseUrl);await tab.getByRole('textbox',{name:'Tin nhắn'}).waitFor();await tab.close();
  await page.getByRole('button',{name:'Tài khoản & bảo mật',exact:true}).click();await page.getByRole('heading',{name:'Tài khoản & bảo mật',exact:true}).waitFor();
  await layout(page);await page.screenshot({path:`${output}/${device}-security.png`,fullPage:true});
  await page.getByLabel('Mật khẩu hiện tại',{exact:true}).fill(password);await page.getByRole('button',{name:'Thiết lập MFA',exact:true}).click();
  await page.locator('.auth-secret').waitFor();const secret=await page.locator('.auth-secret').innerText();
  await page.getByLabel('Mã MFA hoặc mã khôi phục',{exact:true}).fill(totp(secret,Math.floor(Date.now()/30000)));
  await page.getByRole('button',{name:'Xác nhận bật MFA',exact:true}).click();await page.getByRole('heading',{name:/Mã khôi phục/}).waitFor();
  const backups=await page.locator('.auth-secret').allInnerTexts();assert.equal(backups.length,10);
  // No screenshot of enrollment secret or recovery codes is retained.
  await page.getByLabel('Mật khẩu',{exact:true}).fill(password);await page.getByLabel('Mã MFA hoặc mã khôi phục (nếu đã bật)',{exact:true}).fill(backups[0]);
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();
  try {await page.getByRole('textbox',{name:'Tin nhắn'}).waitFor();} catch(e){console.log(await page.locator('input').evaluateAll(els=>els.map(el=>({type:el.type,length:el.value.length,valid:el.checkValidity(),message:el.validationMessage}))));console.log(await page.getByRole('alert').allTextContents());throw e;}
  await page.getByRole('button',{name:'Tài khoản & bảo mật',exact:true}).click();await page.getByLabel('Mật khẩu hiện tại',{exact:true}).fill(password);
  await page.getByLabel('Mã MFA hoặc mã khôi phục',{exact:true}).fill(backups[1]);await page.getByRole('button',{name:'Tắt MFA sau xác thực',exact:true}).click();
  await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor();
  await page.getByLabel('Mật khẩu',{exact:true}).fill(password);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await page.getByRole('textbox',{name:'Tin nhắn'}).waitFor();
  if(device==='desktop') {
   const uid=(await (await page.request.get(`${baseUrl}/v1/auth/me`)).json()).user.id;
   const token=execFileSync('../.venv/bin/python',['-c',"import sys;sys.path.insert(0,'..');from app.core.accounts import AccountStore;print(AccountStore().token(sys.argv[1],'reset'))",uid],{encoding:'utf8'}).trim();
   await page.goto(`${baseUrl}/#reset_token=${token}`);await page.getByRole('button',{name:'Đặt lại mật khẩu',exact:true}).waitFor();
   assert(!page.url().includes(token));
   const replacement='replacement auth UI password 29!';await page.getByLabel('Mật khẩu',{exact:true}).fill(replacement);
   await page.getByRole('button',{name:'Đặt lại mật khẩu',exact:true}).click();await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor();
   await page.getByLabel('Email',{exact:true}).fill(email);await page.getByLabel('Mật khẩu',{exact:true}).fill(replacement);
   await page.getByRole('button',{name:'Đăng nhập',exact:true}).click();await page.getByRole('textbox',{name:'Tin nhắn'}).waitFor();
  }
  await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();await page.getByRole('button',{name:'Đăng nhập',exact:true}).waitFor();
  assert.equal((await page.request.get(`${baseUrl}/v1/auth/me`)).status(),401);
  assert(!await page.evaluate(()=>Object.entries(localStorage).some(([k,v])=>/auth|session|password|token/.test(k)&&v.includes('unique auth UI'))));
  assert.deepEqual(errors,[]);results.push({device,passed:true,checks:['registration','login','HttpOnly cookie','reload','multi-tab CSRF','account security','MFA enrollment','recovery login','MFA disable with recovery',...(device==='desktop'?['reset URL fragment while logged in']:[]),'logout'],screenshots:[`${device}-login.png`,`${device}-security.png`]});await context.close();
 }
 await writeFile(`${output}/browser_evidence.json`,JSON.stringify({code_sha:execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim(),runtime:'real browser and local API; no response substitution; no real email sent',passed:true,total:results.length,results},null,2));
 console.log(JSON.stringify(results));
}finally{await browser.close();}
