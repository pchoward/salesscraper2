// Task 12: reuse saved catalogs + the existing Playwright/local-server setup.
const {chromium}=require('playwright'),{serve}=require('./check_topbar.cjs');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const args=process.argv.slice(2),[site,out,before]=args;const capture=args.includes('--capture-before');
const sports={skate:'wheel',bmx:'bikes',ski:'skis',mtb:'suspension'};
function overlaps(a,b){return a.x<b.x+b.width&&b.x<a.x+a.width&&a.y<b.y+b.height&&b.y<a.y+a.height;}
(async()=>{
 fs.mkdirSync(out,{recursive:true});const{server,base}=await serve(site);
 const browser=await chromium.launch({executablePath:process.env.BROWSER_BINARY,args:['--no-sandbox','--disable-dev-shm-usage']});const results=[];
 try{
 for(const [width,height] of [[390,844],[320,640],[1440,950]])for(const [sport,category] of Object.entries(sports)){
  console.log(capture?'Before phone filters':'Phone filters',sport,width);
  const page=await browser.newPage({viewport:{width,height},hasTouch:width<640,isMobile:width<640});
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
  await page.goto(base+'/?sport='+sport+'&type='+category);
  const frame=await(await page.locator('#skateFrame').elementHandle()).contentFrame();
  await frame.waitForFunction(()=>typeof state!=='undefined'&&typeof captureState==='function');
  await page.waitForFunction(()=>!document.getElementById('categoryToggle').disabled);
  if(!capture)await frame.waitForFunction(()=>typeof phoneFilterSheet!=='undefined'&&phoneFilterSheet!==null);
  await frame.locator('#statusCounts').waitFor();
  await page.screenshot({path:path.join(out,`${sport}-${width}-results.png`)});
  if(width===1440){
   const metrics=await frame.evaluate(()=>{
    const out={};for(const selector of ['#filterDrawer','#brandList','#stickyBar .sort-field','#stickyBar .tool-display','#cardGrid .deal-card .product-name']){
     const n=document.querySelector(selector),r=n.getBoundingClientRect(),c=getComputedStyle(n);
     out[selector]={x:r.x,y:r.y,width:r.width,height:r.height,display:c.display,clamp:c.webkitLineClamp};
    }return out;
   });
   if(capture)fs.writeFileSync(path.join(out,sport+'-desktop.json'),JSON.stringify(metrics,null,2));
   else if(before){
    const previous=JSON.parse(fs.readFileSync(path.join(before,sport+'-desktop.json')));
    for(const selector of Object.keys(previous)){
     for(const k of ['x','y','width','height'])assert(Math.abs(metrics[selector][k]-previous[selector][k])<=1,`${sport} desktop ${selector} ${k} changed`);
     assert.equal(metrics[selector].display,previous[selector].display);assert.equal(metrics[selector].clamp,previous[selector].clamp);
    }
   }
   if(!capture){assert.equal(metrics['#cardGrid .deal-card .product-name'].clamp,'2');assert.equal(await frame.locator('#brandList .phone-brand-hidden').count(),0);}
   assert.deepEqual(errors,[]);results.push({sport,width,status:'pass',desktopUnchanged:!capture&&!!before});await page.close();continue;
  }
  const sort=await frame.locator('#sortSelect').boundingBox(),group=await frame.locator('#groupToggle').boundingBox();
  if(!capture){assert(!overlaps(sort,group),'sort and Group across stores must not overlap');assert(await frame.locator('#filtersOpen').isVisible());}
  const browseBefore=page.url();
  const rowsBefore=await frame.locator('.deal-row:not(.filtered-out)').count();
  await frame.locator('#filtersOpen').click();
  await frame.waitForFunction(()=>getComputedStyle(document.getElementById('filterDrawer')).transform==='none');
  if(capture){await page.screenshot({path:path.join(out,`${sport}-${width}-sheet.png`)});await page.close();continue;}
  await page.waitForFunction(()=>document.body.classList.contains('phone-filters-open'));
  const sheet=await frame.locator('#filterDrawer').boundingBox(),embedded=await page.locator('#skateFrame').boundingBox();
  assert(Math.abs(sheet.x)<=1&&Math.abs(sheet.y)<=1&&Math.abs(sheet.width-width)<=1&&Math.abs(sheet.height-height)<=1,'sheet fills frame');
  assert(Math.abs(embedded.x)<=1&&Math.abs(embedded.y)<=1&&Math.abs(embedded.width-width)<=1&&Math.abs(embedded.height-height)<=1,'sheet covers shared header');
  assert(await page.locator('.shell-header').evaluate(n=>n.inert));
  assert(await frame.locator('#filterDrawer').evaluate(n=>n.getAttribute('aria-modal')==='true'));
  const bodyY=await frame.evaluate(()=>scrollY);await frame.evaluate(()=>scrollTo(0,300));assert.equal(await frame.evaluate(()=>scrollY),bodyY,'background window cannot scroll');
  const sheetButton=frame.locator('#filterDrawer .show-results');
  async function countMatches(){await frame.waitForFunction(()=>{
   const n=parseInt(document.getElementById('statusCounts').textContent,10);
   return document.querySelector('#filterDrawer .show-results').textContent==='Show '+n+' '+(n===1?'deal':'deals');
  });}
  await countMatches();
  const firstSections=await frame.locator('#filterDrawer .filter-section:visible').evaluateAll(nodes=>nodes.slice(0,2).map(n=>n.classList.contains('is-open')));assert(firstSections.every(Boolean),'first two sections open by default');
  await page.screenshot({path:path.join(out,`${sport}-${width}-sheet.png`)});
  if(await frame.locator('.phone-brands-more').getAttribute('hidden')!==null)assert.equal(await frame.locator('.phone-brands-more').isVisible(),false,'More must not appear with zero hidden brands');
  const brand=frame.locator('#brandList .facet-value:not([hidden]):not(.phone-brand-hidden):not([data-brand="all"])').first();
  const chosen=await brand.getAttribute('data-brand');await brand.click();await countMatches();
  const have=await frame.evaluate(()=>state.brand);assert.equal(have,chosen);
  assert(await frame.locator('#brandList .facet-value[aria-pressed="true"]').isVisible());
  await page.screenshot({path:path.join(out,`${sport}-${width}-sheet-selected.png`)});
  const expected=await sheetButton.innerText();
  const rowsChosen=await frame.locator('.deal-row:not(.filtered-out)').count();
  await sheetButton.click();
  await frame.waitForFunction(()=>!phoneFilterSheet.isOpen());
  assert.equal(await frame.locator('#statusCounts').innerText(),expected.replace(/^Show /,''));
  assert.equal(await frame.evaluate(()=>state.brand),chosen,'closing preserves live brand');
  assert(!await page.locator('.shell-header').evaluate(n=>n.inert));
  // Closing changed picks must preserve the pre-sheet browse, not replace it.
  const browseChosen=page.url();
  await page.goBack();
  await frame.waitForFunction(n=>typeof state!=='undefined'&&state.brand==='all'&&document.querySelectorAll('.deal-row:not(.filtered-out)').length===n,rowsBefore);
  assert.equal(page.url(),browseBefore);assert(!await frame.evaluate(()=>phoneFilterSheet.isOpen()));
  await page.goForward();
  await frame.waitForFunction(({brand,n})=>typeof state!=='undefined'&&state.brand===brand&&document.querySelectorAll('.deal-row:not(.filtered-out)').length===n,{brand:chosen,n:rowsChosen});
  assert.equal(page.url(),browseChosen);assert(!await frame.evaluate(()=>phoneFilterSheet.isOpen()));

  await frame.locator('#filtersOpen').scrollIntoViewIfNeeded();await frame.locator('#filtersOpen').click();
  await frame.waitForFunction(()=>phoneFilterSheet.isOpen());
  const address=page.url();await page.goBack();await frame.waitForFunction(()=>!phoneFilterSheet.isOpen());
  assert.equal(page.url(),address,'Back closes sheet without leaving catalog');assert.equal(await frame.evaluate(()=>state.brand),chosen);
  // Clear, top-eight ranking/More/search, zero state, and tap targets.
  await frame.locator('#filtersOpen').click();await frame.waitForFunction(()=>phoneFilterSheet.isOpen());await frame.locator('#clearAll').click();
  await countMatches();
  await frame.evaluate(()=>{const list=document.querySelectorAll('#brandList .facet-value:not([data-brand="all"])');window._phoneAuditBrands=[...list].filter(n=>Number(n.dataset.count)>0).map(n=>({brand:n.dataset.brand,count:Number(n.dataset.count)}));});
  const available=await frame.evaluate(()=>_phoneAuditBrands.length);
  if(available>8){
   assert.equal(await frame.locator('#brandList .facet-value:not([hidden]):not(.phone-brand-hidden):not([data-brand="all"])').count(),8);
   await frame.locator('.phone-brands-more').click();
   const extra=frame.locator('#brandList .facet-value:not([hidden]):not(.phone-brand-hidden):not([data-brand="all"])').last();
   const extraName=await extra.getAttribute('data-brand');await extra.click();
   if(await frame.locator('.phone-brands-more').isVisible())await frame.locator('.phone-brands-more').click();
   assert(await frame.locator('#brandList .facet-value[aria-pressed="true"]').isVisible(),'active brands never disappear behind More');
   await frame.locator('#brandSearch').fill(extraName);assert(await frame.locator('#brandList .facet-value[aria-pressed="true"]').isVisible());await frame.locator('#brandSearch').fill('');
  }
  await frame.evaluate(()=>{document.getElementById('priceMax').value='0.01';document.getElementById('priceMax').dispatchEvent(new Event('input',{bubbles:true}));});
  await frame.waitForFunction(()=>document.querySelector('#filterDrawer .show-results').textContent==='Show 0 deals');
  assert(await sheetButton.isDisabled());assert(await frame.locator('#phoneFilterHint').isVisible());
  await frame.locator('#clearAll').click();await countMatches();assert(!await sheetButton.isDisabled());
  const targets=await frame.locator('#filterDrawer .spec-chip:visible,#filterDrawer .width-chip:visible').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().height));assert(targets.every(h=>h>=44));
  await sheetButton.click();await frame.waitForFunction(()=>!phoneFilterSheet.isOpen());
  // Standalone pages use the same sheet without the shell history owner.
  if(sport==='skate'){
   if(width===390){
    const names=await frame.locator('#cardGrid .deal-card .product-name').evaluateAll(nodes=>nodes.map(n=>({clamp:getComputedStyle(n).webkitLineClamp,height:n.clientHeight,line:parseFloat(getComputedStyle(n).lineHeight),overflow:n.scrollHeight>n.clientHeight})));
    assert(names.some(n=>n.clamp==='3'&&n.height>=n.line*3-2&&n.overflow),'a genuinely long real card title has three visible lines');
    assert.equal(await frame.locator('#cardGrid .deal-card .card-store-link').first().getAttribute('title'),await frame.locator('#cardGrid .deal-card').first().getAttribute('data-name'));
   }
   await page.goto(base+'/sale_items_chart.html?type=wheel');
   await page.waitForFunction(()=>typeof phoneFilterSheet!=='undefined'&&phoneFilterSheet!==null);
   await page.locator('#filtersOpen').click();await page.waitForFunction(()=>phoneFilterSheet.isOpen());
   const location=page.url();await page.goBack();await page.waitForFunction(()=>!phoneFilterSheet.isOpen());assert.equal(page.url(),location);
   const initialRows=await page.locator('.deal-row:not(.filtered-out)').count();
   await page.locator('#filtersOpen').click();
   const pick=page.locator('#brandList .facet-value:not([hidden]):not(.phone-brand-hidden):not([data-brand="all"])').first();
   const name=await pick.getAttribute('data-brand');await pick.click();
   await page.waitForFunction(()=>new URLSearchParams(location.search).has('brand'));
   const filteredRows=await page.locator('.deal-row:not(.filtered-out)').count();
   await page.locator('#filterDrawer .show-results').click();await page.waitForFunction(()=>!phoneFilterSheet.isOpen());
   await page.goBack();await page.waitForFunction(n=>typeof state!=='undefined'&&state.brand==='all'&&document.querySelectorAll('.deal-row:not(.filtered-out)').length===n,initialRows);
   assert.equal(page.url(),location);assert(!await page.evaluate(()=>phoneFilterSheet.isOpen()));
   await page.goForward();await page.waitForFunction(({name,n})=>state.brand===name&&document.querySelectorAll('.deal-row:not(.filtered-out)').length===n,{name,n:filteredRows});
   assert(!await page.evaluate(()=>phoneFilterSheet.isOpen()));

  }
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  results.push({sport,width,status:'pass'});fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));await page.close();
 }
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
