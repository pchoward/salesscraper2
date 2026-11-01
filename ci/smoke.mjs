// Browser smoke test and screenshots for a PR preview (ci/build_preview.py).
//
//   node ci/smoke.mjs SITE_DIR OUT_DIR
//
// Serves SITE_DIR on localhost, opens it in Chromium at desktop and phone
// sizes, and checks what a visitor does first: the page loads clean,
// a category filter, a search, a retailer link, Quick View, the alerts
// panel (which must stay offline in a preview), and sport tabs where the
// page has them. Writes OUT_DIR/summary.json and PNG screenshots. Exits 1
// when a check fails, so CI shows it; screenshots are written either way.

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

    await check(view, "Sport tabs", async () => {
        const tabs = await page.locator("[data-sport]").count();
        if (!tabs) return { skip: "no sport navigation on this page" };
        const sports = await page.evaluate(() => Array.from(document.querySelectorAll("[data-sport]")).map(node => node.getAttribute("data-sport")));
        const other = sports.find(sport => sport && sport !== "skate");
        if (!other) return `${tabs} tab(s)`;
        await page.locator(`[data-sport="${other}"]`).first().click();
        await page.waitForTimeout(300);
        expect(page.url().includes("sport=" + other), "URL does not follow the sport tab");
        await shot("sport");
        return `${sports.length} tabs; ${other} reachable`;
    });

    record(view, "No page errors", errors.length ? "fail" : "pass", errors.slice(0, 3).join(" | "));
    record(view, "No production calls", forbidden.length ? "fail" : "pass", forbidden.slice(0, 2).join(" | "));
    await context.close();
    return shots;
}

const server = await serve();
const base = `http://127.0.0.1:${server.address().port}`;
await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
const shots = [];
try {
    shots.push(...await run(browser, base, "desktop", { viewport: { width: 1366, height: 900 } }));
    shots.push(...await run(browser, base, "mobile", { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 }));
} finally {
    await browser.close();
    server.close();
}
const failed = checks.filter(entry => entry.status === "fail").length;
await writeFile(join(outDir, "summary.json"), JSON.stringify({ checks, screenshots: shots, failed }, null, 2));
for (const entry of checks) console.log(`${entry.status.toUpperCase().padEnd(4)} ${entry.view.padEnd(7)} ${entry.name}${entry.detail ? " - " + entry.detail : ""}`);
process.exit(failed ? 1 : 0);
