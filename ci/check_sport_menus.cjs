// #212 sport hover/focus/touch menus. Uses saved catalogs, never retailers.
const {chromium}=require('playwright');
const {serve}=require('./check_topbar.cjs');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const [site,output]=process.argv.slice(2);fs.mkdirSync(output,{recursive:true});
 const {server,base}=await serve(site);
 const browser=await chromium.launch({executablePath:process.env.BROWSER_BINARY,args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try{
  for(const width of [1440,768,430,390]){
   const touch=width<=430;
   const page=await browser.newPage({viewport:{width,height:900},hasTouch:touch,isMobile:touch});
   const errors=[],catalogRequests=[],metadataRequests=[];page.on('pageerror',e=>errors.push(String(e)));
   page.on('request',request=>{
    const url=new URL(request.url());
    if(url.pathname.endsWith('sale_items_chart.html'))catalogRequests.push(url.pathname);
    if(url.pathname.endsWith('-categories.json'))metadataRequests.push(url.pathname);
   });
   await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
   await page.goto(base+'/?sport=skate');
   await page.waitForFunction(()=>!document.getElementById('categoryToggle').disabled);
   for(const [sport,part] of [['skate','Wheels'],['ski','Skis'],['mtb','Forks & Shocks'],['bmx','Bikes']]){
    console.log('Sport menu',width,sport);
    const before=page.url(),loadedCatalogs=catalogRequests.length;
    if(touch) await page.locator('#sport-'+sport).tap();
    else await page.locator('#sport-'+sport).hover();
    await page.waitForFunction(sport=>document.getElementById('categoryTitle').textContent.toLowerCase().startsWith(sport)&&document.getElementById('categoryPanel').getAttribute('aria-busy')==='false',sport);
    assert.equal(page.url(),before,'opening a sport menu must not navigate');
    assert.equal(catalogRequests.length,loadedCatalogs,'hover/focus/touch must not load an inactive catalog');
    assert.equal(page.frames().length,2,'only the visible catalog iframe may exist');
    assert(await page.locator('#categoryPanel').isVisible());
    const choice=page.locator('#categoryChoices button').filter({has:page.locator('.category-name',{hasText:new RegExp('^'+part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'$')})});
    assert(Number(await choice.getAttribute('data-count'))>0);
    if(!touch){
     await choice.hover();await page.waitForTimeout(250);
     assert(await page.locator('#categoryPanel').isVisible(),'pointer can cross into the menu');
    }
    if(width===1440||width===390) await page.screenshot({path:path.join(output,`menu-${sport}-${width}.png`)});
    await choice.click();
    await page.waitForFunction(({sport,part})=>{
     const f=document.getElementById('skateFrame');
     return new URL(location.href).searchParams.get('sport')===sport&&f.contentDocument?.querySelector('#partFilters [aria-pressed=true]')?.dataset.part===part&&!document.getElementById('categoryToggle').disabled;
    },{sport,part});
    assert.equal(await page.locator('#categoryPanel').isVisible(),false);
    const frame=await(await page.locator('#skateFrame').elementHandle()).contentFrame();
    assert(await frame.locator('#storeFilters').isVisible());
    const rows=await frame.locator('.deal-row:not(.filtered-out)').evaluateAll(rows=>rows.map(r=>r.dataset.part));
    assert(rows.length>0&&rows.every(p=>p===part));
    if(width===1440||width===390)await page.screenshot({path:path.join(output,`results-${sport}-${width}.png`)});
    // One-click All products route, after entering a category.
    if(touch)await page.locator('#sport-'+sport).tap();else await page.locator('#sport-'+sport).hover();
    await page.locator('#categoryChoices [data-part="all"]').click();
    await frame.waitForFunction(()=>state.part==='all');
    await page.waitForURL(url=>url.searchParams.get('type')===(sport==='skate'?'all':null));
    await page.goBack();
    await page.waitForFunction(part=>document.getElementById('skateFrame').contentDocument?.querySelector('#partFilters [aria-pressed=true]')?.dataset.part===part,part);
    await page.goForward();
    await page.waitForFunction(()=>document.getElementById('skateFrame').contentDocument?.querySelector('#partFilters [aria-pressed=true]')?.dataset.part==='all');
    await page.waitForURL(url=>url.searchParams.get('type')===(sport==='skate'?'all':null));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    results.push({sport,width,status:'pass'});
   }
   // Focus opens without switching catalog, Escape returns focus without reopening.
   await page.locator('#shellSearch').focus();const prior=page.url();
   await page.locator('#sport-skate').focus();
   await page.waitForSelector('#categoryPanel:not([hidden])');
   assert.equal(page.url(),prior);await page.keyboard.press('ArrowDown');
   await page.waitForFunction(()=>document.getElementById('categoryChoices').contains(document.activeElement));
   await page.keyboard.press('Escape');
   assert.equal(await page.locator('#categoryPanel').isVisible(),false);
   assert(await page.locator('#sport-skate').evaluate(n=>n===document.activeElement));
   await page.keyboard.press('ArrowRight');
   assert(await page.locator('#sport-ski').evaluate(n=>n===document.activeElement));
   await page.locator('#shellSearch').click();assert.equal(await page.locator('#categoryPanel').isVisible(),false);
   if(!touch){await page.locator('#sport-bmx').hover();await page.locator('#brandHome').hover();await page.waitForTimeout(250);assert.equal(await page.locator('#categoryPanel').isVisible(),false);}
   assert.equal(new Set(metadataRequests).size,metadataRequests.length,'metadata is fetched once per sport and cached');
   assert.deepEqual(errors,[]);await page.close();
  }
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
