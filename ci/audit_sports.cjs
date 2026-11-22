// Four-sport acceptance coverage, reusing the topbar preview server/Playwright.
// node ci/audit_sports.cjs PREVIEW_DIR OUTPUT_DIR
const {serve} = require('./check_topbar.cjs');
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const [site, output] = process.argv.slice(2);
const results = [];
async function check(sport,width,name,fn) {
    try { const detail=await fn(); results.push({sport,width,name,status:'pass',detail}); }
    catch(error) { results.push({sport,width,name,status:'fail',detail:error.message}); }
    console.log(sport,width,name,results[results.length-1].status,results[results.length-1].detail||'');
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2)+'\n');
}
const rows = frame => frame.evaluate(() => [...document.querySelectorAll('.deal-row:not(.filtered-out)')].map(n=>({...n.dataset,price:String(rowPrice(n)),discount:String(rowDiscount(n))})));
async function control(frame,id,value) {
    const isSelect=await frame.evaluate(({id,value})=>{
        const node=document.getElementById(id);
        node.value=value;
        const isSelect=node.tagName==='SELECT';
        node.dispatchEvent(new Event(isSelect?'change':'input',{bubbles:true}));
        return isSelect;
    },{id,value});
    if(!isSelect) await frame.waitForFunction(({id,value})=>state[id]===(value===''?null:Number(value)),{id,value});
}
async function technical(frame,key,value,mobile) {
    if(mobile && !await frame.locator('#filterDrawer').evaluate(n=>n.classList.contains('is-open'))) await frame.locator('#filtersOpen').click();
    const section=frame.locator(`[data-technical-field="${key}"] .section-toggle`);
    if(await section.getAttribute('aria-expanded')!=='true') await section.click();

    await frame.locator(`.tech-chip[data-tech-key="${key}"]`).filter({has:frame.locator('span.spec-label',{hasText:new RegExp('^'+value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'$')})}).click();
    await frame.waitForTimeout(180);
    if(mobile) await frame.locator('#filtersClose').click();
}
async function main(){
 fs.mkdirSync(output,{recursive:true});const {server,base}=await serve(site);
 const browser=await chromium.launch({headless:true,...(process.env.BROWSER_BINARY?{executablePath:process.env.BROWSER_BINARY}:{}),args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const width of (process.env.AUDIT_WIDTHS === 'fixtures' ? [] : (process.env.AUDIT_WIDTHS||'1440,1024,768,430,390').split(',').map(Number))) for(const sport of ['skate','bmx','ski','mtb']){
    const mobile=width<=800;
    const errors=[];
    let page,frame;
    // A failed assertion can leave URL, drawer, or watch state behind. Give
    // each scenario a fresh document and storage, including after failures.
    const scenario=(name,fn)=>check(sport,width,name,async()=>{
     page=await browser.newPage({viewport:{width,height:mobile?900:1000},isMobile:mobile,hasTouch:mobile});
     page.setDefaultTimeout(5000);
     page.on('pageerror',e=>errors.push(e.stack || String(e)));
     try{
      await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
      await page.goto(base+'/?sport='+sport,{waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>{
       const catalog=document.getElementById('skateFrame')?.contentDocument;
       return catalog?.shredCatalogReady && document.getElementById('categoryToggle')?.disabled===false;
      },undefined,{timeout:30000});
      frame=await(await page.waitForSelector('#skateFrame')).contentFrame();
      return await fn();
     }finally{
      await page.close();
     }
    });
    await scenario('Layout and active sport',async()=>{
     if(width===1440||width===390) await page.screenshot({path:path.join(output,`${sport}-${width===1440?'desktop':'mobile'}.png`),animations:'disabled'});
     assert.equal(await page.locator('#sport-'+sport).getAttribute('aria-selected'),'true');
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
     assert(await frame.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
     assert.equal(await frame.locator('.topnav').isVisible(),false);
     const stores=await frame.evaluate(()=>({
      options:[...document.querySelectorAll('#storeSelect option')].map(n=>n.value).sort(),
      inline:[...document.querySelectorAll('#storeFilters .quick-row > button[data-store]')].map(n=>n.dataset.store).sort()
     }));
     // An ineligible zero-count store can retain a hidden chip but have no select option.
     assert.deepEqual(stores.inline.filter(store=>stores.options.includes(store)),stores.options,'eligible stores must be inline by default on every sport');
     const buttons=await page.locator('.catalog-sections button').evaluateAll(ns=>ns.map(n=>{const r=n.getBoundingClientRect();return {x:r.left,right:r.right,y:r.top,bottom:r.bottom}}));
     assert(buttons.every(r=>r.x>=0&&r.right<=width+1));
     assert(buttons.every((r,i)=>buttons.slice(i+1).every(b=>r.right<=b.x+1||r.bottom<=b.y+1||b.right<=r.x+1||b.bottom<=r.y+1)));
     return {rows:(await rows(frame)).length};
    });
    await scenario('Capabilities are honest',async()=>{
     const supported=sport==='skate';
     assert.equal(await page.locator('[data-catalog-control="navAlerts"]').isDisabled(),!supported);
     const alerts=await frame.locator('.card-alert:visible').count();assert.equal(alerts>0,supported);
     assert(await frame.locator('.star:visible').count()>0,'local Watch remains usable');
    });
    const category={skate:'Decks',bmx:'Frames & Forks',ski:'Skis',mtb:'Suspension'}[sport];
    await scenario('Category, store, brand, search, sort and ranges',async()=>{
     await control(frame,'partSelect',category);
     const baseRows=await rows(frame);assert(baseRows.length>0);assert(baseRows.every(r=>r.part===category));
     const sample=baseRows[0];
     await control(frame,'storeSelect',sample.store);await control(frame,'brandSelect',sample.brand);
     await page.locator('#shellSearch').fill(sample.brand);
     // The shell forwards search to the iframe, which filters on a debounce.
     // Its URL update is sent back only after the results have been rendered.
     await page.waitForURL(url=>url.searchParams.get('q')===sample.brand,{timeout:30000});
     const live=await rows(frame);assert(live.length>0);assert(live.every(r=>r.part===category&&r.store===sample.store&&r.brand.toLowerCase()===sample.brand.toLowerCase()));
     await frame.locator('#sortSelect').selectOption('price');
     const prices=(await rows(frame)).map(r=>Number(r.price));assert.deepEqual(prices,[...prices].sort((a,b)=>a-b));
     await control(frame,'priceMax','1');await frame.locator('#emptyState').waitFor({state:'visible'});assert.equal((await rows(frame)).length,0);
     await frame.evaluate(()=>clearFilters());
     await control(frame,'partSelect',category);await control(frame,'discountMin','99');
     assert((await rows(frame)).every(r=>Number(r.discount)>=99));
    });
    if(sport==='skate') await scenario('Deck width plus independent brand/store choices',async()=>{
     await control(frame,'partSelect',category);
     if(mobile)await frame.locator('#filtersOpen').click();
     const chip=frame.locator('#sizeFilters .width-chip[data-buckets*="8.5-8.75"]').first();
     await chip.click();if(mobile)await frame.locator('#filtersClose').click();
     let live=await rows(frame);assert(live.length>0);assert(live.every(r=>r.part==='Decks'&&Number(r.size)>=8.5&&Number(r.size)<8.75));
     const sample=live[0];await control(frame,'storeSelect',sample.store);await control(frame,'brandSelect',sample.brand);
     live=await rows(frame);assert(live.length>0);assert(live.every(r=>r.store===sample.store&&r.brand===sample.brand&&Number(r.size)>=8.5&&Number(r.size)<8.75));
    });
    if(sport!=='skate') await scenario('Technical combinations and variant price oracle',async()=>{
     await control(frame,'partSelect',category);
     const config=await frame.locator('#technicalCatalog').evaluate(n=>JSON.parse(n.textContent));
     const preferred={bmx:['wheel_size','22'],ski:['length','170–179 cm'],mtb:['wheel_size','29']}[sport];
     const field=config.fields.find(f=>f.key===preferred[0]);assert(field&&field.values.includes(preferred[1]));
     await technical(frame,field.key,preferred[1],mobile);
     let selection=await frame.evaluate(()=>SportSpecFilters.capture());
     const original=await frame.evaluate(()=>[...document.querySelectorAll('.deal-row')].filter(r=>r.dataset.part===document.getElementById('partSelect').value&&r.dataset.removed!=='1').map(r=>({...r.dataset})));
     function oracle(selected){return original.flatMap(row=>{
      const item=config.items[row.url];const fields=config.fields.filter(f=>selected[f.key]&&(!f.categories?.length||f.categories.includes(row.part)));
      const offers=(item?.offers||[]).filter(o=>o.available!==false&&fields.every(f=>(o.specs?.[f.key]||[]).some(v=>(Array.isArray(selected[f.key])?selected[f.key]:[selected[f.key]]).includes(v))));
      if(!offers.length)return [];const best=offers.reduce((a,b)=>Number(a.price)<=Number(b.price)?a:b);return [{id:row.id,price:Number(best.price)}];});}
     let expected=oracle(selection);let actual=await rows(frame);assert.deepEqual(actual.map(r=>r.id).sort(),expected.map(r=>r.id).sort());
     for(const row of actual)assert.equal(Number(row.price),expected.find(x=>x.id===row.id).price);
     const brand=sport==='ski'?'Armada':(actual[0]?.brand||'all');
     if(brand!=='all'){
      await control(frame,'brandSelect',brand);
      const ids=new Set(original.filter(r=>r.brand.toLowerCase()===brand.toLowerCase()).map(r=>r.id));
      assert.deepEqual((await rows(frame)).map(r=>r.id).sort(),expected.filter(r=>ids.has(r.id)).map(r=>r.id).sort());
      await control(frame,'brandSelect','all');
     }
     // Native controls debounce URL writes; a sport menu can also load another
     // catalog in the background. Wait for committed state, not a fixed delay.
     await page.waitForFunction(()=>{
      const child=document.getElementById('skateFrame').contentWindow;
      if(typeof child.encodeState!=='function')return false;
      const actual=new URL(location.href).searchParams;actual.delete('sport');
      return actual.toString()===child.encodeState(child.captureState());
     });
     const savedTechnicalURL=page.url();
     const nextSport=sport==='ski'?'bmx':'ski';
     await page.locator('#sport-'+nextSport).click();
     await page.waitForURL(url=>url.searchParams.get('sport')===nextSport);
     for(const f of config.fields)assert.equal(new URL(page.url()).searchParams.has(f.param),false,'technical parameters must not leak between sports');
     await page.goBack();await page.waitForURL(savedTechnicalURL);
     frame=await(await page.waitForSelector('#skateFrame')).contentFrame();
     await frame.waitForFunction(expected=>typeof SportSpecFilters!=='undefined'&&JSON.stringify(SportSpecFilters.capture())===JSON.stringify(expected),selection);
     assert.equal(page.url(),savedTechnicalURL);assert.deepEqual(await frame.evaluate(()=>SportSpecFilters.capture()),selection);
     const chips=await frame.locator('#activeChips').textContent();assert(chips.includes(preferred[1]),'technical choice must appear in removable active filters');
     // A second scoped field combines with AND on one offer. Counts are live
     // (as on Skate), so options and fields with no match under the first pick
     // are hidden: pick a value that is still offered.
     const second=await frame.evaluate(first=>{
      for(const section of document.querySelectorAll('[data-technical-field]')){
       const key=section.dataset.technicalField;
       if(key===first||section.hidden||section.style.display==='none')continue;
       const chip=[...section.querySelectorAll('.tech-chip')].find(c=>c.dataset.value&&!c.hidden&&Number(c.dataset.count)>0);
       if(chip)return {key,value:chip.dataset.value};
      }
      return null;
     },field.key);
     if(second){await technical(frame,second.key,second.value,mobile);selection=await frame.evaluate(()=>SportSpecFilters.capture());expected=oracle(selection);actual=await rows(frame);assert.deepEqual(actual.map(r=>r.id).sort(),expected.map(r=>r.id).sort());}
     await frame.evaluate(()=>clearFilters());assert.deepEqual(await frame.evaluate(()=>SportSpecFilters.capture()),{});
    });
    await scenario('Quick View, retailer-first links, chart and Watch',async()=>{
     const card=frame.locator('#cardGrid .deal-card:not(.filtered-out):not(.grouped-hide)').first();
     if(width<=640){
      const layout=await card.evaluate(node=>{
       const rect=selector=>node.querySelector(selector)?.getBoundingClientRect();
       const photo=rect('.card-photo'),quick=rect('.card-quick'),store=rect('.store-mark');
       const alert=rect('.card-alert'),star=rect('.star');
       return {photoBottom:photo.bottom,quickTop:quick.top,quickHeight:quick.height,
        storeBottom:store.bottom, quickLeft:quick.left, alertRight:alert?.right || 0,
        alertTop:alert?.height?alert.top:quick.top, starTop:star.top, starRight:star.right};
      });
      assert(layout.quickTop>=layout.photoBottom&&layout.quickHeight>=36);
      assert(layout.quickTop>=layout.storeBottom,'Quick View does not cover the retailer');
      assert(layout.alertTop===layout.quickTop&&layout.starTop===layout.quickTop);
      assert(Math.max(layout.alertRight,layout.starRight)<=layout.quickLeft);
     }
     assert.equal(await frame.locator('#searchInput').getAttribute('aria-expanded'),'false');
     await card.hover();const dataset=await card.evaluate(n=>({...n.dataset}));
     const link=card.locator('.card-store-link');assert.equal(await link.getAttribute('href'),dataset.url);assert.equal(await link.getAttribute('target'),'_blank');
     await card.locator('.card-quick').click();await frame.waitForSelector('#quickView:not([hidden])');
     assert((await frame.locator('#quickView').textContent()).includes(dataset.name));
     assert((await frame.locator('#quickView .quick-price').textContent()).includes(Number(dataset.price).toFixed(2)));
     const links=await frame.locator('#quickView a').evaluateAll(ns=>ns.filter(n=>n.href.startsWith('http')).map(n=>({href:n.href,target:n.target})));
     assert(links.some(l=>l.href===dataset.url&&l.target==='_blank'));
     assert(await frame.locator('#quickView .history-chart').count()>0||/No tracked|one tracked/i.test(await frame.locator('#quickView').textContent()));
     await page.goBack();await frame.waitForSelector('#quickView[hidden]',{state:'attached'});
     await card.locator('.star').click();assert.equal(await card.locator('.star').getAttribute('aria-pressed'),'true');await card.locator('.star').click();
    });
    await scenario('Grouping, layout, empty deal types and drawer',async()=>{
     assert.equal(await frame.locator('#cardPool .deal-card').count(),0);
     assert(await frame.evaluate(()=>lazyCardMarkup.size>0),'the catalog has unparsed cards');
     assert.equal(await frame.locator('#mainTable tbody td').count(),0);

     if(width<=640)await frame.locator('#filtersOpen').click();
     await frame.locator('#groupToggle').click();assert.equal(await frame.locator('#groupToggle').getAttribute('aria-pressed'),'true');await frame.locator('#groupToggle').click();
     if(mobile){if(width>640)await frame.locator('#filtersOpen').click();assert(await frame.locator('#filterDrawer').evaluate(n=>n.classList.contains('is-open')));await frame.waitForTimeout(300);
      const drawer=await frame.locator('#filterDrawer').evaluate(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,width:innerWidth,small:[...n.querySelectorAll('button')].filter(b=>b.getClientRects().length&&b.getBoundingClientRect().height<24).map(b=>b.getAttribute('aria-label')||b.textContent.trim())};});
      assert(drawer.left>=-1&&drawer.right<=drawer.width+1,'drawer must finish inside the phone viewport');
      assert.deepEqual(drawer.small,[],'visible drawer buttons must be at least 24px tall');
      if(width===390)await page.screenshot({path:path.join(output,sport+'-mobile-filters.png'),animations:'disabled'});await frame.locator('#filtersClose').click();}
     else{
      await frame.locator('#layoutTable').click();
      assert(await frame.locator('.table-wrap').isVisible());
      assert(await frame.locator('#mainTable tbody td').count()>0);
      assert.equal(await frame.locator('#tableRows').count(),0);
      await frame.locator('#layoutCards').click();
      assert(await frame.locator('#cardGrid .deal-card:not(.filtered-out)').first().isVisible());
     }
     await frame.locator('#btnNew').click();assert((await rows(frame)).every(r=>r.added==='1'&&r.removed!=='1'));await frame.locator('#btnGone').click();assert((await rows(frame)).every(r=>r.removed==='1'));await frame.locator('#btnAll').click();assert((await rows(frame)).every(r=>r.removed!=='1'));
    });
    await scenario('Back/Forward and cross-sport state isolation',async()=>{
     // Each step waits for its own result (URL, restored search, rows), not a
     // fixed delay: slower CI runners made the fixed 250-400 ms waits flaky.
     const until=async(test,what,limit=10000)=>{const end=Date.now()+limit;let last;
      while(Date.now()<end){try{last=await test();if(last)return last;}catch(e){last=e.message;}await page.waitForTimeout(100);}
      throw new Error('Timed out waiting for '+what+' (last: '+last+')');};
     await page.locator('#shellSearch').fill('audit-no-such-product-zzzz');
     await until(async()=>(await rows(frame)).length===0,'the search to empty the list');
     // The page writes the search into the URL a moment after typing; capture
     // the URL only once it holds it (the old fixed 250 ms raced this).
     await until(()=>new URL(page.url()).searchParams.get('q')==='audit-no-such-product-zzzz','the search in the URL');
     const url=page.url();const next=sport==='ski'?'bmx':'ski';
     await page.locator('#sport-'+next).click();
     await until(()=>new URL(page.url()).searchParams.get('sport')===next,'the '+next+' tab');
     await page.goBack();
     await until(()=>page.url()===url,'Back to '+sport);
     frame=await(await page.waitForSelector('#skateFrame')).contentFrame();await frame.waitForSelector('#searchInput',{state:'attached'});
     await until(async()=>(await frame.locator('#searchInput').inputValue())==='audit-no-such-product-zzzz','the search to be restored');
     assert.equal(page.url(),url);
     await page.goForward();
     await until(()=>new URL(page.url()).searchParams.get('sport')===next,'Forward to '+next);
    });
    await check(sport,width,'No browser errors',async()=>assert.deepEqual(errors,[]));
  }
  const fixturePath=path.join(site,'audit-fixtures','manifest.json');
  if(process.env.AUDIT_FIXTURES!=='off'&&fs.existsSync(fixturePath)) {
   const fixtures=JSON.parse(fs.readFileSync(fixturePath));
   for(const width of [1440,390]) for(const [sport,fixture] of Object.entries(fixtures)) {
    await check(sport,width,'Technical sidebar order follows heading ranks when present',async()=>{
     const phone=width===390;
     const page=await browser.newPage({viewport:{width,height:900},isMobile:phone,hasTouch:phone});
     try{
      await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
      await page.goto(base+'/'+fixture.path);
      const fields='#contextSpecs > [data-technical-field]';
      const order=selector=>page.locator(selector).evaluateAll(nodes=>nodes.map(node=>node.dataset.technicalField));
      const built=await page.locator('#technicalCatalog').evaluate(node=>JSON.parse(node.textContent).fields.map(field=>field.key));
      await page.evaluate(()=>filterByPart('all'));
      assert.deepEqual(await order(fields),built);
      if(sport!=='ski'){
       await control(page, 'partSelect', fixture.part);
       assert.equal(await page.locator(fields+'[data-rank]').count(),0);
       assert.deepEqual(await order(fields),built);
       return;
      }
      if(phone)await page.locator('#filtersOpen').click();
      for(const [heading,wanted] of [
       ['Boots',['mondo','gender','flex','last']],
       ['Bindings',['din','brake','gender']],
       ['Goggles',['gender','goggle_size']],
      ]){
       await control(page,'partSelect',heading);
       assert.deepEqual((await order(fields+':visible')).slice(0,wanted.length),wanted);
       assert.equal(await page.locator('#contextSpecs').evaluate(node=>node.previousElementSibling.dataset.section),'brand');
      }
      await page.evaluate(()=>filterByPart('Packs'));
      assert.deepEqual(await order(fields),built);
      await control(page,'partSelect','Boots');
      assert.deepEqual((await order(fields+':visible')).slice(0,4),['mondo','gender','flex','last']);
      const mondo=page.locator('[data-technical-field="mondo"]');
      const toggle=mondo.locator('.section-toggle');
      const count=await mondo.locator('.tech-chip[data-value=""]').getAttribute('data-count');
      assert.equal(count,'1');
      const nextExpanded=String(await toggle.getAttribute('aria-expanded')==='false');
      await toggle.click();
      assert.equal(await toggle.getAttribute('aria-expanded'),nextExpanded);
      await control(page,'partSelect','Bindings');
      await control(page,'partSelect','Boots');
      assert.equal(await toggle.getAttribute('aria-expanded'),nextExpanded);
      assert.equal(await mondo.locator('.tech-chip[data-value=""]').getAttribute('data-count'),count);
      await page.evaluate(()=>filterByPart('all'));
      assert.deepEqual(await order(fields),built);
     }finally{await page.close();}
    });
    if(sport==='mtb') await check(sport,width,'MTB Motor quick filters share facet counts and history',async()=>{
     const page=await browser.newPage({viewport:{width,height:900},isMobile:width<800,hasTouch:width<800});
     try{
      await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
      await page.goto(base+'/'+fixture.path+'?type=bikes');
      const bar=page.locator('#mtbPowerChips');
      await bar.waitFor({state:'visible'});
      for(const [value,count] of [['',2],['E-MTB',1],['Regular',1]]){
       assert.equal(await bar.locator(`[data-value="${value}"]`).getAttribute('data-count'),String(count));
       assert.equal(await page.locator(`#tech-power [data-value="${value}"]`).getAttribute('data-count'),String(count));
      }
      await bar.locator('[data-value="E-MTB"]').click();
      await page.waitForURL(url=>url.searchParams.get('mtb_motor')==='E-MTB');
      assert.deepEqual((await rows(page)).map(row=>row.url),['https://example.test/mtb/bike-0']);
      assert.equal(await page.locator('#tech-power [data-value="E-MTB"]').getAttribute('aria-pressed'),'true');
      await page.goBack();
      await page.waitForFunction(()=>document.querySelector('#mtbPowerChips [data-value=""]').getAttribute('aria-pressed')==='true');
      assert.equal((await rows(page)).length,2);
     }finally{await page.close();}
    });
    await check(sport,width,'Synthetic same-variant, missing-spec, sold-out and price boundaries',async()=>{
     const page=await browser.newPage({viewport:{width,height:900},isMobile:width<800,hasTouch:width<800});
     try {
      await page.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
      await page.goto(base+'/'+fixture.path);const frame=page.mainFrame();
      await frame.waitForSelector('.deal-row',{state:'attached'});
      await control(frame,'partSelect',fixture.part);
      for(const [key,values] of Object.entries(fixture.selected))await technical(frame,key,values[0],width<800);
      let live=await rows(frame);assert.deepEqual(live.map(r=>r.url),[fixture.match]);assert.equal(Number(live[0].price),250);
      assert((await frame.locator('#cardGrid .deal-card:not(.filtered-out) .now-price').first().textContent()).includes('250.00'));
      // The price bound must choose another matching variant, rather than
      // rejecting the product because its cheapest matching variant is $250.
      await control(frame,'priceMin','275');live=await rows(frame);assert.deepEqual(live.map(r=>r.url),[fixture.match]);assert.equal(Number(live[0].price),300);
      assert((await frame.locator('#cardGrid .deal-card:not(.filtered-out) .now-price').first().textContent()).includes('300.00'));
      await control(frame,'priceMax','280');assert.equal((await rows(frame)).length,0);assert(await frame.locator('#emptyState').isVisible());
      const summary=await frame.locator('#emptyState').textContent();assert(summary.includes('Remove'),'zero results must offer targeted recovery');
      await control(frame,'priceMax','');await control(frame,'priceMin','');
      const card=frame.locator('#cardGrid .deal-card:not(.filtered-out)').first();await card.hover();await card.locator('.card-quick').click();
      assert((await frame.locator('#quickView .quick-price').textContent()).includes('250.00'));assert.equal(await frame.locator('#quickView .quick-alert').count(),0);
      assert.match(await frame.locator('#quickView .quick-price-note').textContent(),/history is for this listing and may include other variants/);
      return 'Only one available variant matches all specifications and ranges; the card/Quick View agree';
     }finally{await page.close();}
    });
    if(sport==='mtb'||sport==='bmx') await check(sport,width,'Promo visibility, copy and dismiss',async()=>{
     const page=await browser.newPage({viewport:{width,height:900},isMobile:width<800,hasTouch:width<800});
     try{
      await page.context().grantPermissions(['clipboard-read','clipboard-write']);
      await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
      await page.goto(base+'/'+fixture.path);
      const strip=page.locator('#promoStrip');
      if(sport==='bmx'){
       assert.equal(await strip.count(),0);
       return;
      }
      await strip.waitFor({state:'visible'});
      const phone=width<640;
      const more=strip.locator('#promoMore');
      const offers=strip.locator('.promo-offer:visible');
      assert.equal(await offers.count(),phone?1:2);
      if(phone){
       assert.match(await offers.first().textContent(),/FIXTURE20/);
       assert.equal(await more.getAttribute('aria-expanded'),'false');
      }
      await strip.getByRole('button',{name:'Copy FIXTURE20'}).click();
      await page.waitForFunction(async()=>await navigator.clipboard.readText()==='FIXTURE20');
      if(phone){
       await more.click();
       assert.equal(await offers.count(),2);
       assert.equal(await more.getAttribute('aria-expanded'),'true');
      }
      await strip.getByRole('button',{name:'Dismiss FIXTURE20'}).click();
      await strip.getByRole('button',{name:'Dismiss SPORTS10'}).click();
      await strip.waitFor({state:'hidden'});
      await page.reload();
      assert.equal(await strip.isVisible(),false);
     }finally{await page.close();}
    });
   }
  }
 }finally{await browser.close();server.close();fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2)+'\n');}
 const failed=results.filter(r=>r.status==='fail');console.log(JSON.stringify({passed:results.length-failed.length,failed},null,2));if(failed.length)process.exitCode=1;
}
main().catch(e=>{console.error(e);process.exitCode=1});
