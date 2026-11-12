// #212: real category navigation, shared facet counts, no live retailer calls.
const {chromium}=require('playwright');
const {serve}=require('./check_topbar.cjs');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
async function main(){
 const [site,output,before]=process.argv.slice(2);fs.mkdirSync(output,{recursive:true});
 const {server,base}=await serve(site);
 const prior=before?await serve(before):null;
 const browser=await chromium.launch({executablePath:process.env.BROWSER_BINARY,args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 const widths=(process.env.CATEGORY_WIDTHS||'1440,1024,768,430,390,320').split(',').map(Number);
 try{
  for(const width of widths)for(const sport of ['skate','ski','mtb','bmx']){
   console.log('Category navigation',sport,width);
   const page=await browser.newPage({viewport:{width,height:width===320?640:width===390?844:950}});const errors=[];
   page.on('pageerror',e=>errors.push(String(e)));
   await page.route('**/*',r=>[base,prior?.base].includes(new URL(r.request().url()).origin)?r.continue():r.abort());
   const frame=async()=>await(await page.waitForSelector('#skateFrame')).contentFrame();
   async function ready(){
    try { await page.waitForFunction(()=>!document.getElementById('categoryNavigation').hidden&&!document.getElementById('categoryToggle').disabled); }
    catch(error){ console.error('Navigation readiness',sport,width,await page.evaluate(()=>({url:location.href,frame:document.getElementById('skateFrame').contentDocument?.URL,hidden:document.getElementById('categoryNavigation').hidden,choices:document.querySelectorAll('#categoryChoices button').length})),errors);throw error; }
   }
   async function counts(){
    await page.waitForFunction(()=>{
     const source=document.getElementById('skateFrame').contentDocument;
     if(!source?.querySelector('#mainTable'))return false;
     const actual=[...document.querySelectorAll('#categoryChoices button[data-part]')];
     const original=[...source.querySelectorAll('#partFilters button[data-part]')];
     const totals={all:0};for(const row of source.querySelectorAll('#mainTable .deal-row')){
      if(row.dataset.removed==='1')continue;
      totals.all++;totals[row.dataset.part]=(totals[row.dataset.part]||0)+1;
     }
     return actual.length===original.length&&actual.every(button=>original.some(node=>node.dataset.part===button.dataset.part&&Number(button.dataset.count)===(totals[node.dataset.part]||0)&&node.getAttribute('aria-pressed')===button.getAttribute('aria-pressed')));
    });
    const child=await frame();
    const live=await child.locator('.deal-row:not(.filtered-out)').count();
    assert.equal(await page.locator('#categoryChoices button').evaluateAll(nodes=>nodes.filter(n=>Number(n.dataset.count)>0&&n.disabled).length),0,'available navigation categories are never disabled by filters');
    assert.equal(Number(await page.locator('#categoryCount').innerText()),live);
   }
   async function select(part){
    await page.locator('#categoryToggle').click();
    await page.locator('#categoryChoices button[data-part='+JSON.stringify(part)+']').click();
    await ready();const child=await frame();await child.waitForFunction(part=>typeof state!=='undefined'&&state.part===part,part);
    await counts();
   }
   async function input(id,value){
    const child=await frame();
    await child.evaluate(({id,value})=>{const n=document.getElementById(id);n.value=value;n.dispatchEvent(new Event(n.tagName==='SELECT'?'change':'input',{bubbles:true}));},{id,value});
    await child.waitForFunction(({id,value})=>{
     const key={storeSelect:'store',brandSelect:'brand',priceMax:'priceMax',discountMin:'discountMin'}[id];
     const expected=id.endsWith('Select')?value:value===''?null:Number(value);
     return state[key]===expected;
    },{id,value});
    await counts();
   }
   if(prior&&(width===1440||width===390)){
    await page.goto(prior.base+'/?sport='+sport);const old=await frame();await old.waitForSelector('.deal-row',{state:'attached'});
    await old.evaluate(part=>filterByPart(part),({skate:'Wheels',ski:'Skis',mtb:'Suspension',bmx:'Bikes'})[sport]);
    await page.waitForTimeout(150);await page.screenshot({path:path.join(output,`before-${sport}-${width}.png`)});
   }
   if(prior&&sport==='bmx'&&width<=390){
    await page.goto(prior.base+'/?sport=bmx&type=seats-posts&bmx_protects=Wrists%2CElbows&brand=supacaz');
    const old=await frame();await old.waitForFunction(()=>typeof state!=='undefined'&&state.part==='Seats & Posts');
    await page.screenshot({path:path.join(output,`before-stale-${width}.png`)});
    await page.locator('#categoryToggle').click();await page.screenshot({path:path.join(output,`before-menu-${width}.png`)});
   }
   await page.goto(base+'/?sport='+sport);await ready();let child=await frame();await counts();
   assert.equal(await child.locator('#partFilters').isVisible(),false,'duplicate Products row must be hidden');
   assert(await child.locator('#storeFilters').isVisible(),'store chips remain visible');
   await page.locator('#categoryToggle').focus();await page.keyboard.press('ArrowDown');
   assert(await page.locator('#categoryPanel').isVisible());await page.keyboard.press('Escape');
   assert(await page.locator('#categoryToggle').evaluate(n=>n===document.activeElement));
   if(sport==='skate'){
    await page.locator('#shellSearch').fill('wheels');
    await page.waitForFunction(()=>document.getElementById('categoryLabel').textContent==='Search results');
    await counts();
    assert((await child.locator('.deal-row:not(.filtered-out)').evaluateAll(nodes=>nodes.map(n=>n.dataset.part))).every(part=>part==='Wheels'));
    await page.locator('#shellSearch').fill('');
    await page.waitForFunction(()=>document.getElementById('categoryLabel').textContent==='Decks');
    await counts();
   }
   const targets={skate:'Wheels',ski:'Skis',mtb:'Suspension',bmx:'Bikes'};
   const target=targets[sport];
   await select(target);
   if(sport==='skate'){
    assert(await child.locator('#diameterFilters').evaluate(n=>!n.closest('.filter-section').classList.contains('is-type-hidden')),'wheel-specific filters must be active');
    const spec=await child.locator('#diameterFilters .spec-chip:not([hidden])').first().getAttribute('data-value');
    await child.evaluate(value=>toggleSpec('diameters',value),spec);await counts();
   }
   const sample=await child.locator('.deal-row:not(.filtered-out)').first().evaluate(n=>({store:n.dataset.store,brand:n.dataset.brand}));
   await input('storeSelect',sample.store);await input('brandSelect',sample.brand);
   const selectedStore=await child.locator('#storeFilters .quick-chip[aria-pressed=true]').getAttribute('data-count');
   assert.equal(Number(selectedStore),await child.locator('.deal-row:not(.filtered-out)').count());
   await input('priceMax','1');assert.equal(await child.locator('.deal-row:not(.filtered-out)').count(),0);
   assert.equal(await page.locator('#categoryCount').innerText(),'0');
   await input('priceMax','');await input('discountMin','99');await input('discountMin','');
   await page.locator('#shellSearch').fill('zzzz-no-matching-category-product');
   await child.waitForFunction(()=>document.querySelectorAll('.deal-row:not(.filtered-out)').length===0);await counts();
   await page.locator('#shellSearch').fill('');await child.waitForFunction(()=>document.querySelectorAll('.deal-row:not(.filtered-out)').length>0);await counts();
   await child.evaluate(()=>clearFilters());await counts();
   if(sport==='skate'){
    await child.locator('#storeFilters .quick-chip[data-store="Tactics"]').click();
    await child.evaluate(()=>filterByPart('Wheels'));await counts();
    assert.equal(await child.locator('#storeSelect').inputValue(),'Tactics','sidebar category facet still preserves retailer');
    await select('Wheels');
    assert.equal(await child.locator('#storeSelect').inputValue(),'all','top category choice clears retailer selection');
    await child.evaluate(()=>clearFilters());await counts();
   }
   if(sport==='bmx'){
    // #254 primary brief / #255 acceptance: fresh top navigation, deliberate URLs preserved.
    await select('Protection');
    const phone=width<=640;
    if(phone){
     await child.locator('#filtersOpen').click();await child.waitForFunction(()=>phoneFilterSheet?.isOpen());
     const protects=child.locator('[data-technical-field="protects"] .filter-section');
     if(!await protects.evaluate(n=>n.classList.contains('is-open')))await protects.locator(':scope > .section-toggle').click();
     await protects.locator('[data-value="Wrists"]').click();await protects.locator('[data-value="Elbows"]').click();
    }else await child.evaluate(()=>{SportSpecFilters.restore({protects:['Wrists','Elbows']});applyFilters();});
    await page.waitForURL(url=>url.searchParams.has('bmx_protects'));
    await child.waitForFunction(()=>document.querySelectorAll('.deal-row:not(.filtered-out)').length>0);
    const sample=await child.locator('.deal-row:not(.filtered-out)').first().evaluate(n=>({brand:n.dataset.brand,store:n.dataset.store}));
    await input('brandSelect',sample.brand);await input('storeSelect',sample.store);await input('priceMax','1');
    if(phone){
     assert(await child.locator('.show-results').isDisabled(),'zero results can still be exited with Back');
     await child.locator('#filtersClose').click();await child.waitForFunction(()=>!phoneFilterSheet.isOpen());
     await page.waitForURL(url=>url.searchParams.get('max')==='1');
    }
    const priorURL=page.url();
    const priorState=await child.evaluate(()=>({technical:SportSpecFilters.capture(),brand:state.brand,store:state.store,priceMax:state.priceMax}));
    const seatsTotal=Number(await page.locator('#categoryChoices [data-part="Seats & Posts"]').getAttribute('data-count'));
    await select('Seats & Posts');
    assert.equal(await child.locator('.deal-row:not(.filtered-out)').count(),seatsTotal);
    assert.equal((await child.locator('#breadcrumbs').innerText()).replace(/\s+/g,' ').trim(),'BMX Seats & Posts');
    assert.doesNotMatch(await child.locator('#activeChips').innerText(),/Wrists|Elbows|Protects/);
    assert.equal(await child.locator('#brandSelect').inputValue(),'all');
    assert.equal(await child.locator('#storeSelect').inputValue(),'all');
    assert.equal(await child.locator('#priceMax').inputValue(),'');
    assert.equal(new URL(page.url()).searchParams.has('bmx_protects'),false);
    if(width===1440||width===390||width===320)await page.screenshot({path:path.join(output,`fresh-seats-${width}.png`)});
    await page.goBack();await ready();await counts();
    assert.equal(page.url(),priorURL);
    if(phone)assert.equal(await child.evaluate(()=>phoneFilterSheet.isOpen()),false,'category Back restores filters without reopening an old sheet');
    assert.deepEqual(await child.evaluate(()=>({technical:SportSpecFilters.capture(),brand:state.brand,store:state.store,priceMax:state.priceMax})),priorState);
    assert.match(await child.locator('#breadcrumbs').innerText(),/Wrists/);
    if(width<=390)await page.screenshot({path:path.join(output,`restored-protection-${width}.png`)});
    await page.goForward();await ready();await counts();
    const supacaz=await child.evaluate(()=>{const node=document.getElementById('brandSelect');return Array.from(node._facetPool||node.options).find(o=>o.value.toLowerCase()==='supacaz')?.value;});
    assert(supacaz,'catalog has the reported Supacaz brand');await input('brandSelect',supacaz);
    await select('Bikes');
    assert.equal(await child.locator('#brandSelect').inputValue(),'all','seats brand cannot constrain bike navigation');
    // Direct legacy/saved-view state remains serialized even when its dimension is dormant.
    await page.goto(base+'/?sport=bmx&type=seats-posts&bmx_protects=Wrists%2CElbows&brand=supacaz');
    await ready();await counts();child=await frame();
    assert.deepEqual(await child.evaluate(()=>SportSpecFilters.capture().protects),['Wrists','Elbows']);
    assert.doesNotMatch(await child.locator('#breadcrumbs').innerText(),/Wrists|Elbows/);
    assert.doesNotMatch(await child.locator('#activeChips').innerText(),/Protects|Wrists|Elbows/);
    assert.match(await child.evaluate(()=>encodeState(captureState())),/bmx_protects=Wrists%2CElbows/);
    if(width<=390){
     await page.screenshot({path:path.join(output,`after-stale-${width}.png`)});
     await page.locator('#categoryToggle').click();await page.screenshot({path:path.join(output,`after-menu-${width}.png`)});
     await page.locator('#categoryClose').click();
    }
    const saved=await child.evaluate(()=>encodeState(captureState()));
    await child.evaluate(query=>{applySnapshot(decodeQuery(query));},saved);
    await counts();
    assert.equal(await child.locator('.deal-row:not(.filtered-out)').count(),1);
    await child.evaluate(()=>filterByPart('Protection'));
    assert.match(await child.locator('#activeChips').innerText(),/Wrists/,'sidebar restores applicability without destroying mixed state');
    await child.evaluate(()=>clearFilters());await counts();
   }
   await select(target);
   const slug=await child.evaluate(part=>typeSlug(part),target);
   await page.waitForURL(url=>url.searchParams.get('type')===slug);
   await select('all');
   await page.goBack();await ready();await counts();
   assert.equal(await page.locator('#categoryChoices button[aria-pressed=true]').getAttribute('data-part'),target);
   await page.goForward();await ready();await counts();
   assert.equal(await page.locator('#categoryChoices button[aria-pressed=true]').getAttribute('data-part'),'all');
   await select(target);
   if(width===1440||width===390)await page.screenshot({path:path.join(output,`after-${sport}-${width}.png`)});
   await page.locator('#categoryToggle').click();
   assert(await page.locator('#categoryPanel').isVisible());
   if(width===768&&sport==='skate'){
    await page.setViewportSize({width,height:420});
    await page.waitForFunction(()=>document.getElementById('categoryPanel').getBoundingClientRect().bottom<=innerHeight);
    await page.setViewportSize({width,height:950});
   }
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(width===1440||width===390)await page.screenshot({path:path.join(output,`menu-${sport}-${width}.png`)});
   const next=sport==='ski'?'mtb':'ski';
   await page.locator('#sport-'+next).click();await ready();await counts();
   assert(!(new URL(page.url())).searchParams.has('type'),'sport changes clear the category');
   assert.equal(await page.locator('#categoryPanel').isVisible(),false);
   assert.match(await page.locator('#categoryTitle').innerText(),new RegExp(next==='mtb'?'MTB':'Ski'));
   assert.deepEqual(errors,[]);
   results.push({sport,width,status:'pass'});fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));await page.close();
  }
  console.log(JSON.stringify(results));
 }finally{await browser.close();await new Promise(r=>server.close(r));if(prior)await new Promise(r=>prior.server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
