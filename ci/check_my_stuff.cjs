// Part B: catalog-owned personal tools, unchanged persistence, no hidden sidebar.
const{chromium}=require('playwright'),{serve}=require('./check_topbar.cjs');const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{const[site,out]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});const{server,base}=await serve(site);const browser=await chromium.launch({executablePath:process.env.BROWSER_BINARY,args:['--no-sandbox','--disable-dev-shm-usage']});const results=[];
try{for(const width of[1440,390])for(const sport of['skate','ski','mtb','bmx']){
 console.log('My stuff',sport,width);const page=await browser.newPage({viewport:{width,height:950},isMobile:width===390,hasTouch:width===390,permissions:['clipboard-read','clipboard-write']});const errors=[];page.on('pageerror',e=>errors.push(String(e)));await page.route('**/*',r=>new URL(r.request().url()).origin===base?r.continue():r.abort());
 async function ready(){await page.waitForSelector('#myStuffSave:not([disabled])',{state:'attached'});return(await page.locator('#skateFrame').elementHandle()).contentFrame();}
 await page.goto(base+'/?sport='+sport+'&utm_source=my-stuff-qa');let frame=await ready();
 for(const section of['views','watching','bookmarks'])assert.equal(await frame.locator('#filterDrawer [data-section="'+section+'"]').count(),0);
 const card=frame.locator('#cardGrid .deal-card:not(.filtered-out)').first();await card.hover();const star=card.locator('.star');await star.click();
 const name='QA '+sport;await page.locator('#myStuffToggle').click();assert(await page.locator('#skateFrame').evaluate(n=>n.inert));
 await page.locator('#myStuffName').fill(name);await page.locator('#myStuffSave').click();
 await page.getByRole('button',{name:name+' · Shared',exact:true}).waitFor();
 const views=await page.evaluate(()=>JSON.parse(localStorage.getItem('salesscraper2.views')));assert.equal(views.length,1);assert.deepEqual(Object.keys(views[0]).sort(),['id','name','query']);
 assert.equal(views[0].name,name);assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('salesscraper2.stars')).length),1);
 await page.evaluate(sport=>{const views=JSON.parse(localStorage.getItem('salesscraper2.views'));views.push({id:'current-sport',name:'This sport only',query:'sport='+sport+'&type=all'});views.push({id:'foreign-sport',name:'Other sport only',query:'sport='+(sport==='ski'?'bmx':'ski')+'&q=foreign'});localStorage.setItem('salesscraper2.views',JSON.stringify(views));},sport);
 await page.reload();frame=await ready();await page.locator('#myStuffToggle').click();await page.getByRole('button',{name:name+' · Shared',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:/Other sport only/}).count(),0);await page.getByRole('button',{name:'This sport only · '+({skate:'Skate',ski:'Ski',mtb:'MTB',bmx:'BMX'})[sport],exact:true}).waitFor();if(sport!=='skate')assert.equal(await page.getByRole('button',{name:/Decks 8.25/}).count(),0);
 // Close/focus then change search; applying the saved snapshot restores it.
 await page.keyboard.press('Escape');assert(await page.locator('#myStuffToggle').evaluate(n=>n===document.activeElement));assert.equal(await page.locator('#skateFrame').evaluate(n=>n.inert),false);
 await page.locator('#shellSearch').fill('zzzz-my-stuff-no-result');await frame.waitForFunction(()=>document.querySelectorAll('.deal-row:not(.filtered-out)').length===0);
 await page.locator('#myStuffToggle').click();await page.getByRole('button',{name:name+' · Shared',exact:true}).click();
 await frame.waitForFunction(()=>document.getElementById('searchInput').value===''&&document.querySelectorAll('.deal-row:not(.filtered-out)').length>0);
 await page.locator('#myStuffToggle').click();await page.locator('#myStuffWatching').click();await page.waitForFunction(()=>document.getElementById('myStuffWatching').getAttribute('aria-pressed')==='true');
 await frame.waitForFunction(()=>state.watching&&document.querySelectorAll('.deal-row:not(.filtered-out)').length===1);
 assert.equal(await page.locator('#myStuffWatching').innerText(),'Show all deals');
 assert.match(await page.locator('#myStuffStars').innerText(),/^1 starred deal/);
 await page.locator('#myStuffBookmark').click();await page.waitForFunction(()=>document.getElementById('myStuffStatus').textContent==='Selection link copied.');
 const copied=new URL(await page.evaluate(()=>navigator.clipboard.readText()));assert.equal(copied.searchParams.get('watching'),'1');assert.equal(copied.searchParams.get('sport'),sport);assert.equal(copied.searchParams.get('utm_source'),'my-stuff-qa');
 if(width===390)assert(await page.locator('#myStuffPanel').evaluate(n=>n.getBoundingClientRect().right<=innerWidth));
 await page.screenshot({path:path.join(out,`${sport}-${width}.png`)});
 // Keyboard trap and outside tap both release the frame and return focus.
 await page.locator('#myStuffClose').focus();await page.keyboard.press('Shift+Tab');assert(await page.locator('#myStuffBookmark').evaluate(n=>n===document.activeElement));await page.keyboard.press('Tab');assert(await page.locator('#myStuffClose').evaluate(n=>n===document.activeElement));
 await page.keyboard.press('Escape');assert.equal(await page.locator('#myStuffPanel').isVisible(),false);
 await page.locator('#myStuffToggle').click();await page.locator('#myStuffBackdrop').click({position:{x:4,y:900}});assert.equal(await page.locator('#myStuffPanel').isVisible(),false);assert.equal(await page.locator('#skateFrame').evaluate(n=>n.inert),false);
 await page.locator('#myStuffToggle').click();await page.keyboard.press('/');assert.equal(await page.locator('#myStuffPanel').isVisible(),false);assert(await page.locator('#shellSearch').evaluate(n=>n===document.activeElement));
 // Rename/delete still use the original catalog functions and storage shape.
 await page.locator('#myStuffToggle').click();await page.getByRole('button',{name:'Rename '+name,exact:true}).click();await page.locator('#myStuffName').fill(name+' renamed');await page.locator('#myStuffSave').click();await page.getByRole('button',{name:name+' renamed · Shared',exact:true}).waitFor();
 await page.getByRole('button',{name:'Delete '+name+' renamed',exact:true}).click();await page.waitForFunction(()=>JSON.parse(localStorage.getItem('salesscraper2.views')).length===2);assert.deepEqual((await page.evaluate(()=>JSON.parse(localStorage.getItem('salesscraper2.views')).map(view=>view.id))).sort(),['current-sport','foreign-sport']);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
 // Same artifact, no shell: all three personal sections remain in the drawer.
 await page.goto(base+(sport==='skate'?'/sale_items_chart.html':'/'+sport+'/sale_items_chart.html'));
 await page.waitForSelector('#personalTools',{state:'attached'});for(const section of['views','watching','bookmarks'])assert.equal(await page.locator('#filterDrawer [data-section="'+section+'"]').count(),1);
 results.push({sport,width,status:'pass'});await page.close();
}fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));}finally{await browser.close();await new Promise(r=>server.close(r));}})().catch(e=>{console.error(e);process.exitCode=1});
