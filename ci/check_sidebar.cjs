// Part A: disclosure and legacy state contract, using saved catalogs only.
const {chromium}=require('playwright');const{serve}=require('./check_topbar.cjs');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{const[site,out]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});const{server,base}=await serve(site);
const browser=await chromium.launch({executablePath:process.env.BROWSER_BINARY,args:['--no-sandbox','--disable-dev-shm-usage']});const results=[];
try{for(const width of[1440,390])for(const sport of['skate','ski','mtb','bmx']){
 console.log('Sidebar',sport,width);const page=await browser.newPage({viewport:{width,height:950},hasTouch:width===390,isMobile:width===390});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
 async function visit(query=''){await page.goto(base+'/?sport='+sport+query);const frame=await(await page.waitForSelector('#skateFrame')).contentFrame();await frame.waitForSelector('#discountMin',{state:'attached'});await frame.waitForFunction(()=>document.readyState==='complete');await frame.waitForFunction(()=>document.getElementById('moreCount')!==null);return frame;}
 let frame=await visit();let more=frame.locator('[data-section="more"]');await frame.waitForFunction(()=>document.querySelector('[data-section="more"] > button').getAttribute('aria-expanded')==='false');
 assert.equal(await more.locator('[data-section]').count(),3);
 assert.equal(await frame.locator('[data-section="discount"]').count(),0);
 assert.equal(await frame.locator('[data-section="price"] #discountMin').count(),1);
 assert.equal(await frame.locator('#storeSelect').count(),1);
 assert.equal(await frame.locator('#filterDrawer .show-results').evaluate(n=>n===n.parentElement.lastElementChild),true);
 // Preserve existing section preferences as More gains its own id.
 await page.evaluate(()=>localStorage.setItem('salesscraper2.filterSections',JSON.stringify({discount:true,more:false})));
 frame=await visit('&scoremin=70');more=frame.locator('[data-section="more"]');
 await frame.waitForFunction(()=>document.getElementById('scoreMin').value==='70'&&document.querySelector('[data-section="more"]').classList.contains('is-open'));
 assert.equal(await frame.locator('#moreCount').innerText(),'· 1');
 assert(await frame.locator('[data-section="score"]').evaluate(n=>n.classList.contains('is-open')));
 if(width===390)await frame.locator('#filtersOpen').click();
 await more.locator(':scope > button').click();assert.equal(await more.locator(':scope > button').getAttribute('aria-expanded'),'false');
 assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('salesscraper2.filterSections')).discount),true);
 await page.reload();frame=await(await page.waitForSelector('#skateFrame')).contentFrame();
 await frame.waitForFunction(()=>document.querySelector('[data-section="more"]').classList.contains('is-open'));
 frame=await visit('&discount=30&discountmax=65&scoremin=70&scoremax=95&interval=week');
 await frame.waitForFunction(()=>document.getElementById('discountMin').value==='30'&&document.getElementById('discountMax').value==='65');
 assert(await frame.locator('[data-section="price"]').evaluate(n=>n.classList.contains('is-open')));
 assert.equal(await frame.locator('#scoreMax').inputValue(),'95');
 // Saved snapshots keep exactly the same field/parameter contract.
 const encoded=await frame.evaluate(()=>encodeState(captureState()));const params=new URLSearchParams(encoded);
 for(const[k,v]of Object.entries({discount:'30',discountmax:'65',scoremin:'70',scoremax:'95',interval:'week'}))assert.equal(params.get(k),v);
 await frame.evaluate(()=>{const snapshot=decodeQuery('?scoremin=80');clearFilters();applySnapshot(snapshot);});
 await frame.waitForFunction(()=>document.getElementById('scoreMin').value==='80'&&document.querySelector('[data-section="more"]').classList.contains('is-open'));
 if(width===390)await frame.locator('#filtersOpen').click();
 if(width===1440||width===390)await page.screenshot({path:path.join(out,`${sport}-${width}.png`)});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
 results.push({sport,width,status:'pass'});await page.close();
}fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));}
finally{await browser.close();await new Promise(r=>server.close(r));}})().catch(e=>{console.error(e);process.exitCode=1});
