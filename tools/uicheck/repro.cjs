// Reproduce the "finish workout does nothing" bug in a real browser.
const { chromium } = require("playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8793";

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newContext({ viewport: { width: 402, height: 874 } }).then(c => c.newPage());

  const logs = [];
  page.on("console", m => logs.push(`console.${m.type()}: ${m.text()}`));
  page.on("pageerror", e => logs.push(`PAGEERROR: ${e.message}`));
  page.on("requestfailed", r => logs.push(`REQFAILED: ${r.method()} ${r.url()} — ${r.failure()?.errorText}`));
  page.on("response", r => { if (r.url().includes("/api/log")) logs.push(`RESP /api/log: ${r.status()}`); });

  await page.goto(BASE + "/workout", { waitUntil: "networkidle" });
  await page.waitForTimeout(500);

  // Check a few exercises so completion > 60%.
  const checks = await page.$$(".ex-check");
  console.log("exercise checkboxes found:", checks.length);
  for (const c of checks) { await c.click().catch(() => {}); }
  await page.waitForTimeout(200);

  // Click the footer finish button.
  const footerBtn = await page.$(".wk-footer .btn");
  console.log("footer button text:", footerBtn ? await footerBtn.innerText() : "(none)");
  await footerBtn?.click();
  await page.waitForTimeout(400);

  const sheet = await page.$(".rating-sheet");
  console.log("rating sheet visible:", !!sheet);

  // Click the first rating dot.
  const dot = await page.$(".rating-dot");
  console.log("rating dot found:", !!dot);
  await dot?.click();
  await page.waitForTimeout(1500);

  console.log("URL after rating click:", page.url());
  console.log("celebrate shown:", !!(await page.$(".celebrate")));
  console.log("--- captured events ---");
  console.log(logs.join("\n") || "(none)");

  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
