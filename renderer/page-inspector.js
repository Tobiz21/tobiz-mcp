const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', chunk => chunks.push(chunk));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    process.stdin.on('error', reject);
  });
}

function browserPath(explicit) {
  const candidates = [explicit, process.env.TOBIZ_BROWSER_BIN,
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    '/usr/bin/microsoft-edge', '/usr/bin/google-chrome', '/usr/bin/chromium'];
  return candidates.find(value => value && fs.existsSync(value));
}

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
};

async function inspect(page, forbiddenTerms = []) {
  return page.evaluate((forbiddenTerms) => {
    const visible = el => {
      const s = getComputedStyle(el); const r = el.getBoundingClientRect();
      return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity) > 0 && r.width > 1 && r.height > 1;
    };
    const ref = el => ({ tag: el.tagName.toLowerCase(), id: el.id || null,
      classes: [...el.classList].slice(0, 5), text: (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 120) });
    const style = el => { const s = getComputedStyle(el); return {
      fontFamily: s.fontFamily, fontSize: s.fontSize, fontWeight: s.fontWeight,
      lineHeight: s.lineHeight, color: s.color, backgroundColor: s.backgroundColor,
      textAlign: s.textAlign, padding: s.padding, margin: s.margin, borderRadius: s.borderRadius,
    }; };
    const rgb = value => {
      const match = String(value || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/i);
      return match ? [Number(match[1]), Number(match[2]), Number(match[3]), match[4] === undefined ? 1 : Number(match[4])] : null;
    };
    const luminance = color => {
      const channels = color.slice(0, 3).map(value => { const x = value / 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; });
      return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
    };
    const contrast = (a, b) => { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
    const background = el => {
      for (let node = el; node; node = node.parentElement) {
        const color = rgb(getComputedStyle(node).backgroundColor);
        if (color && color[3] >= .75) return color;
        const overlay = node.matches?.('[id^="b_"]') ? node.querySelector(':scope > .back_dark') : null;
        if (overlay && visible(overlay)) {
          const raw = `${overlay.style.background} ${getComputedStyle(overlay).backgroundImage}`;
          const hex = raw.match(/#([0-9a-f]{6})/i);
          if (hex) return [parseInt(hex[1].slice(0,2),16), parseInt(hex[1].slice(2,4),16), parseInt(hex[1].slice(4,6),16), 1];
        }
      }
      return [255, 255, 255, 1];
    };
    const sample = selector => { const el = [...document.querySelectorAll(selector)].find(visible); return el ? { ...ref(el), style: style(el) } : null; };
    const links = [...document.querySelectorAll('a, button, input[type=submit], input[type=button]')].filter(visible);
    const badButtons = links.map(el => {
      const href = el.getAttribute('href'); const target = href && href.startsWith('#') ? document.querySelector(href) : null;
      const hasHandler = !!(el.onclick || el.getAttribute('onclick') || el.dataset.action || el.dataset.target || el.dataset.bsTarget || el.dataset.toggle || el.dataset.bsToggle);
      let issue = null;
      if (el.tagName === 'A' && (!href || href === '#') && !hasHandler) issue = 'no_action';
      else if (href && href.startsWith('#') && !target && !hasHandler) issue = 'missing_anchor';
      return issue ? { ...ref(el), href, issue } : null;
    }).filter(Boolean);
    const forms = [...document.querySelectorAll('form')].map(form => {
      const fields = [...form.querySelectorAll('input, textarea, select')].filter(el => !['hidden','submit','button'].includes(el.type));
      const submits = [...form.querySelectorAll('button, input[type=submit], input[type=button]')];
      const formVisible = visible(form);
      const fieldIssues = fields.map(el => {
        const s = getComputedStyle(el); const placeholder = getComputedStyle(el, '::placeholder').color;
        const issues = [];
        if (s.color === s.backgroundColor) issues.push('text_matches_background');
        if (!el.name) issues.push('missing_name');
        if (formVisible && !visible(el)) issues.push('not_visible');
        return issues.length ? { ...ref(el), issues, color: s.color, backgroundColor: s.backgroundColor, placeholder } : null;
      }).filter(Boolean);
      return { ...ref(form), visible: formVisible, action: form.getAttribute('action'), method: form.method, fields: fields.length,
        submits: submits.length, canSubmit: fields.length > 0 && submits.length > 0, issues: fieldIssues };
    });
    const popups = [...document.querySelectorAll('[class*=popup], [class*=modal], [role=dialog]')].map(el => ({ ...ref(el), visible: visible(el) })).slice(0, 100);
    const allVisible = [...document.body.querySelectorAll('*')].filter(visible);
    const overflow = allVisible.filter(el => { const r = el.getBoundingClientRect(); return r.right > innerWidth + 2 || r.left < -2; }).slice(0, 100).map(ref);
    const images = [...document.images].map(img => ({ src: img.currentSrc || img.src, alt: img.alt || '', complete: img.complete,
      naturalWidth: img.naturalWidth, visible: visible(img) }));
    const textContrast = [...document.querySelectorAll('h1,h2,h3,h4,p,.form_title,.form_text,.field_title')]
      .filter(el => visible(el) && [...el.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim()))
      .map(el => {
        const s = getComputedStyle(el); const fg = rgb(s.color); const bg = background(el);
        if (!fg || !bg) return null;
        const ratio = contrast(fg, bg); const large = parseFloat(s.fontSize) >= 24 || (parseFloat(s.fontSize) >= 18.66 && Number(s.fontWeight) >= 700);
        return ratio < (large ? 3 : 4.5) ? { ...ref(el), ratio: Number(ratio.toFixed(2)), color: s.color, background: bg.slice(0,3) } : null;
      }).filter(Boolean).slice(0, 100);
    const blockIssues = [];
    for (const block of [...document.querySelectorAll('[id^="b_"]')].filter(visible)) {
      const inner = block.querySelector(':scope > .section_inner');
      if (!inner) continue;
      const rect = inner.getBoundingClientRect();
      const children = [...inner.children].filter(visible).map(el => ({ el, rect: el.getBoundingClientRect() }));
      for (const item of children) {
        if (item.rect.left < rect.left - 3 || item.rect.right > rect.right + 3) blockIssues.push({ block: block.id, code: 'child_outside_container', child: ref(item.el) });
      }
      if (innerWidth >= 1100) {
        const footerCols = children.filter(item => ['logo','address-and-ua','phone-and-address'].some(name => item.el.classList.contains(name)));
        if (footerCols.length === 3 && Math.max(...footerCols.map(x => x.rect.top)) - Math.min(...footerCols.map(x => x.rect.top)) > 80) blockIssues.push({ block: block.id, code: 'footer_columns_stacked_desktop' });
      }
    }
    const bodyText = document.body.innerText.replace(/\s+/g, ' ');
    const termMatches = (forbiddenTerms || []).filter(term => typeof term === 'string' && term.trim()).map(term => {
      const escaped = term.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const matches = bodyText.match(new RegExp(escaped, 'giu')) || [];
      return matches.length ? { term, count: matches.length } : null;
    }).filter(Boolean);
    return {
      title: document.title, url: location.href,
      document: { scrollWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth,
        overflowX: document.documentElement.scrollWidth > innerWidth + 2 },
      computedStyles: { body: sample('body'), h1: sample('h1'), h2: sample('h2'), paragraph: sample('p'),
        link: sample('a'), button: sample('a.btn1, a.btn2, a.btn3, a.btn4, a.btn5, button, input[type=submit]'),
        input: sample('input:not([type=hidden]), textarea') },
      interactions: { controls: links.length, broken: badButtons, forms, popups },
      layout: { horizontalOverflow: overflow, blockIssues, textContrast },
      media: { images: images.length, brokenImages: images.filter(i => i.complete && i.naturalWidth === 0), missingAlt: images.filter(i => i.visible && !i.alt).length },
      content: { emptyHeadings: [...document.querySelectorAll('h1,h2,h3,h4')].filter(el => visible(el) && !el.innerText.trim()).map(ref), termMatches },
    };
  }, forbiddenTerms);
}

(async () => {
  let browser;
  try {
    const request = JSON.parse(await readStdin());
    const executablePath = browserPath(request.browser_bin);
    if (!executablePath) throw new Error('Edge/Chrome executable not found');
    if (request.screenshot) fs.mkdirSync(request.output_dir, { recursive: true });
    browser = await chromium.launch({ executablePath, headless: true, args: ['--disable-dev-shm-usage'] });
    const result = { ok: true, url: request.url, viewports: {}, consoleErrors: [], pageErrors: [] };
    for (const name of request.viewports || ['desktop', 'mobile']) {
      if (!VIEWPORTS[name]) continue;
      const context = await browser.newContext({ viewport: VIEWPORTS[name], ignoreHTTPSErrors: true });
      const page = await context.newPage();
      page.on('console', msg => { if (msg.type() === 'error') result.consoleErrors.push({ viewport: name, text: msg.text().slice(0, 500) }); });
      page.on('pageerror', error => result.pageErrors.push({ viewport: name, text: String(error).slice(0, 500) }));
      await page.goto(request.url, { waitUntil: 'domcontentloaded', timeout: request.timeout_ms || 45000 });
      await page.waitForLoadState('load', { timeout: Math.min(request.timeout_ms || 45000, 15000) }).catch(() => {});
      await page.evaluate(() => document.fonts?.ready).catch(() => {});
      const report = await inspect(page, request.forbidden_terms || []);
      if (request.screenshot) {
        const file = path.join(request.output_dir, `${name}.png`);
        await page.screenshot({ path: file, fullPage: true });
        report.screenshot = file;
      }
      result.viewports[name] = report;
      await context.close();
    }
    process.stdout.write(JSON.stringify(result));
  } catch (error) {
    process.stdout.write(JSON.stringify({ ok: false, error: String(error.message || error) }));
    process.exitCode = 1;
  } finally { if (browser) await browser.close(); }
})();
