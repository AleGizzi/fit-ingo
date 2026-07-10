// Decisive repro: replicate an installed-PWA where the service worker CONTROLS
// the page, then do the finish->rating flow with STRICT clicks. Captures whether
// the /api/log POST is sent, its status, SW controller state, and any errors.
const { chromium } = require("playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8793";

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 402, height: 874 }, serviceWorkers: "allow" });
  const page = await ctx.newPage();
  const ev = [];
  page.on("console", m => ev.push(`console.${m.type()}: ${m.text()}`));
  page.on("pageerror", e => ev.push(`PAGEERROR: ${e.message}`));
  page.on("requestfailed", r => ev.push(`REQFAILED ${r.method()} ${r.url()} — ${r.failure()?.errorText}`));
  page.on("response", r => { if (r.url().includes("/api/log")) ev.push(`RESP /api/log ${r.request().method()} -> ${r.status()} (from SW: ${r.fromServiceWorker?.() ?? "?"})`); });

  // First load registers the SW.
  await page.goto(BASE + "/today", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  // Reload so the page is controlled by the now-active SW (installed-PWA condition).
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const controlled = await page.evaluate(() => !!navigator.serviceWorker.controller);
  ev.push(`SW controls page: ${controlled}`);

  await page.goto(BASE + "/workout", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);

  // Mark a couple items done (partial, like a real user).
  const checks = await page.$$(".ex-check");
  for (let i = 0; i < 3 && i < checks.length; i++) await checks[i].click();
  await page.waitForTimeout(150);

  // Open the rating sheet.
  await page.click(".wk-footer .btn");
  await page.waitForTimeout(300);
  const sheet = !!(await page.$(".rating-sheet"));
  ev.push(`rating sheet visible: ${sheet}`);

  // STRICT click on a rating dot — throws if covered/intercepted.
  try {
    await page.click(".rating-dot", { timeout: 3000 });
    ev.push("rating-dot click: OK");
  } catch (e) {
    ev.push("rating-dot click FAILED: " + e.message.split("\n")[0]);
  }
  await page.waitForTimeout(2000);
  ev.push(`URL after: ${page.url().replace(BASE, "")}`);
  ev.push(`celebrate shown: ${!!(await page.$(".celebrate"))}`);

  // Did it persist server-side?
  const log = await (await ctx.request.get(BASE + "/api/today")).json();
  ev.push(`server today.log after: ${JSON.stringify(log.log)}`);

  console.log(ev.join("\n"));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
