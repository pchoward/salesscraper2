// PR #199: header/search behavior uses the catalog's own filters and URL state.
const {chromium} = require('playwright');
const {serve} = require('./check_topbar.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
async function main() {
    const [site, output] = process.argv.slice(2);
    fs.mkdirSync(output, {recursive:true});
    const {server, base} = await serve(site);
    const browser = await chromium.launch({executablePath:process.env.BROWSER_BINARY, args:['--no-sandbox','--disable-dev-shm-usage']});
    const results = [];
    try {
        for (const width of [1440, 390]) {
            const page = await browser.newPage({viewport:{width,height:1000}});
            const errors = [];
            page.on('pageerror', error => errors.push(String(error)));
            await page.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
            const header = page.locator('#shellSearch');
            const home = fs.readFileSync(path.join(site,'index.html'),'utf8');
            const emptyHome = home.replace(/(<script[^>]+id="sportConfig"[^>]*>)([\s\S]*?)(<\/script>)/, (_,open,json,close) => {
                const config = JSON.parse(json);
                config.sports.push({id:'surf',label:'Surf',catalog:null,categories:[],facets:{}});
                return open + JSON.stringify(config) + close;
            });
            await page.route('**/empty.html*', route => route.fulfill({contentType:'text/html',body:emptyHome}));
            async function frameInput(id, query) {
                await page.waitForFunction(({id,query}) => document.getElementById('skateFrame').contentDocument?.getElementById(id)?.value === query, {id,query});
            }
            async function headerValue(query) { await page.waitForFunction(query => document.getElementById('shellSearch').value === query, query); }
            for (const sport of ['skate','ski','mtb','bmx']) {
                console.log('Checking header search',sport,width);
                await page.goto(base + '/?sport=' + sport + '&q=initial-query');
                let frame = await (await page.waitForSelector('#skateFrame')).contentFrame();
                await frame.waitForSelector('#searchInput',{state:'attached'});
                await frameInput('searchInput','initial-query'); await headerValue('initial-query');
                assert.equal(await frame.locator('#searchInput').isVisible(),false,'duplicate search must be hidden');
                const layout = await page.evaluate(() => {
                    const search=document.querySelector('.shell-search').getBoundingClientRect();
                    const sports=document.getElementById('sportTabs').getBoundingClientRect();
                    const utility=document.querySelector('.catalog-sections')?.getBoundingClientRect();
                    return {search:{width:search.width,bottom:search.bottom,right:search.right},sportsTop:sports.top,utilityRight:utility?.right};
                });
                assert(layout.search.width >= (width > 800 ? 600 : width-30),'primary search must be large');
                assert(layout.sportsTop >= layout.search.bottom,'sports must be on a separate row');
                if (width > 800) assert(layout.utilityRight >= width-30,'utility controls must be at the far right');
                await frame.evaluate(() => clearFilters()); await headerValue('');
                const sample = await frame.locator('.deal-row:not(.filtered-out)').first().evaluate(row => ({store:row.dataset.store,part:row.dataset.part}));
                await frame.evaluate(sample => {
                    for (const [id,value] of [['partSelect',sample.part],['storeSelect',sample.store]]) {
                        const select = document.getElementById(id); select.value = value; select.dispatchEvent(new Event('change',{bubbles:true}));
                    }
                }, sample);
                await header.fill('zzzz-unmatched-header-search');
                await frameInput('searchInput','zzzz-unmatched-header-search');
                await frame.waitForFunction(() => document.querySelectorAll('.deal-row:not(.filtered-out)').length === 0);
                await header.fill(''); await frameInput('searchInput','');
                assert.equal(await frame.locator('#partSelect').inputValue(),sample.part);
                assert.equal(await frame.locator('#storeSelect').inputValue(),sample.store);
                await frame.evaluate(() => { const input=document.getElementById('searchInput');input.value='native-search';input.dispatchEvent(new Event('input',{bubbles:true})); }); await headerValue('native-search');
                await frame.evaluate(() => clearFilters()); await headerValue('');
                if (sport === 'skate') {
                    await header.fill('spi');
                    await page.locator('#shellSuggestions [role=option]').first().waitFor();
                    await header.press('ArrowDown');
                    await page.waitForFunction(() => document.getElementById('shellSearch').hasAttribute('aria-activedescendant'));
                    await header.press('Enter');
                    await page.locator('#shellSuggestions').waitFor({state:'hidden'});
                    await frame.evaluate(() => clearFilters()); await headerValue('');
                    await header.fill('spi');
                    await page.locator('#shellSuggestions [role=option]').first().click();
                    await page.locator('#shellSuggestions').waitFor({state:'hidden'});
                    await frame.evaluate(() => clearFilters()); await headerValue('');
                }
                // Programmatic search-chip changes use URL state rather than input events.
                await header.fill('under 100'); await frameInput('searchInput','under 100');
                await frame.locator('#searchChips .search-chip').first().waitFor();
                await frame.locator('#searchChips .search-chip').first().click(); await headerValue('');
                await header.fill('history-first'); await frameInput('searchInput','history-first');
                await page.waitForURL(url => url.searchParams.get('q') === 'history-first');
                await header.fill('history-second'); await frameInput('searchInput','history-second');
                await page.waitForURL(url => url.searchParams.get('q') === 'history-second');
                await page.goBack(); await headerValue('history-first'); await frameInput('searchInput','history-first');
                await page.goForward(); await headerValue('history-second'); await frameInput('searchInput','history-second');
                await frame.evaluate(() => clearFilters()); await headerValue('');
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
                if (sport === 'mtb') await page.evaluate(() => document.getElementById('sportPanel').focus());
                if (sport === 'mtb') await page.screenshot({path:path.join(output,`header-${width}.png`)});
                results.push({sport,width,case:'Deals search, clear, chips, existing filters and history',status:'pass'});
            }
            await page.goto(base + '/?sport=mtb&view=explore&scope=mtb-dirt-jump&ex_query=Example');
            let frame = await (await page.waitForSelector('#skateFrame')).contentFrame();
            await frame.waitForSelector('#query',{state:'attached'}); await headerValue('Example');
            await header.fill('zzzz-unmatched-header-search'); await frameInput('query','zzzz-unmatched-header-search');
            assert.equal(await frame.locator('.inventory-card').count(),0);
            await frame.locator('button[type=reset]').click(); await headerValue('');
            await header.fill('complete 1'); await headerValue('complete 1');
            assert.equal(await frame.locator('.inventory-card').count(),2);
            await page.locator('[data-catalog-control=navDeals]').click();
            await frameInput('searchInput',''); await headerValue('');
            // A previous view cannot overwrite the active catalog's query.
            await page.evaluate(() => {
                const frame = document.getElementById('skateFrame');
                dispatchEvent(new MessageEvent('message',{origin:location.origin,source:frame.contentWindow,
                    data:{type:'shreddeals:search-sync',href:new URL('discover/mtb-dirt-jump/index.html',location.href).href,query:'late-explore-query'}}));
            });
            assert.equal(await header.inputValue(),'');
            await page.locator('#sport-ski').click(); await frameInput('searchInput',''); await headerValue('');
            await page.evaluate(() => document.getElementById('sportPanel').focus());
            await page.keyboard.press('/'); assert(await header.evaluate(node => document.activeElement === node));
            await page.goto(base + '/empty.html?sport=surf');
            await page.locator('#comingSoon').waitFor();
            assert(await header.isDisabled());
            assert.equal(await header.inputValue(),'');
            await page.locator('#sport-skate').click();
            await frameInput('searchInput',''); await headerValue('');
            assert(await header.isEnabled());
            assert.deepEqual(errors,[]);
            // Direct catalog links retain their original standalone search UI.
            await page.goto(base + '/sale_items_chart.html');
            const standalone = page.locator('#searchInput');
            await standalone.waitFor();
            await standalone.fill('spi');
            await page.locator('#searchSuggest [role=option]').first().waitFor();
            await standalone.press('ArrowDown'); await standalone.press('Enter');
            await page.locator('#searchSuggest').waitFor({state:'hidden'});
            results.push({sport:'mtb',width,case:'Explore bidirectional search, reset, mode/sport switches and stale-message isolation',status:'pass'});
            await page.close();
        }
        fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2)+'\n');
        console.log(JSON.stringify(results));
    } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
}
main().catch(error => {console.error(error);process.exitCode=1;});
