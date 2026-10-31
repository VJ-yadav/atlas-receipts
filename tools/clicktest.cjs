// Opens receipt links in a real browser and checks the quoted sentence is on the rendered page.
// Run from ../mass-ai-atlas (for Playwright): node ../atlas-receipts/tools/clicktest.cjs <items.json>
const { chromium } = require(process.cwd() + '/node_modules/playwright');
const items = require(process.argv[2]);
const norm = s => s.replace(/[’‘]/g,"'").replace(/[“”]/g,'"').replace(/\s+/g,' ').trim().toLowerCase();
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ userAgent: 'AtlasReceipts/0.1 (+https://github.com/VJ-yadav/atlas-receipts; TOA hackathon verifier)' });
  for (const it of items) {
    let res;
    try { await p.goto(it.url, { waitUntil: 'domcontentloaded', timeout: 20000 }); await p.waitForTimeout(1500);
      const txt = norm(await p.evaluate(() => document.body.innerText));
      const words = norm(it.quote).split(' '); const head = words.slice(0, 4).join(' '), tail = words.slice(-4).join(' ');
      res = txt.includes(norm(it.quote)) ? 'FOUND (whole sentence)' : (txt.includes(head) && txt.includes(tail)) ? 'FOUND (start and end)' : 'NOT FOUND';
    } catch (e) { res = 'ERROR ' + e.message.slice(0, 60); }
    console.log(res.padEnd(24), it.key);
    await new Promise(r => setTimeout(r, 1000));
  }
  await b.close();
})();
