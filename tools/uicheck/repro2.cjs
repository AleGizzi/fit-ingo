// Test the skip path and partial-completion path.
const { chromium } = require("playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8793";

async function run(label, { check, useSkip }) {
  const browser = await chromium.launch();
  const page = await browser.newContext({ viewport: { width: 402, height: 874 } }).then(c => c.newPage());
  const logs = [];
  page.on("console", m => logs.push(`console.${m.type()}: ${m.text()}`));
  page.on("pageerror", e => logs.push(`PAGEERROR: ${e.message}`));
  page.on("response", r => { if (r.url().includes("/api/log")) logs.push(`RESP /api/log ${r.request().method()}: ${r.status()}`); });

  await page.goto(BASE + "/workout", { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  const checks = await page.$$(".ex-check");
  for (let i = 0; i < check && i < checks.length; i++) await checks[i].click().catch(() => {});
  await page.waitForTimeout(150);
  await (await page.$(".wk-footer .btn"))?.click();
  await page.waitForTimeout(300);
  const sheetVisible = !!(await page.$(".rating-sheet"));
  if (useSkip) await (await page.$(".rating-skip"))?.click();
  else await (await page.$(".rating-dot"))?.click();
  await page.waitForTimeout(1800);
  console.log(`\n[${label}] checked=${check} skip=${useSkip} | sheet=${sheetVisible} | url=${page.url().replace(BASE,"")} | celebrate=${!!(await page.$(".celebrate"))}`);
  console.log("  events:", logs.join(" | ") || "(none)");
  await browser.close();
}

(async () => {
  await run("skip, 0 done", { check: 0, useSkip: true });
  await run("rating, 2 done", { check: 2, useSkip: false });
  await run("skip, 2 done", { check: 2, useSkip: true });
})().catch(e => { console.error(e); process.exit(1); });
