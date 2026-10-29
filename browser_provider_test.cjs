const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
const browser=await chromium.launch({headless:true,channel:'msedge',timeout:20000});const page=await browser.newPage();page.setDefaultTimeout(15000);const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8877');await page.waitForFunction(()=>document.querySelector('#aiProvider').options.length===3);
assert.equal(await page.locator('#aiProvider').inputValue(),'baseten');assert.match(await page.locator('#status').innerText(),/Baseten selected/);
await page.selectOption('#sourceMode','image');await page.setInputFiles('#orderImage',require('node:path').resolve('browser_order_fixture.png'));await page.click('#analyse');await page.waitForSelector('#choice0');
await page.selectOption('#aiProvider','meta');assert.equal(await page.locator('#confirmArea').isHidden(),true);assert.match(await page.locator('#providerInfo').innerText(),/muse-spark-1.3/);
await page.selectOption('#sourceMode','text');await page.fill('#message','Please send 3 green zips');
let pending=page.waitForResponse(r=>r.url().endsWith('/api/propose'));await page.click('#analyse');let response=await pending;assert.equal(response.request().postDataJSON().provider,'meta');assert.equal(response.status(),400);await page.waitForFunction(()=>document.querySelector('#error').textContent.includes('MODEL_API_KEY'));console.log('PASS browser provider selection: default Baseten, Meta model display, provider switch clears proposal, missing Meta credential is visible without fallback.');
await page.selectOption('#aiProvider','baseten');assert.match(await page.locator('#status').innerText(),/Baseten selected/);assert.deepEqual(errors,[]);console.log('PASS switching back to Baseten and no JavaScript errors.');await Promise.race([browser.close(),new Promise(resolve=>setTimeout(resolve,3000))]);process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
