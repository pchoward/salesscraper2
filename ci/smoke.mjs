// Browser smoke test and screenshots for a PR preview (ci/build_preview.py).
//
//   node ci/smoke.mjs SITE_DIR OUT_DIR
//
// Serves SITE_DIR on localhost, opens it in Chromium at desktop and phone
// sizes, and checks what a visitor does first: the page loads clean,
// a category filter, a search, a retailer link, Quick View, the alerts
// panel (which must stay offline in a preview), then the ShredDeals
// homepage: sport tabs, Skate's catalog, empty other sports, Back/Forward.
// Writes OUT_DIR/summary.json and PNG screenshots. Exits 1 when a check
// fails, so CI shows it; screenshots are written either way.

import { createRequire } from "node:module";
import { createServer } from "node:http";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { extname, join, normalize, resolve } from "node:path";

// CI installs Playwright next to this file (ci/node_modules); a machine
// with a global Playwright works too.
const { chromium } = createRequire(import.meta.url)("playwright");

const [siteDir, outDir] = process.argv.slice(2);
if (!siteDir || !outDir) {
    console.error("usage: node ci/smoke.mjs SITE_DIR OUT_DIR");
    process.exit(2);
}
const SITE = resolve(siteDir);
const TYPES = { ".html": "text/html; charset=utf-8", ".json": "application/json", ".css": "text/css", ".js": "text/javascript" };
// Hosts a preview must never call: the production alerts Worker, Turnstile,
// and analytics.
const FORBIDDEN = /workers\.dev|challenges\.cloudflare\.com|cloudflareinsights\.com/i;

function serve() {
    const server = createServer(async (request, response) => {
        const path = normalize(decodeURIComponent(new URL(request.url, "http://x").pathname)).replace(/^([/\\])+/, "");
        const file = join(SITE, path || "index.html");
        if (!file.startsWith(SITE)) {
            response.writeHead(403).end();
            return;
        }
        try {
            const body = await readFile(file);
            response.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" }).end(body);
        } catch (err) {
            response.writeHead(404).end();
        }
    });
    return new Promise(done => server.listen(0, "127.0.0.1", () => done(server)));
}

const checks = [];
function record(view, name, status, detail) {
    checks.push({ view, name, status, detail: String(detail || "") });
}

async function check(view, name, fn) {
    try {
        const result = await fn();
        if (result && result.skip) record(view, name, "skip", result.skip);
        else record(view, name, "pass", result || "");
    } catch (err) {
        record(view, name, "fail", (err && err.message) || err);
    }
}

function expect(condition, message) {
    if (!condition) throw new Error(message);
}

const liveCards = page => page.evaluate(() => Array.from(document.querySelectorAll("#cardGrid .deal-card"))
    .filter(card => !card.classList.contains("filtered-out") && !card.classList.contains("grouped-hide")).length);

async function run(browser, base, view, options) {
    const context = await browser.newContext(options);
    const page = await context.newPage();
    const errors = [];
    const forbidden = [];
    page.on("pageerror", error => errors.push(String(error)));
    page.on("request", request => { if (FORBIDDEN.test(request.url())) forbidden.push(request.url()); });
    // Off-site requests are blocked, except product photos (the stores'
    // image CDNs, as any visitor loads them) so screenshots look real.
    await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, route =>
        (route.request().resourceType() === "image" ? route.continue() : route.abort()));
    const shots = [];
    async function shot(name) {
        const file = `${view}-${name}.png`;
        await page.screenshot({ path: join(outDir, file) });
        shots.push(file);
    }

    await check(view, "Page loads", async () => {
        await page.goto(base + "/sale_items_chart.html", { waitUntil: "load", timeout: 60000 });
        await page.waitForTimeout(800);
        const count = await liveCards(page);
        expect(count > 0, "no deal cards rendered");
        expect(await page.locator("#previewBanner").count() === 1, "PREVIEW banner missing");
        return count + " deal cards";
    });
    await shot("home");

    await check(view, "Category filter", async () => {
        const target = await page.evaluate(() => {
            const button = Array.from(document.querySelectorAll("button[data-part]"))
                .find(node => node.getAttribute("data-part") !== "Decks" && node.getAttribute("data-part") !== "all");
            if (!button) return "";
            button.click();
            return button.getAttribute("data-part");
        });
        if (!target) return { skip: "no category buttons" };
        await page.waitForTimeout(300);
        const part = await page.evaluate(() => state.part);
        expect(part === target, `clicked ${target}, page shows ${part}`);
        await page.evaluate(() => { const decks = document.querySelector('button[data-part="Decks"]'); if (decks) decks.click(); });
        return target;
    });

    await check(view, "Search", async () => {
        const input = page.locator("#searchInput");
        expect(await input.count() === 1, "no search box");
        await input.fill("baker");
        await page.waitForTimeout(400);
        const count = await liveCards(page);
        expect(count > 0, "\"baker\" found nothing");
        await shot("search");
        await input.fill("");
        await page.waitForTimeout(300);
        return `"baker": ${count} deals`;
    });

    await check(view, "Retailer link", async () => {
        const href = await page.evaluate(() => {
            const link = document.querySelector("#cardGrid .deal-card .card-store-link");
            return link ? link.href : "";
        });
        expect(/^https:\/\//.test(href), "first card has no https store link");
        return new URL(href).hostname;
    });

    await check(view, "Quick View", async () => {
        const opened = await page.evaluate(() => {
            const card = document.querySelector("#cardGrid .deal-card");
            if (!card || typeof openQuickView !== "function") return false;
            openQuickView(card, true);
            return !document.getElementById("quickView").hidden;
        });
        expect(opened, "Quick View did not open");
        await page.waitForTimeout(300);
        await shot("quickview");
        await page.keyboard.press("Escape");
        return "opens";
    });

    await check(view, "Alerts stay offline", async () => {
        const mode = await page.evaluate(async () => {
            if (typeof openAlerts !== "function") return "";
            await openAlerts({});
            return alertsUi && alertsUi.config ? alertsUi.config.mode : "";
        });
        if (!mode) return { skip: "no alerts panel" };
        expect(mode !== "live", "alerts are live in a preview");
        expect(!forbidden.length, "called " + forbidden[0]);
        await page.keyboard.press("Escape");
        return "mode " + mode;
    });

    record(view, "No page errors", errors.length ? "fail" : "pass", errors.slice(0, 3).join(" | "));
    record(view, "No production calls", forbidden.length ? "fail" : "pass", forbidden.slice(0, 2).join(" | "));
    await context.close();
    return shots;
}

// The ShredDeals homepage (index.html): sport tabs around the SkateDeals
// page in a same-origin frame. Skate shows the catalog; every other sport
// must stay empty (no skate products passed off as BMX), follow the URL, and
// come back with Back.
async function runHomepage(browser, base, view, options) {
    let shell = "";
    try {
        shell = await readFile(join(SITE, "index.html"), "utf8");
    } catch (err) {
        shell = "";
    }
    if (!shell.includes('id="sportTabs"')) {
        record(view, "Homepage sport tabs", "skip", "no ShredDeals homepage");
        return [];
    }
    const context = await browser.newContext(options);
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(String(error)));
    await page.route(/^https?:\/\/(?!127\.0\.0\.1)/, route =>
        (route.request().resourceType() === "image" ? route.continue() : route.abort()));
    const shots = [];
    async function shot(name) {
        const file = `${view}-${name}.png`;
        await page.screenshot({ path: join(outDir, file) });
        shots.push(file);
    }
    const frameCards = () => page.frameLocator("#skateFrame").locator("#cardGrid .deal-card").count();
    const selected = () => page.evaluate(() => {
        const tab = document.querySelector('#sportTabs [role="tab"][aria-selected="true"]');
        return tab ? tab.id.replace(/^sport-/, "") : "";
    });
    let others = [];

    await check(view, "Homepage sport tabs", async () => {
        await page.goto(base + "/index.html", { waitUntil: "load", timeout: 60000 });
        const tabs = await page.evaluate(() => Array.from(document.querySelectorAll('#sportTabs [role="tab"]')).map(tab => tab.id.replace(/^sport-/, "")));
        expect(tabs.length >= 2, "fewer than two sport tabs");
        expect(tabs.includes("skate"), "no Skate tab");
        expect(await selected() === "skate", "Skate is not selected on a fresh visit");
        others = tabs.filter(id => id !== "skate");
        return tabs.join(", ");
    });

    await check(view, "Homepage shows Skate deals", async () => {
        let count = 0;
        for (let i = 0; i < 60 && !count; i++) {
            count = await frameCards().catch(() => 0);
            if (!count) await page.waitForTimeout(500);
        }
        expect(count > 0, "the Skate catalog did not load in the homepage");
        expect(await page.locator("#skateFrame").isVisible(), "the Skate frame is hidden");
        return count + " deal cards";
    });
    await shot("shell");

    await check(view, "Other sports stay empty", async () => {
        if (!others.length) return { skip: "only Skate" };
        for (const sport of others) {
            await page.locator("#sport-" + sport).click();
            await page.waitForTimeout(250);
            expect(new URL(page.url()).searchParams.get("sport") === sport, `URL does not say sport=${sport}`);
            expect(!(await page.locator("#skateFrame").isVisible()), `${sport} still shows the Skate catalog`);
            expect(await page.locator("#comingSoon").isVisible(), `${sport} shows no empty state`);
            if (sport === others[0]) await shot("sport");
        }
        return others.join(", ") + ": no catalog";
    });

    await check(view, "Back and Forward", async () => {
        if (others.length < 2) return { skip: "needs two other sports" };
        await page.goBack();
        await page.waitForTimeout(250);
        const back = await selected();
        expect(back === others[others.length - 2], `Back shows ${back}, expected ${others[others.length - 2]}`);
        await page.goForward();
        await page.waitForTimeout(250);
        expect(await selected() === others[others.length - 1], "Forward did not return");
        await page.locator("#sport-skate").click();
        await page.waitForTimeout(250);
        expect(await page.locator("#skateFrame").isVisible(), "Skate did not come back");
        return "restores the sport";
    });

    record(view, "Homepage page errors", errors.length ? "fail" : "pass", errors.slice(0, 3).join(" | "));
    await context.close();
    return shots;
}

const server = await serve();
const base = `http://127.0.0.1:${server.address().port}`;
await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
const shots = [];
try {
    const desktop = { viewport: { width: 1366, height: 900 } };
    const mobile = { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 };
    shots.push(...await run(browser, base, "desktop", desktop));
    shots.push(...await run(browser, base, "mobile", mobile));
    shots.push(...await runHomepage(browser, base, "desktop", desktop));
    shots.push(...await runHomepage(browser, base, "mobile", mobile));
} finally {
    await browser.close();
    server.close();
}
const failed = checks.filter(entry => entry.status === "fail").length;
await writeFile(join(outDir, "summary.json"), JSON.stringify({ checks, screenshots: shots, failed }, null, 2));
for (const entry of checks) console.log(`${entry.status.toUpperCase().padEnd(4)} ${entry.view.padEnd(7)} ${entry.name}${entry.detail ? " - " + entry.detail : ""}`);
process.exit(failed ? 1 : 0);
