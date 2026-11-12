// Real catalog OR filtering, counts, removable choices, saved views and history.
const {chromium}=require('playwright'),{serve}=require('./check_topbar.cjs');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const [site,out,before]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});
 const {server,base}=await serve(site),baseline=before?await serve(before):null;
 const browser=await chromium.launch({executablePath:process.env.BROWSER_BINARY,args:['--no-sandbox','--disable-dev-shm-usage']});const results=[];
 try{for(const width of [1440,390,320])for(const sport of ['skate','bmx','ski','mtb']){
  console.log('Multi-store',sport,width);
  const page=await browser.newPage({viewport:{width,height:width===320?640:844},isMobile:width<641,hasTouch:width<641});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',r=>[base,baseline?.base].includes(new URL(r.request().url()).origin)?r.continue():r.abort());
  const url='/?sport='+sport+'&type=all';
  async function visit(href=base+url){
   await page.goto(href);const frame=await(await page.locator('#skateFrame').elementHandle()).contentFrame();
   await frame.waitForFunction(()=>typeof state!=='undefined'&&typeof applyFilters==='function'&&state.part==='all');return frame;
  }
  async function stores(frame){
   if(width<641){await frame.locator('#filtersOpen').click();await frame.waitForFunction(()=>phoneFilterSheet.isOpen());}
   await frame.evaluate(()=>paintFilterSection(document.querySelector('[data-section="store"]'),true));
   await frame.locator('[data-section="store"]').scrollIntoViewIfNeeded();
  }
  if(baseline&&width!==320){const old=await visit(baseline.base+url);await stores(old);await page.screenshot({path:path.join(out,`${sport}-${width}-before.png`)});}
  let frame=await visit();
  const all=await frame.locator('.deal-row').evaluateAll(nodes=>nodes.map(n=>({id:n.id,store:n.dataset.store,part:n.dataset.part,brand:n.dataset.brand,price:Number(n.dataset.price)})));
  const names=[...new Set(all.map(r=>r.store))];assert(names.length>=2,'catalog needs at least two stores');
  const chosen=sport==='skate'&&names.includes('CCS')&&names.includes('Tactics')?['CCS','Tactics']:names.sort((a,b)=>all.filter(r=>r.store===b).length-all.filter(r=>r.store===a).length).slice(0,2);
  const expected=all.filter(r=>chosen.includes(r.store)).map(r=>r.id).sort();
  await stores(frame);
  // Use actual pointer/keyboard controls, not filter state mutations.
  const selector=name=>'#storeList button[data-store='+JSON.stringify(name)+']';
  await frame.locator(selector(chosen[0])).click();
  if(width===320){await frame.locator(selector(chosen[1])).focus();await frame.locator(selector(chosen[1])).press('Space');}
  else await frame.locator(selector(chosen[1])).click();
  assert.deepEqual(await frame.locator('.deal-row:not(.filtered-out)').evaluateAll(nodes=>nodes.map(n=>n.id).sort()),expected);
  assert.equal(await frame.locator('#storeList [aria-pressed="true"]').count(),2);
  assert.equal(await frame.locator('#storeFilters [aria-pressed="true"]').count(),2);
  // Counts describe each store under the other filters, rather than the union.
  for(const name of chosen)assert.equal(await frame.locator(selector(name)).getAttribute('data-count'),String(all.filter(r=>r.store===name).length));
  if(width!==320){
   if(width<641)await frame.evaluate(()=>{
    const body=document.querySelector('.phone-filter-body'),section=document.querySelector('[data-section="store"]');
    body.scrollTop+=section.getBoundingClientRect().top-body.getBoundingClientRect().top-8;
   });
   await page.screenshot({path:path.join(out,`${sport}-${width}-after.png`)});
  }
  if(width<641){await frame.locator('#filterDrawer .show-results').click();await frame.waitForFunction(()=>!phoneFilterSheet.isOpen());}
  await page.waitForFunction(()=>new URL(location.href).searchParams.get('store')?.includes(','));
  const shared=page.url(),query=await frame.evaluate(()=>currentQuery());
  const params=new URL(shared).searchParams;assert.equal(params.get('store').split(',').length,2);
  // Reload/bookmarks and old saved-view shape round-trip the same query string.
  await page.reload();frame=await(await page.locator('#skateFrame').elementHandle()).contentFrame();
  await frame.waitForFunction(()=>typeof selectedStores==='function'&&selectedStores().length===2);
  assert.deepEqual(await frame.locator('.deal-row:not(.filtered-out)').evaluateAll(nodes=>nodes.map(n=>n.id).sort()),expected);
  await frame.evaluate(query=>{writeJson(VIEWS_KEY,[{id:'multi-store-qa',name:'Two stores',query}]);clearFilters();applySnapshot(decodeQuery(customViews()[0].query));},query);
  assert.equal(await frame.evaluate(()=>currentQuery()),query);
  // Remove only one store using the real active chip; keep the other.
  await frame.getByRole('button',{name:'Remove Store: '+chosen[0],exact:true}).click();
  await frame.waitForFunction(()=>selectedStores().length===1);
  assert.equal(await frame.evaluate(()=>selectedStores()[0]),chosen[1]);
  assert.equal(await frame.locator('.deal-row:not(.filtered-out)').count(),all.filter(r=>r.store===chosen[1]).length);
  await page.goBack();await frame.waitForFunction(()=>typeof selectedStores==='function'&&selectedStores().length===2);
  assert.deepEqual(await frame.locator('.deal-row:not(.filtered-out)').evaluateAll(nodes=>nodes.map(n=>n.id).sort()),expected);
  await page.goForward();await frame.waitForFunction(()=>typeof selectedStores==='function'&&selectedStores().length===1);
  // Category + brand + price + search + sort still narrow the chosen stores.
  await frame.evaluate(query=>applySnapshot(decodeQuery(query)),query);
  const sample=all.find(r=>chosen.includes(r.store)&&r.brand&&Number.isFinite(r.price));assert(sample);
  await frame.evaluate(sample=>{
   filterByPart(sample.part);setSelect('brandSelect',sample.brand);
   document.getElementById('priceMax').value=sample.price;
   document.getElementById('sortSelect').value='price';applySortChoice();applyFilters();
  },sample);
  const matching=all.filter(r=>chosen.includes(r.store)&&r.part===sample.part&&r.brand===sample.brand&&r.price<=sample.price).map(r=>r.id).sort();
  assert.deepEqual(await frame.locator('.deal-row:not(.filtered-out)').evaluateAll(nodes=>nodes.map(n=>n.id).sort()),matching);
  // Technical picks remain ANDed with the OR store selection.
  await frame.evaluate(()=>{
   const chip=[...document.querySelectorAll('.spec-chip,.tech-chip,.width-chip')].find(n=>Number(n.dataset.count)>0&&n.closest('.filter-section')?.getClientRects().length);
   if(chip){paintFilterSection(chip.closest('.filter-section'),true);chip.click();}
  });
  assert.equal(await frame.evaluate(()=>selectedStores().length),2);
  const technicalRows=await frame.locator('.deal-row:not(.filtered-out)').evaluateAll(nodes=>nodes.map(n=>n.id));
  assert(technicalRows.every(id=>matching.includes(id)),'technical picks cannot expand beyond the other filters');

  await frame.evaluate(()=>{document.getElementById('searchInput').value='zzzz-no-store-test-match';applyFilters();});
  assert.equal(await frame.locator('.deal-row:not(.filtered-out)').count(),0);
  await stores(frame);
  for(const name of chosen){assert(await frame.locator(selector(name)).isVisible(),'selected zero-count stores remain removable');assert.equal(await frame.locator(selector(name)).getAttribute('aria-pressed'),'true');}
  await frame.locator(selector(chosen[0])).click();assert.equal(await frame.evaluate(()=>selectedStores().length),1);
  await frame.locator(selector('all')).click();assert.equal(await frame.evaluate(()=>state.store),'all');
  await frame.locator('#clearAll').click();
  const resetPart=await frame.evaluate(()=>state.part);
  assert.equal(await frame.locator('.deal-row:not(.filtered-out)').count(),all.filter(r=>resetPart==='all'||r.part===resetPart).length);
  if(width<641){await frame.locator('#filtersClose').click();await frame.waitForFunction(()=>!phoneFilterSheet.isOpen());}
  // A legacy single-store bookmark still selects exactly one retailer.
  const legacy=new URL(base+url);legacy.searchParams.set('store',await frame.evaluate(name=>storeSlug(name),chosen[0]));
  frame=await visit(legacy.href);assert.equal(await frame.evaluate(()=>selectedStores().length),1);
  assert.equal(await frame.locator('.deal-row:not(.filtered-out)').count(),all.filter(r=>r.store===chosen[0]).length);
  const top=frame.locator('#storeFilters [data-store='+JSON.stringify(chosen[0])+']');
  await top.click();assert.equal(await frame.evaluate(()=>state.store),'all');
  await top.click();assert.equal(await frame.evaluate(()=>selectedStores()[0]),chosen[0]);

  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  results.push({sport,width,status:'pass'});fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));await page.close();
 }console.log(JSON.stringify(results));}finally{await browser.close();await new Promise(r=>server.close(r));if(baseline)await new Promise(r=>baseline.server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
