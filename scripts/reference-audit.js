const fs = require('fs');
const path = require('path');
const { chromium } = require('../renderer/node_modules/playwright-core');

const sites = [
  ['yuhim', 'https://yuhim.ru/'], ['saas-421040', 'https://421040.lp.tobiz.net/'],
  ['beloussov', 'https://start.beloussov.ru/'], ['toplivopro', 'https://toplivopro.ru/'],
  ['ref-405788', 'https://405788.lp.tobiz.net/'], ['ref-381594', 'https://381594.lp.tobiz.net/'],
  ['ref-380853', 'https://380853.lp.tobiz.net/'], ['ref-380539', 'https://380539.lp.tobiz.net/'],
  ['ref-377038', 'https://377038.lp.tobiz.net/'], ['greenwood', 'https://greenwood-villa.ru/'],
  ['ref-373389', 'https://373389.lp.tobiz.net/'], ['cherevatkin', 'https://cherevatkin.ru/'],
  ['ref-367091', 'https://367091.lp.tobiz.net/'], ['auto-up', 'https://auto-up.ru/'],
  ['aktive-montage', 'https://anapa.aktive-montage.ru/'], ['zona-auto', 'https://zona-auto.ru/'],
  ['woodenbull', 'https://woodenbull-vrn.ru/'],
];

function executable() {
  return ['C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'].find(fs.existsSync);
}

function slugText(text) { return (text || '').trim().replace(/\s+/g, ' ').slice(0, 180); }

async function metrics(page) {
  return page.evaluate(() => {
    const visible = el => { const s = getComputedStyle(el), r = el.getBoundingClientRect();
      return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0 && r.width > 2 && r.height > 2; };
    const freq = (selector, prop) => {
      const map = new Map();
      [...document.querySelectorAll(selector)].filter(visible).forEach(el => {
        const value = getComputedStyle(el)[prop]; if (value) map.set(value, (map.get(value) || 0) + 1);
      });
      return [...map.entries()].sort((a,b) => b[1]-a[1]).slice(0,8).map(([value,count]) => ({value,count}));
    };
    const sample = selector => { const el = [...document.querySelectorAll(selector)].find(visible); if (!el) return null;
      const s = getComputedStyle(el); return { text: (el.innerText || '').trim().replace(/\s+/g,' ').slice(0,180),
        fontFamily:s.fontFamily,fontSize:s.fontSize,fontWeight:s.fontWeight,lineHeight:s.lineHeight,
        color:s.color,backgroundColor:s.backgroundColor,textAlign:s.textAlign }; };
    const sectionSelector = '.section, section, main > div';
    const sections = [...document.querySelectorAll(sectionSelector)].filter(visible);
    const ctas = [...document.querySelectorAll('a,button,input[type=submit]')].filter(visible)
      .map(el => (el.innerText || el.value || '').trim().replace(/\s+/g,' ')).filter(t => t.length > 2 && t.length < 90);
    return { title:document.title, height:document.documentElement.scrollHeight,
      sectionCount:sections.length, h1:sample('h1'), h2:sample('h2'), body:sample('p,li'), button:sample('a.btn1,a.btn2,a.btn3,a.btn4,a.btn5,button,input[type=submit]'),
      fonts:freq('h1,h2,h3,p,li,a,button','fontFamily'), colors:freq('h1,h2,h3,p,li,a,button','color'),
      backgrounds:freq('.section,section,body','backgroundColor'), headings:[...document.querySelectorAll('h1,h2')].filter(visible).map(x => x.innerText.trim().replace(/\s+/g,' ').slice(0,160)).slice(0,14),
      ctas:[...new Set(ctas)].slice(0,18), images:[...document.images].filter(visible).length,
      forms:[...document.forms].filter(visible).length };
  });
}

async function contactSheet(browser, files, output, title) {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  const cards = files.map(file => {
    const data = fs.readFileSync(file.path).toString('base64');
    return `<figure><img src="data:image/png;base64,${data}"><figcaption>${file.name}</figcaption></figure>`;
  }).join('');
  await page.setContent(`<style>body{margin:0;padding:24px;font:16px Arial;background:#e8e8e8}h1{font-size:28px}main{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}figure{margin:0;background:#fff;padding:8px}img{width:100%;height:270px;object-fit:cover;object-position:top}figcaption{padding:8px 2px 2px;font-weight:700}</style><h1>${title}</h1><main>${cards}</main>`);
  await page.screenshot({ path: output, fullPage: true });
  await page.close();
}

(async () => {
  const output = path.resolve(process.argv[2] || 'reference-audit'); fs.mkdirSync(output,{recursive:true});
  const browser = await chromium.launch({ executablePath: executable(), headless:true });
  const results=[]; const desktopFiles=[]; const mobileFiles=[];
  for (const [name,url] of sites) {
    const entry={name,url};
    try {
      for (const [mode,viewport] of [['desktop',{width:1440,height:900}],['mobile',{width:390,height:844}]]) {
        const context=await browser.newContext({viewport,ignoreHTTPSErrors:true}); const page=await context.newPage();
        await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000}); await page.waitForTimeout(2500);
        if(mode==='desktop') entry.metrics=await metrics(page);
        const file=path.join(output,`${name}-${mode}.png`); await page.screenshot({path:file});
        (mode==='desktop'?desktopFiles:mobileFiles).push({name,path:file}); await context.close();
      }
      entry.ok=true;
    } catch(error) { entry.ok=false; entry.error=String(error.message||error); }
    results.push(entry); process.stderr.write(`${name}: ${entry.ok?'ok':'failed'}\n`);
  }
  fs.writeFileSync(path.join(output,'metrics.json'),JSON.stringify(results,null,2));
  await contactSheet(browser,desktopFiles,path.join(output,'desktop-contact-sheet.png'),'TOBIZ references - desktop');
  await contactSheet(browser,mobileFiles,path.join(output,'mobile-contact-sheet.png'),'TOBIZ references - mobile');
  await browser.close();
  process.stdout.write(JSON.stringify({ok:results.filter(x=>x.ok).length,total:results.length,output}));
})();
