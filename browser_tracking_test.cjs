const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const base='http://127.0.0.1:8876';
await page.goto(base);
const saved=await page.request.post(base+'/api/confirm',{data:{message:'10 blue zips',proposal:{items:[{name:'zips',variant:'blue',quantity:10,evidence:'10 blue zips'}]},decisions:['new']}}).then(r=>r.json());
const applied=await page.request.post(base+'/api/apply',{data:{event_id:saved.event_id,order_id:'__new__',order_name:'Tracking browser order',targets:[null],confirmed:true}}).then(r=>r.json());
assert.ok(applied.order_id);
await page.reload();await page.waitForFunction(id=>Array.from(document.querySelector('#trackingOrder').options).some(o=>o.value===id),applied.order_id);
await page.selectOption('#trackingOrder',applied.order_id);
await page.fill('#trackingQty0','4');await page.click('#recordTracking');assert.match(await page.locator('#trackingResult').innerText(),/Check confirmation/);
async function record(q,kind,status=200){
 await page.selectOption('#trackingKind',kind);await page.fill('#trackingQty0',String(q));await page.check('#trackingConfirm');
 const pending=page.waitForResponse(r=>r.url().endsWith('/api/fulfillment'));
 await page.click('#recordTracking');const response=await pending;assert.equal(response.status(),status);
 await page.waitForFunction(()=>!document.querySelector('#recordTracking').disabled);
 assert.match(await page.locator('#trackingResult').innerText(),status===200?/Success:/:/Could not record/);
 return response.request().postDataJSON();
}
const first=await record(4,'dispatch');console.log('PASS browser partial dispatch: ordered 10, dispatched 4, outstanding 6');
const retry=await page.request.post(base+'/api/fulfillment',{data:first}).then(r=>r.json());assert.equal(retry.already_recorded,true);
await record(7,'dispatch',400);await record(5,'receipt',400);await record(2,'receipt');
console.log('PASS browser over-dispatch and over-receipt show nearby errors; partial receipt succeeds');
await record(6,'dispatch');
let orders=await page.request.get(base+'/api/orders').then(r=>r.json());let order=orders.find(o=>o.id===applied.order_id);
assert.deepEqual([order.items[0].ordered,order.items[0].dispatched,order.items[0].outstanding_dispatch,order.items[0].received],[10,10,0,2]);assert.equal(order.fulfillment_history.length,3);assert.ok(order.fulfillment_history.every(a=>a.created.endsWith('Z')));
await page.reload();await page.waitForFunction(()=>document.querySelector('#orders').textContent.includes('Tracking browser order'));
const line=page.locator(`tr[data-line-id="${order.items[0].id}"] td`);assert.deepEqual(await line.allTextContents(),['10','10','0','2']);
await page.selectOption('#trackingOrder',applied.order_id);await page.fill('#trackingQty0','-1');await page.check('#trackingConfirm');await page.click('#recordTracking');assert.match(await page.locator('#trackingResult').innerText(),/positive whole numbers/);
assert.deepEqual(errors,[]);console.log('PASS browser full dispatch, balances after reload, timestamped history, duplicate retry, negative quantity and confirmation; no JavaScript errors');
await Promise.race([browser.close(),new Promise(resolve=>setTimeout(resolve,3000))]);process.exit(0);
})().catch(e=>{console.error(e);process.exit(1)});
