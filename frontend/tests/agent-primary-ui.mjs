import { authenticatePage } from './login-helper.mjs';
// Mocked UI authority contract only; no real model call.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {chromium} from 'playwright-core';
const saved=JSON.parse(await readFile('../artifacts/v28_adaptive_length/browser_evidence.json','utf8'));
const original=saved.results.find(x=>x.question.includes('đau răng')).response;
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
const results=[];
try {
 for(const [device,viewport] of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]])for(const verified of [true,false]){
  const context=await browser.newContext({viewport}),page=await context.newPage(),f=structuredClone(original);
  f.answer.summary='LEGACY_SUMMARY_MARKER';f.answer.next_steps=['LEGACY_ACTION_MARKER'];
  f.answer.narrative=[{kind:'paragraph',text:'VERIFIED_AGENT_MARKER: nội dung agent đã duyệt.',source_ids:[],emphasis:[]}];
  f.verification_status=verified?'verified':'unavailable';f.answer_origin=verified?'gateway_verified':'deterministic_fallback';
  await page.route('**/v1/chat',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify(f)}));
  await authenticatePage(page, 'http://127.0.0.1:8000');
  await page.goto('http://127.0.0.1:8000');await page.getByRole('textbox',{name:'Tin nhắn'}).fill('Tôi đau răng');await page.getByRole('button',{name:'Gửi tin nhắn'}).click();
  const card=page.locator('.chat-assistant:not(.pending):visible').last();await card.locator('.clinical-summary-copy').waitFor();
  if(verified){await card.locator('[data-answer-authority="verified-agent"]').waitFor();const t=await card.innerText();assert(t.includes('VERIFIED_AGENT_MARKER'));assert(!t.includes('LEGACY_SUMMARY_MARKER')&&!t.includes('LEGACY_ACTION_MARKER'));}
  else{await card.locator('[role="status"]').waitFor();assert((await card.innerText()).includes('Chưa hoàn tất thẩm định'));assert.equal(await card.locator('[data-answer-authority="verified-agent"]').count(),0);}
  results.push({device,verified_fixture:verified,passed:true});await context.close();
 }
 await writeFile('../artifacts/v28_adaptive_length/agent_primary_ui_contract.json',JSON.stringify({scope:'mocked UI authority contract; no real model call',results},null,2));console.log('Mocked UI contracts PASS: '+results.length);
}finally{await browser.close();}
