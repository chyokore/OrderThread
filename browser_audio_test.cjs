const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
const browser=await chromium.launch({headless:true,channel:'msedge'});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const base='http://127.0.0.1:8878';await page.goto(base);await page.waitForFunction(()=>document.querySelector('#aiProvider').value==='baseten');
await page.selectOption('#sourceMode','audio');assert.equal(await page.locator('#message').isVisible(),false);
const bytes=Buffer.alloc(32044);bytes.write('RIFF');bytes.writeUInt32LE(32036,4);bytes.write('WAVEfmt ',8);bytes.writeUInt32LE(16,16);bytes.writeUInt16LE(1,20);bytes.writeUInt16LE(1,22);bytes.writeUInt32LE(16000,24);bytes.writeUInt32LE(32000,28);bytes.writeUInt16LE(2,32);bytes.writeUInt16LE(16,34);bytes.write('data',36);bytes.writeUInt32LE(32000,40);
await page.setInputFiles('#voiceNote',{name:'temporary.wav',mimeType:'audio/wav',buffer:bytes});
await page.click('#analyse');await page.waitForSelector('#transcript');assert.match(await page.locator('#proposal').innerText(),/AI-generated transcript/);assert.match(await page.locator('#proposal').innerText(),/Instructions only/);
assert.deepEqual(await page.request.get(base+'/api/events').then(r=>r.json()),[]);
await page.click('#confirm');assert.match(await page.locator('#error').innerText(),/Confirm/);
await page.check('#audioReviewed');await page.fill('#audioNote','Customer will pick up tomorrow; list was already sent.');assert.equal(await page.locator('#audioReviewed').isChecked(),false);
await page.check('#audioReviewed');const pending=page.waitForResponse(r=>r.url().endsWith('/api/confirm'));await page.click('#confirm');assert.equal((await pending).status(),200);await page.waitForFunction(()=>document.querySelector('#history').textContent.includes('Source: uploaded audio'));
const history=await page.request.get(base+'/api/events').then(r=>r.json());assert.equal(history.length,1);assert.equal(history[0].data.items.length,0);assert.match(history[0].data.fulfillment_note,/list was already sent/);assert.deepEqual(await page.request.get(base+'/api/orders').then(r=>r.json()),[]);
await page.selectOption('#savedReview',String(history[0].id));assert.equal(await page.locator('#apply').isDisabled(),true);assert.match(await page.locator('#reviewHelp').innerText(),/Instruction-only/);
await page.reload();await page.waitForFunction(()=>document.querySelector('#history').textContent.includes('AI-generated transcript'));await page.selectOption('#sourceMode','text');assert.equal(await page.locator('#message').isVisible(),true);await page.selectOption('#sourceMode','image');assert.equal(await page.locator('#orderImage').isVisible(),true);assert.deepEqual(errors,[]);
console.log('PASS audio browser: temporary WAV/mock, transcript and instructions, correction clears confirmation, explicit save, no invented items/orders, persisted source label, text/image recovery, no JS errors.');await Promise.race([browser.close(),new Promise(resolve=>setTimeout(resolve,3000))]);process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
