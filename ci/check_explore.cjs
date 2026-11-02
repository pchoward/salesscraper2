// Existing Playwright runtime and HTTP helper; no live retailer requests.
const {chromium} = require('playwright');
const {serve} = require('./check_topbar.cjs');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
async function main() {
    const [site, output] = process.argv.slice(2); fs.mkdirSync(output, {recursive:true});
    const {server, base} = await serve(site);
    const browser = await chromium.launch({executablePath:process.env.BROWSER_BINARY, args:['--no-sandbox','--disable-dev-shm-usage']});
    const results = [];
    try {
        for (const width of [1440,768,430,390]) for (const sport of ['mtb','ski']) {
            const page = await browser.newPage({viewport:{width,height:900}});
            const errors = []; page.on('pageerror', e => errors.push(String(e)));
            await page.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
            await page.goto(base + '/?sport=' + sport);
            await page.locator('[data-catalog-control="navExplore"]').waitFor();
            assert(!page.url().includes('view=explore'), 'Deals is default');
            await page.locator('[data-catalog-control="navExplore"]').click();
            await page.waitForURL('**view=explore**');
            let frame = await (await page.waitForSelector('#skateFrame')).contentFrame();
            await frame.locator('.inventory-card').first().waitFor();
            assert.equal(await frame.locator('.inventory-card').count(), 12);
            const size = sport === 'mtb' ? 'Large' : '178 cm';
            await frame.locator('#size').selectOption(size);
            await frame.locator('#brand').selectOption('Demo Cycles');
            await frame.locator('#sale').selectOption('sale');
            assert.equal(await frame.locator('.inventory-card').count(), 3);
            assert.match(await frame.locator('.inventory-card').first().innerText(), /1050.00/);
            await frame.locator('#sale').selectOption('regular');
            assert.equal(await frame.locator('.inventory-card').count(), 0);
            await page.goBack();
            await page.waitForFunction(() => document.getElementById('skateFrame').contentDocument.getElementById('sale')?.value === 'sale');
            frame = await (await page.$('#skateFrame')).contentFrame();
            assert.equal(await frame.locator('.inventory-card').count(), 3);
            await page.goForward();
            await page.waitForFunction(() => document.getElementById('skateFrame').contentDocument.getElementById('sale')?.value === 'regular');
            assert.equal(await frame.locator('.inventory-card').count(), 0);
            await frame.locator('button[type=reset]').click();
            assert.equal(await frame.locator('.inventory-card').count(), 12);
            await frame.locator('#query').fill('nothing matches');
            assert.equal(await frame.locator('.inventory-card').count(), 0);
            await frame.locator('#query').fill('');
            await frame.locator('.inventory-card button').first().click();
            assert(await frame.locator('#quick').isVisible());
            assert.match(await frame.locator('#quickContent').innerText(), /Observed price history/);
            assert.match(await frame.locator('#quickContent a').getAttribute('href'), /https:\/\/example.com\/products\/fixture-1\?variant=10/);
            await page.keyboard.press('Escape');
            assert(!(await frame.locator('#quick').isVisible()));
            await frame.locator('#view').selectOption('table');
            assert.equal(await frame.locator('#inventory').getAttribute('class'), 'table');
            await frame.locator('#view').selectOption('cards');
            assert(await frame.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
            assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
            if (width === 1440 || width === 390) await page.screenshot({path:path.join(output, `${sport}-${width}.png`)});
            await page.locator('[data-catalog-control="navDeals"]').click();
            await page.waitForURL(url => !url.searchParams.has('view'));
            await page.locator('[data-catalog-control="navExplore"]').waitFor();
            await page.goBack();
            await page.waitForURL('**view=explore**');
            frame = await (await page.$('#skateFrame')).contentFrame();
            await frame.locator('.inventory-card').first().waitFor();
            const other = sport === 'mtb' ? 'ski' : 'mtb';
            await page.locator('#sport-' + other).click();
            assert(!page.url().includes('view=explore'));
            assert(!page.url().includes('ex_'));
            assert.deepEqual(errors, []);
            results.push({sport,width,status:'pass'}); await page.close();
        }
        fs.writeFileSync(path.join(output,'results.json'), JSON.stringify(results,null,2));
        console.log(JSON.stringify(results));
    } finally {await browser.close(); await new Promise(resolve => server.close(resolve));}
}
main().catch(error => {console.error(error); process.exitCode=1;});
