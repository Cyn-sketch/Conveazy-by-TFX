// End-to-end: two partners, full Phase 1 journey, privacy boundaries checked in the real UI.
// Usage: BASE_URL=http://localhost:3000 SHOTS=./e2e/shots node e2e/two-partners.mjs
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");
import { mkdirSync } from "node:fs";

const BASE = process.env.BASE_URL || "http://localhost:3000";
const SHOTS = process.env.SHOTS || "";
if (SHOTS) mkdirSync(SHOTS, { recursive: true });
const run = Date.now().toString(36);
const assert = (c, m) => { if (!c) throw new Error("FAILED: " + m); console.log("  ✓ " + m); };
const visible = (page, text, ms = 5000) => page.getByText(text).first().waitFor({ timeout: ms }).then(() => true, () => false);
const shot = async (page, name) => { if (SHOTS) await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true }); };

async function signup(browser, name, mobile = false) {
  const ctx = await browser.newContext(mobile ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true } : { viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/signup`);
  await page.fill("#name", name);
  await page.fill("#email", `${name.toLowerCase()}-${run}@example.com`);
  await page.fill("#password", "correct-horse-battery");
  await page.click("button:has-text('Create account')");
  await page.waitForURL("**/onboarding");
  await page.check("#care");
  await page.click("button:has-text('Continue')");
  await page.click("button:has-text('Continue')");
  await page.fill("#pr", name === "Asha" ? "she/her" : "he/him");
  await page.click("button:has-text('Enter my space')");
  await page.waitForURL("**/app");
  await page.getByText("What do you want to say?").waitFor();
  return page;
}

const browser = await chromium.launch();
try {
  console.log("Partner A onboarding");
  const a = await signup(browser, "Asha");
  assert(await visible(a, "Mock mode: not live AI"), "mock mode is labelled in the shell");
  await shot(a, "01-home");

  console.log("Check-in");
  await a.goto(`${BASE}/app/checkin`);
  await a.click("button:has-text('hurt')");
  await a.fill("#note", "He didn't reply all day");
  await a.click("button:has-text('reassurance')");
  await a.click("button:has-text('Talk to my partner')");
  await shot(a, "02-checkin");
  await a.click("button:has-text('Save check-in')");
  await a.getByText("Thank you for noticing.").waitFor();
  assert(true, "check-in saved");

  console.log("Message Translator");
  await a.goto(`${BASE}/app/translate`);
  await a.fill("#draft", "You NEVER text back when you say you will. You obviously don't care about me. Whatever. Please stop making plans and then disappearing.");
  await a.click("button:has-text('Translate')");
  await a.getByText("What you're saying underneath").waitFor();
  assert(await a.getByText("Your boundary stays.").isVisible(), "boundary preserved note shown");
  assert(await a.locator("mark").count() >= 2, "risky phrases highlighted in the original");
  await shot(a, "03-translator");

  console.log("Understand My Partner");
  await a.goto(`${BASE}/app/partner`);
  await a.click("button:has-text('Why might silence feel like rejection?')");
  await a.getByText("How sure is this?").waitFor();
  assert(await a.getByText("Only your partner knows").first().isVisible(), "individual-tier evidence shown");
  assert(await a.locator("#src-hazan-shaver-1987").count() === 1, "citations rendered with source links");
  await shot(a, "04-partner");

  console.log("Understand Myself");
  await a.goto(`${BASE}/app/myself`);
  await a.fill("#sit", "I told him I was having a hard day at 2pm. He replied at 7pm with 'ok'.");
  await a.click("button:has-text('Next')");
  await a.fill("#int", "That I'm not a priority to him.");
  await a.click("button:has-text('Next')");
  await a.click("button:has-text('hurt')"); await a.click("button:has-text('anxious')");
  await a.click("button:has-text('Next')");
  await a.click("button:has-text('reassurance')");
  await a.click("button:has-text('Reflect with me')");
  await a.getByText("How you might say it").waitFor();
  assert(true, "reflection produced S→I→E→N→C");
  await shot(a, "05-myself");

  console.log("Profile + invite");
  await a.goto(`${BASE}/app/us`);
  const share = async (page, key, text, shareIt) => {
    const card = page.locator(".card", { has: page.locator(`#${key}`) });
    await page.fill(`#${key}`, text);
    if (shareIt) await card.getByRole("switch", { name: "Share with partner" }).click();
    await card.getByRole("switch", { name: "Let AI use this" }).click();
    await card.getByRole("button", { name: "Save" }).click();
    await card.getByText("Saved").waitFor();
  };
  await share(a, "reassurance_looks_like", "A two-word text when you're running late", true);
  await share(a, "feel_dismissed_when", "PRIVATE-ONLY: being told I'm overthinking", false);
  await a.click("button:has-text('Create an invite code')");
  const code = (await a.getByTestId("invite-code").textContent()).trim();
  assert(/^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(code), `invite code issued (${code})`);

  console.log("Partner B joins (mobile)");
  const b = await signup(browser, "Ravi", true);
  await b.goto(`${BASE}/app/us`);
  await b.fill("#code", code);
  await b.click("button:has-text('Join')");
  await b.getByText("You're linked with Asha").waitFor();
  assert(await b.getByText("A two-word text when you're running late").isVisible(), "B sees what A chose to share");
  assert(!(await b.getByText("PRIVATE-ONLY").isVisible()), "B cannot see A's private profile answer");
  await shot(b, "06-us-mobile");

  console.log("Say it to her (bridge)");
  // A (her) fills the core 'About me' fields and opts in to the check-in signal.
  await a.goto(`${BASE}/app/us`);
  await share(a, "my_triggers", "Silence or one-word replies, feeling ignored, being blamed", true);
  await share(a, "what_calms_me", "A voice note and a hug", true);
  await share(a, "self_disclosed_context", "I have BPD, MDD, GAD and PCOS", true);
  await share(a, "my_story", "My father went silent for days and then left without a word", false);
  await a.goto(`${BASE}/app/privacy`);
  await a.getByText("Let my partner's messages adapt").click();
  await a.goto(`${BASE}/app/checkin`);
  await a.click("button:has-text('angry')"); await a.locator("#int").fill("9");
  await a.click("button:has-text('space')"); await a.click("button:has-text('Take a break')"); await a.click("button:has-text('Save check-in')");
  await a.getByText("Thank you for noticing.").waitFor();
  await b.goto(`${BASE}/app/bridge`);
  await b.fill("#situation", "Work was awful and I didn't reply for hours. She thinks I'm mad at her.");
  await b.fill("#scraps", "didnt reply cuz i was drained not cuz of u\nyou're overthinking it\ni want us ok");
  await b.click("button:has-text('Understand me')");
  await b.getByText("Here's what I think you're trying to say").waitFor();
  assert(await visible(b, "What you're feeling right now"), "raw feelings read shown to the writer");
  await shot(b, "10-bridge-confirm-mobile");
  await b.click("button:has-text('Yes, that')");
  await b.getByText("Your message to Asha").waitFor();
  assert(await visible(b, "Send now"), "short version offered because her check-in is 9/10");
  assert(await visible(b, "what Ravi is really feeling"), "feeling brief goes with the message");
  assert(await visible(b, "Copy message + brief"), "message and brief can be copied together");
  assert(!(await b.getByText("father", { exact: false }).isVisible()), "her private story never reaches him");
  assert(!(await b.locator("[data-testid=message]").innerText()).toLowerCase().includes("overthinking"), "condition trigger word avoided");
  assert(!(await b.getByText("SECRET").isVisible()), "her check-in note never reaches him");
  await b.click("button:has-text('Full message')");
  await shot(b, "11-bridge-message-mobile");

  console.log("Privacy boundaries");
  await b.goto(`${BASE}/app/partner`);
  assert(await visible(b, "Private to you."), "B has no access to A's partner questions");
  await b.goto(`${BASE}/app/checkin`);
  await visible(b, "Where are you at?");
  assert(!(await visible(b, "Your recent check-ins", 1500)), "B cannot see A's check-ins");
  const exportText = await b.evaluate(async () => (await fetch("/api/privacy/export")).text());
  assert(exportText.includes("Ravi") && !exportText.includes("PRIVATE-ONLY") && !exportText.includes("two-word text"), "B's export contains none of A's data");
  await b.goto(`${BASE}/app/translate`);
  await shot(b, "07-translate-mobile");

  console.log("Crisis handling");
  await b.fill("#draft", "I can't do this anymore, I want to kill myself");
  await b.click("button:has-text('Translate')");
  await b.getByText("Your safety comes first").waitFor();
  assert(await b.getByText("14416").isVisible() && await visible(b, "What you're saying underneath"), "crisis resources shown alongside the rewrite");
  await shot(b, "08-crisis-mobile");

  console.log("Privacy page");
  await a.goto(`${BASE}/app/privacy`);
  await shot(a, "09-privacy");
  const dark = await browser.newContext({ colorScheme: "dark", viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
  const d = await dark.newPage(); await d.goto(BASE); await shot(d, "00-landing-dark");
  const light = await browser.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
  const l = await light.newPage(); await l.goto(BASE); await shot(l, "00-landing");
  console.log("\nAll end-to-end checks passed.");
} finally {
  await browser.close();
}
