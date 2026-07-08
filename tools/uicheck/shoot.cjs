// UI screenshot harness for Fit-ingo.
// Assumes the Flask server is already running and serving the built dist.
// Seeds a profile + some activity via the API, then screenshots each screen
// at a phone viewport in both light and dark color schemes.
//
// Usage: BASE=http://localhost:8792 OUT=./shots node shoot.cjs
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const BASE = process.env.BASE || "http://localhost:8792";
const OUT = process.env.OUT || path.join(__dirname, "shots");

async function seed() {
  const j = (p, body, method = "POST") =>
    fetch(BASE + p, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  // 6 training days so "today" is a training day (workout screen renders).
  await j("/api/profile", {
    name: "Ale", age: 32, sex: "male", height_cm: 178, weight_kg: 82,
    goal: "gain_muscle", level: "intermediate", impact: "low",
    equipment: "dumbbells", days_per_week: 6, session_minutes: 40,
    limitations: [], diet_pref: "any",
  });
  // Some weight history + a couple completed days for Progress/streak.
  const today = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today); d.setDate(today.getDate() - i);
    const iso = d.toISOString().slice(0, 10);
    await j("/api/weight", { weight_kg: 82 - i * 0.2, date: iso });
    if (i > 0 && i % 2 === 0)
      await j("/api/log", { date: iso, completed: true, items_done: ["a"], items_total: 6, perceived_difficulty: 3 });
  }
}

const SCREENS = [
  ["onboarding", "/onboarding"],
  ["today", "/today"],
  ["library", "/library"],
  ["progress", "/progress"],
  ["diet", "/diet"],
  ["settings", "/settings"],
  ["workout", "/workout"],
];

async function shoot() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({
      viewport: { width: 402, height: 874 },
      deviceScaleFactor: 2,
      colorScheme: scheme,
    });
    const page = await ctx.newPage();
    for (const [name, route] of SCREENS) {
      await page.goto(BASE + route, { waitUntil: "networkidle" });
      await page.waitForTimeout(700); // let charts/animations settle
      const file = path.join(OUT, `${name}-${scheme}.png`);
      await page.screenshot({ path: file, fullPage: true });
      console.log("shot", file);
    }
    await ctx.close();
  }
  await browser.close();
}

(async () => {
  await seed();
  await shoot();
  console.log("done ->", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
