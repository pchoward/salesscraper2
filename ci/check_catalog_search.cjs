// No live Shopify calls: feature gate and route are mocked in this preview only.
const {chromium}=require('playwright'),{serve}=require('./check_topbar.cjs');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const [site,out]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});
 const {server,base}=await serve(site),api='https://catalog-api.example.test';
 const browser=await chromium.launch({executablePath:process.env.BROWSER_BINARY,args:['--no-sandbox','--disable-dev-shm-usage']});const results=[];
 const price=amount=>({amount,currency:'USD'});
 const rawURL='https://sample-shop.example/products/mock-bike?variant=123&shcgid=retain%2Fexact&shclid=keep-this#large';
 const item=(title='MOCK / SAMPLE catalog bike')=>({title,url:rawURL,image:'https://sample-images.example/bike.svg',seller:{name:'Sample Shop',domain:'sample-shop.example'},price:price(7500),list_price:price(10000),discount:25});
 try{for(const width of (process.env.CATALOG_WIDTHS||'1440,390,320').split(',').map(Number))for(const sport of ['skate','bmx','ski','mtb']){
  console.log('Catalog search',sport,width);
  const page=await browser.newPage({viewport:{width,height:844},isMobile:width<641,hasTouch:width<641});
  const errors=[],requests=[];let enabled=true,mode='ok';
  await page.addInitScript(()=>localStorage.setItem('salesscraper2.views',JSON.stringify([{id:'catalog-qa',name:'Existing view',query:'type=all&brand=Saved'}])));
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin===api){
    requests.push({q:url.searchParams.get('q'),sport:url.searchParams.get('sport')});
    if(url.searchParams.get('q')==='slow catalog query')await new Promise(r=>setTimeout(r,1200));
    let body={items:[item(url.searchParams.get('q')+' · MOCK / SAMPLE'),{...item('MOCK five-percent offer'),price:price(9500)},
       {...item('MOCK rejected four-percent offer'),price:price(9600)}],expires_at:Date.now()+(mode==='expire'?2000:600000),max_age_ms:mode==='expire'?2000:600000};
    if(mode==='empty')body={items:[]};
    try{await route.fulfill({status:mode==='error'?503:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(body)});}catch(_){}
    return;
   }
   if(url.origin==='https://sample-images.example')return route.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#e2e8f0"/><text x="35" y="95" font-size="20">MOCK / SAMPLE IMAGE</text></svg>'});
   if(url.origin!==base)return route.abort();
   if(url.pathname.endsWith('sale_items_chart.html')&&enabled){
    const response=await route.fetch();let html=await response.text();
    html=html.replace(/(<script type="application\/json" id="liveCatalogSettings">).*?(<\/script>)/s,
      '$1'+JSON.stringify({enabled:true,apiBase:api})+'$2');
    return route.fulfill({response,body:html});
   }
   return route.continue();
  });
  async function visit(){
   await page.goto(base+'/?sport='+sport+'&type=all&q=bookmark-query&utm_source=catalog-qa');
   const frame=await(await page.locator('#skateFrame').elementHandle()).contentFrame();
   await frame.waitForFunction(()=>typeof applyFilters==='function'&&typeof state!=='undefined'&&state.search==='bookmark-query');return frame;
  }
  let frame=await visit();const header=page.locator('#shellSearch');
  const local=()=>page.evaluate(()=>Object.fromEntries(Object.keys(localStorage).sort().map(k=>[k,localStorage.getItem(k)])));
  const before=await local();
  const rowCount=await frame.locator('.deal-row').count();
  await page.waitForTimeout(550);assert.equal(requests.length,0,'no call for bookmarked search on page load');
  await frame.evaluate(()=>{document.getElementById('priceMax').value='99999';applyFilters();});
  await page.waitForTimeout(550);assert.equal(requests.length,0,'filter-only changes do not search Catalog');
  await header.fill('ab');await page.waitForTimeout(550);assert.equal(requests.length,0,'minimum three characters');
  await header.fill('mock catalog bike');
  await frame.locator('#liveCatalogDeals').waitFor({state:'visible'});
  assert.equal(requests.length,1);assert.equal(requests[0].sport,sport);assert.equal(requests[0].q,'mock catalog bike');
  assert.equal(await frame.locator('#liveCatalogGrid article').count(),2,'defensive five-percent cutoff');
  assert.equal(await frame.locator('#liveCatalogGrid a').first().getAttribute('href'),rawURL);
  assert.match(await frame.locator('#liveCatalogGrid').innerText(),/\$75\.00/);assert.match(await frame.locator('#liveCatalogGrid').innerText(),/25% off/);
  assert(await frame.evaluate(()=>document.getElementById('cardGrid').compareDocumentPosition(document.getElementById('liveCatalogDeals'))&Node.DOCUMENT_POSITION_FOLLOWING));
  assert.equal(await frame.locator('.deal-row').count(),rowCount,'Catalog results never enter the first-party catalog');
  assert.equal(await frame.locator('.deal-row:not(.filtered-out)').count(),0,'own search still works independently');
  const ownCount=await frame.locator('#statusCounts').innerText();assert.match(ownCount,/^0 deals/);
  assert.deepEqual(await local(),before,'live results do not write localStorage/saved views');
  assert.equal(new URL(page.url()).searchParams.get('utm_source'),'catalog-qa');
  assert.equal(new URL(page.url()).searchParams.get('sport'),sport);
  await header.evaluate(node=>node.blur());await frame.locator('#liveCatalogDeals').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,`${sport}-${width}.png`)});
  // A real first-party brand still produces our own matches alongside Catalog.
  const realBrand=await frame.locator('.deal-row').evaluateAll(nodes=>nodes.find(n=>n.dataset.brand)?.dataset.brand);
  assert(realBrand);await header.fill(realBrand);
  await frame.waitForFunction(()=>state.search&&document.querySelectorAll('.deal-row:not(.filtered-out)').length>0);
  const ownMatches=await frame.locator('.deal-row:not(.filtered-out)').count();
  await frame.locator('#liveCatalogDeals').waitFor({state:'visible'});
  assert.equal(await frame.locator('.deal-row:not(.filtered-out)').count(),ownMatches);
  // Slow results never block our filters and must not replace a later query.
  await header.fill('slow catalog query');await page.waitForTimeout(600);
  assert.equal(await frame.locator('#liveCatalogDeals').isVisible(),false);
  assert.equal(await frame.evaluate(()=>state.search),'slow catalog query');
  await header.fill('new catalog query');await frame.locator('#liveCatalogDeals').waitFor({state:'visible'});
  await page.waitForTimeout(1300);assert.match(await frame.locator('#liveCatalogGrid').innerText(),/new catalog query/);
  assert.doesNotMatch(await frame.locator('#liveCatalogGrid').innerText(),/slow catalog query/);
  const count=requests.length;await frame.evaluate(()=>{document.getElementById('priceMax').value='20';applyFilters();});
  await page.waitForTimeout(550);assert.equal(requests.length,count,'active results do not refetch on filter changes');
  mode='error';await header.fill('catalog error query');await page.waitForTimeout(800);
  assert.equal(await frame.locator('#liveCatalogDeals').isVisible(),false);assert.equal(await frame.locator('#statusCounts').innerText(),ownCount);
  mode='empty';await header.fill('catalog empty query');await page.waitForTimeout(800);assert.equal(await frame.locator('#liveCatalogDeals').isVisible(),false);
  mode='expire';await header.fill('catalog short expiry');await frame.locator('#liveCatalogDeals').waitFor({state:'visible'});
  await frame.locator('#liveCatalogDeals').waitFor({state:'hidden'});assert.equal(await frame.locator('#liveCatalogGrid article').count(),0,'prices expire from the DOM');
  mode='ok';await header.fill('catalog clear query');await frame.locator('#liveCatalogDeals').waitFor({state:'visible'});
  assert.deepEqual(await local(),before,'loading and expiring live results never persists them');
  await frame.evaluate(()=>clearFilters());await frame.locator('#liveCatalogDeals').waitFor({state:'hidden'});
  // Existing Clear all remembers disclosure preferences; live search does not.
  const afterClear=await local(),withoutSections={...before};
  delete afterClear['salesscraper2.filterSections'];delete withoutSections['salesscraper2.filterSections'];
  assert.deepEqual(afterClear,withoutSections);

  // A disabled production flag makes typing inert even with a healthy mock API.
  enabled=false;frame=await visit();const beforeOff=requests.length;await header.fill('catalog flag off query');
  await page.waitForTimeout(600);assert.equal(requests.length,beforeOff);assert.equal(await frame.locator('#liveCatalogDeals').isVisible(),false);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
  results.push({sport,width,status:'pass'});fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));await page.close();
 }console.log(JSON.stringify(results));}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
