// Same-offer fit, stock, price, URL history and responsive truck controls.
const {chromium}=require('playwright'),{serve}=require('./check_topbar.cjs');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const [site,out]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});
 const {server,base}=await serve(site);
 const browser=await chromium.launch({executablePath:process.env.BROWSER_BINARY,args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try{for(const width of [1440,390,320]){
  console.log('Truck fit',width);
  const page=await browser.newPage({viewport:{width,height:950},isMobile:width<500,hasTouch:width<500});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  async function visit(query=''){
   await page.goto(base+'/truck-fixtures.html?type=trucks&layout=cards'+query);
   await page.waitForFunction(()=>typeof TruckFit!=='undefined'&&typeof captureState==='function'&&state.part==='Trucks');
   await page.waitForFunction(()=>document.querySelector('#truckfitFilters .spec-chip'));
  }
  const visible=()=>page.locator('.deal-row:not(.filtered-out)').evaluateAll(nodes=>nodes.map(n=>new URL(n.dataset.url).pathname.slice(1)).sort());
  await visit();assert.equal((await visible()).length,8);
  assert(await page.locator('[data-section="trucknative"]').evaluate(n=>n.classList.contains('is-type-hidden')));
  await visit('&min=100');
  assert.equal(await page.locator('#truckfitFilters [data-value="9.0"] .spec-count').innerText(),'1');
  await visit('&truckfit=9.0&max=60');assert.deepEqual(await visible(),[]);
  await visit('&truckfit=9.0&trucknative=ace%3A55');assert.deepEqual(await visible(),[]);
  await visit('&truckfit=9.0&brand=Ace');assert.deepEqual(await visible(),['variants']);
  const card=page.locator('.deal-card[data-url$="/variants"]');
  assert.match(await card.locator('.now-price').innerText(),/150\.00/);
  assert.match(await card.locator('.truck-fit-label').innerText(),/Ace 66/);
  assert.equal(await card.locator('.avg-price').isVisible(),false);
  assert(!await page.locator('[data-section="trucknative"]').evaluate(n=>n.classList.contains('is-type-hidden')));
  assert.equal(await page.locator('#trucknativeFilters [data-value="independent:166"]').isVisible(),false);
  await visit('&truckfit=9.5%2B');assert.deepEqual(await visible(),['classic','wide']);
  assert.match(await page.locator('.deal-card[data-url$="/wide"] .truck-fit-label').innerText(),/owner guidance 9\.75\+/);
  await visit('&trucksize=8.75');assert.deepEqual(await visible(),['legacy']);
  await visit('&trucknative=independent%3A166');assert.deepEqual(await visible(),['stage4']);
  await visit('&q=indy%20159');assert.deepEqual(await visible(),['legacy']);
  await visit('&q=ace%2066');assert.deepEqual(await visible(),['classic','variants']);
  await visit('&q=9.0%20trucks');assert.deepEqual(await visible(),['stage4','variants']);
  // A real chip interaction must survive both browser history directions.
  await visit();if(width<500)await page.locator('#filtersOpen').click();
  await page.locator('#truckfitFilters [data-value="9.0"]').click();
  await page.waitForFunction(()=>new URLSearchParams(location.search).get('truckfit')==='9.0');
  assert.deepEqual(await visible(),['stage4','variants']);
  await page.goBack();await page.waitForFunction(()=>state.truckFits.length===0);assert.equal((await visible()).length,8);
  await page.goForward();await page.waitForFunction(()=>state.truckFits.includes('9.0'));assert.deepEqual(await visible(),['stage4','variants']);
  if(width<500)await page.locator('#filtersClose').click();
  const quick=page.locator('.deal-card[data-url$="/variants"]');await quick.hover();await quick.locator('.card-quick').click();
  await page.waitForSelector('#quickView', {state:'visible'});
  assert.match(await page.locator('#quickView').innerText(),/150\.00/);
  assert.match(await page.locator('#quickView').innerText(),/Ace 66/);
  await page.keyboard.press('Escape');
  if(width<500){await page.locator('#filtersOpen').click();await page.waitForFunction(()=>getComputedStyle(document.getElementById('filterDrawer')).transform==='none');}
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:path.join(out,'trucks-'+width+'.png')});
  assert.deepEqual(errors,[]);results.push({width,status:'pass'});await page.close();
 }
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
