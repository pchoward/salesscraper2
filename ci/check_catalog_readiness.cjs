// Exercise load order and a WindowProxy reused by a different sport.
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
  for(const mode of ['early','legacy','late','stale']){
   const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
   const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   let release,held=false,body;
   const gate=new Promise(resolve=>release=resolve);
   await page.route('**/*',async route=>{
    const url=new URL(route.request().url());
    if(url.origin!==base)return route.abort();
    if(mode==='late'&&url.pathname.endsWith('/navigation/skate-bridge.js')){
     held=true;await gate;return route.continue();
    }
    if(url.pathname==='/__stalled_catalog.js'){
     held=true;await gate;return route.fulfill({contentType:'application/javascript',body});
    }
    if(url.pathname.endsWith('sale_items_chart.html')&&mode!=='late'&&(mode==='early'||mode==='legacy'||url.pathname.includes('/mtb/'))){
     const response=await route.fetch();let html=await response.text();
     let replaced=false;
     html=html.replace(/<script>(?=(?:const SPORT_SETTINGS|const WIDTH_RANGES))([\s\S]*?)<\/script>/,(_,script)=>{
      replaced=true;body=mode==='legacy'?script.replace(/    \/\/ Readiness belongs[^\n]*\n    document.shredCatalogReady[^\n]*\n    document.dispatchEvent\(new Event\("shreddeals:catalog-ready"\)\);\n/,''):script;
      return '<script>document.documentElement.dataset.stalled="yes";'+(['early','legacy'].includes(mode)?'window.parent.shredApp.registerCategories(document.getElementById("partFilters"),window);':'')+'</script><script src="/__stalled_catalog.js"></script>';
     });
     assert(replaced,'catalog main script was stalled');
     return route.fulfill({response,body:html});
    }
    return route.continue();
   });
   await page.goto(base+'/?sport=skate',{waitUntil:'domcontentloaded'});
   if(mode==='stale'){
    await page.waitForFunction(()=>!document.getElementById('categoryToggle').disabled);
    await page.evaluate(()=>{
     const child=document.getElementById('skateFrame').contentWindow;
     window.oldCatalog={child,source:child.document.getElementById('partFilters'),document:child.document};
     shredApp.choose('ski','sport');
     setTimeout(()=>shredApp.choose('mtb','sport'),30);
    });
   }
   await page.waitForFunction(mode=>{
    const child=document.getElementById('skateFrame').contentWindow;
    return mode==='late'?!!child.document.shredCatalogReady:child.document.documentElement?.dataset.stalled==='yes';
   },mode);
   // Route handlers are outside the page; wait until the held request arrived.
   await assertEventually(()=>held);
   assert(await page.locator('#categoryToggle').isDisabled());
   if(mode==='stale')await page.evaluate(()=>{
    const old=window.oldCatalog;
    setTimeout(()=>shredApp.registerCategories(old.source,old.child,old.document),0);
    old.document.dispatchEvent(new Event('shreddeals:catalog-ready'));
   });
   assert.deepEqual(errors,[]);
   release();
   await page.waitForFunction(()=>!document.getElementById('categoryToggle').disabled);
   if(mode==='stale')assert.equal(await page.evaluate(()=>shredApp.registerCategories(oldCatalog.source,oldCatalog.child,oldCatalog.document)),false);
   const counts=await page.evaluate(()=>{
    const child=document.getElementById('skateFrame').contentWindow;
    const expected={all:0};for(const row of child.dealRows()){
     if(row.dataset.removed==='1'||!row.dataset.part||row.dataset.part==='all')continue;
     expected.all++;expected[row.dataset.part]=(expected[row.dataset.part]||0)+1;
    }
    document.getElementById('categoryToggle').click();
    return {expected,actual:Object.fromEntries([...document.querySelectorAll('#categoryChoices [data-part]')].map(b=>[b.dataset.part,Number(b.dataset.count)]))};
   });
   for(const [part,count] of Object.entries(counts.expected))assert.equal(counts.actual[part],count,part+' live count');
   assert.deepEqual(errors,[]);
   results.push({mode,width:390,status:'pass'});await page.close();
  }
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));console.log(results);
 }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
async function assertEventually(predicate){
 const deadline=Date.now()+10000;
 while(!predicate()&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,20));
 assert(predicate(),'stalled request arrived');
}
