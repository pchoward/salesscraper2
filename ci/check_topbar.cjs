// Issue #154: actual shell/catalog interaction checks and review screenshots.
// Build with ci/build_preview.py first; external requests are blocked here.
// node ci/check_topbar.cjs SITE_DIR OUTPUT_DIR [BEFORE_SITE_DIR]
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const [site, output, before] = process.argv.slice(2);
if (!site || !output) throw new Error('Expected SITE_DIR OUTPUT_DIR [BEFORE_SITE_DIR]');
const mime = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json'};
async function serve(root) {
    root = path.resolve(root);
    const server = http.createServer((req, res) => {
        const name = decodeURIComponent(new URL(req.url, 'http://local').pathname);
        const file = path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
        if (!file.startsWith(root + path.sep)) return res.writeHead(403).end();
        try { res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream'); res.end(fs.readFileSync(file)); }
        catch { res.writeHead(404).end(); }
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    return {server, base:'http://127.0.0.1:' + server.address().port};
}
async function main() {
    fs.mkdirSync(output, {recursive:true});
    const browser = await chromium.launch({headless:true,
        ...(process.env.BROWSER_BINARY ? {executablePath:process.env.BROWSER_BINARY} : {}),
        args:['--no-sandbox', '--disable-dev-shm-usage']});
    const results = [];
    try {
        for (const [version, root] of [...(before ? [['before', before]] : []), ['after', site]]) {
            const {server, base} = await serve(root);
            try {
                for (const width of [1440, 1024, 800, 390, 320]) {
                    const page = await browser.newPage({viewport:{width,height:width <= 800 ? 844 : 1000},
                        isMobile:width <= 800, hasTouch:width <= 800});
                    const errors = [];
                    page.on('pageerror', e => errors.push(String(e)));
                    await page.route('**/*', route => new URL(route.request().url()).hostname === '127.0.0.1' ? route.continue() : route.abort());
                    await page.goto(base);
                    let frame = await (await page.waitForSelector('#skateFrame')).contentFrame();
                    await frame.waitForSelector('#cardGrid .deal-card');
                    if (version === 'after') await page.waitForSelector('[data-catalog-control="navAlerts"]');
                    await page.waitForTimeout(400);
                    const metrics = await page.evaluate(() => {
                        const frame = document.getElementById('skateFrame');
                        const doc = frame.contentDocument;
                        return {cardTop:Math.round(frame.getBoundingClientRect().top + doc.getElementById('cardGrid').getBoundingClientRect().top),
                            shellOverflow:document.documentElement.scrollWidth > innerWidth,
                            catalogOverflow:doc.documentElement.scrollWidth > frame.clientWidth};
                    });
                    if (width === 1440 || width === 390) await page.screenshot({path:path.join(output,`${version}-${width === 1440 ? 'desktop' : 'mobile'}.png`)});
                    if (version === 'after') {
                        assert(!metrics.shellOverflow && !metrics.catalogOverflow, `Overflow at ${width}`);
                        assert.equal(await frame.locator('.topnav').isVisible(), false);
                        assert.equal(await page.locator('.catalog-sections').count(), 1);
                        assert.equal(await page.locator('.catalog-sections button').count(), 4);
                        const controls = await page.locator('.catalog-sections button').evaluateAll(nodes => nodes.map(n => {
                            const r = n.getBoundingClientRect(); return {left:r.left,right:r.right,bottom:r.bottom,top:r.top};
                        }));
                        assert(controls.every(r => r.left >= 0 && r.right <= width + 1));
                        assert(controls.every((r,i) => controls.slice(i+1).every(b => r.right <= b.left+1 || r.bottom <= b.top+1)));
                        const originalCounts = await frame.locator('#partFilters [data-part]').count();
                        const storeCounts = await frame.locator('#storeFilters [data-store]').count();
                        assert(originalCounts > 2 && storeCounts > 2);
                        await frame.locator('#searchInput').fill('baker');
                        await page.waitForTimeout(400);
                        assert.match(page.url(), /q=baker/);
                        const queryURL = page.url();
                        await page.locator('[data-catalog-control="navTrack"]').click();
                        await page.waitForFunction(() => document.querySelector('[data-catalog-control="navTrack"]').getAttribute('aria-pressed') === 'true');
                        assert.equal(await frame.evaluate(() => state.watching), true);
                        await page.locator('[data-catalog-control="navDeals"]').click();
                        assert.equal(await frame.evaluate(() => state.watching), false);
                        assert.equal(await frame.locator('#searchInput').inputValue(), 'baker');
                        await page.locator('[data-catalog-control="navInsights"]').click();
                        await page.waitForFunction(() => document.querySelector('[data-catalog-control="navInsights"]').getAttribute('aria-pressed') === 'true');
                        await page.locator('[data-catalog-control="navDeals"]').click();
                        await page.locator('[data-catalog-control="navAlerts"]').click();
                        assert(await frame.locator('#alertsRoot').isVisible());
                        assert.notEqual(await frame.evaluate(() => alertsUi.config.mode), 'live');
                        await page.keyboard.press('Escape');
                        await frame.evaluate(() => closeAlerts());
                        await frame.locator('#searchInput').fill('');
                        await page.waitForTimeout(350);
                        await frame.locator('#partFilters [data-part="Wheels"]').click();
                        assert.equal(await frame.evaluate(() => state.part), 'Wheels');
                        await frame.locator('#storeFilters [data-store="Zumiez"]').click();
                        assert.equal(await frame.evaluate(() => state.store), 'Zumiez');
                        await frame.locator('#sortSelect').selectOption('price');
                        assert.equal(await frame.locator('#sortSelect').inputValue(), 'price');
                        await frame.locator('#groupToggle').click();
                        assert.equal(await frame.locator('#groupToggle').getAttribute('aria-pressed'), 'true');
                        if (width <= 800) {
                            await frame.locator('#filtersOpen').click();
                            assert(await frame.locator('#filterDrawer').evaluate(n => n.classList.contains('is-open')));
                            await frame.evaluate(() => document.querySelector('.filters-done').click());
                        } else {
                            await frame.locator('#layoutTable').click();
                            assert.equal(await frame.locator('#layoutTable').getAttribute('aria-pressed'), 'true');
                            await frame.locator('#layoutCards').click();
                        }
                        assert.equal(await frame.locator('#partFilters [data-part]').count(), originalCounts);
                        assert.equal(await frame.locator('#storeFilters [data-store]').count(), storeCounts);
                        // Returning through browser history restores query state.
                        await page.goto(queryURL);
                        frame = await (await page.waitForSelector('#skateFrame')).contentFrame();
                        await frame.waitForSelector('#searchInput');
                        assert.equal(await frame.locator('#searchInput').inputValue(), 'baker');
                        await page.locator('#sport-ski').click();
                        await page.waitForTimeout(600);
                        await page.goBack();
                        await page.waitForTimeout(600);
                        frame = await (await page.waitForSelector('#skateFrame')).contentFrame();
                        await frame.waitForSelector('#searchInput');
                        assert.equal(await frame.locator('#searchInput').inputValue(), 'baker');
                        assert.equal(await page.locator('.catalog-sections').count(), 1);
                        assert.deepEqual(errors, []);
                    }
                    results.push({version,width,...metrics});
                    await page.close();
                }
            } finally { server.close(); }
        }
        fs.writeFileSync(path.join(output,'results.json'), JSON.stringify(results,null,2)+'\n');
        console.log(JSON.stringify(results,null,2));
    } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
