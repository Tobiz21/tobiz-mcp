// Рантайм рендера блоков: воспроизводит то, что делает редактор TOBIZ перед отправкой
// SaveBlocks. Проверено побайтовым совпадением с настоящим `cache` (docs/spikes/S-5-render.md).
//
// Из чего состоит совпадение (любой пропущенный пункт даёт расхождение):
//   1. underscore 1.8.3 — файл вендора /js/underscore-min.js, а не свежая версия;
//   2. шаблоны блоков из /js/blocks2.js (tobiz.blocks[].template);
//   3. хелперы вендора — объект из _.mixin({...}) в editor.min.js, целиком;
//   4. глобалы замыкания редактора: A (= window.tobiz) и I (= window.tobiz.isValidValue);
//   5. методы приложения вида A.ParseVKVideoLink (в бандле объявлены через локальные алиасы);
//   6. DOM-раундтрип через jsdom: prepend(<span class="block_anchor">) + data-id/id + outerHTML;
//   7. цепочка строковых замен, ровно в том порядке, что в обработчике «Сохранить».
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { JSDOM } = require('jsdom');

const BUNDLES = [
  'editor.min.js',
  'editor.bundle.min.js',
  'flex_tools.min.js',
  'script.min.js',
];

// --- 1. объект _.mixin({...}) из editor.min.js ---
function findMixinObject(src) {
  const start = src.indexOf('_.mixin({');
  if (start < 0) throw new Error('_.mixin не найден в editor.min.js (изменилась сборка вендора)');
  const open = start + '_.mixin('.length;
  let i = open;
  let depth = 0;
  let prevToken = '';
  while (i < src.length) {
    const c = src[i];
    if (c === '"' || c === "'" || c === '`') {
      const quote = c;
      i++;
      while (i < src.length && src[i] !== quote) {
        if (src[i] === '\\') i++;
        i++;
      }
      prevToken = 'str';
      i++;
      continue;
    }
    if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; continue; }
    if (c === '/' && src[i + 1] === '*') { i = src.indexOf('*/', i) + 2; continue; }
    if (c === '/' && /[=(,:[!&|?{};+\-*%<>~^]|return|typeof|case/.test(prevToken || '=')) {
      i++;
      let inClass = false;
      while (i < src.length) {
        const d = src[i];
        if (d === '\\') { i += 2; continue; }
        if (d === '[') inClass = true;
        else if (d === ']') inClass = false;
        else if (d === '/' && !inClass) break;
        else if (d === '\n') break;
        i++;
      }
      i++;
      prevToken = 'regex';
      continue;
    }
    if (c === '{' || c === '(' || c === '[') depth++;
    if (c === '}' || c === ')' || c === ']') {
      depth--;
      if (depth === 0) return src.slice(open, i + 1);
    }
    if (!/\s/.test(c)) prevToken = c;
    i++;
  }
  throw new Error('не найден конец объекта _.mixin');
}

// --- 2. методы приложения: App.X / window.tobiz.X / <алиас>.X для нужных имён ---
function extractAppMethods(sources, neededNames) {
  const combined = sources.join('\n');
  const out = new Map();
  if (!neededNames || !neededNames.length) return out;
  const pattern = new RegExp(
    `(?:[A-Za-z_$][A-Za-z0-9_$]*\\.)(${neededNames.join('|')})\\s*=\\s*function\\s*\\(`, 'g');
  let match;
  while ((match = pattern.exec(combined))) {
    const name = match[1];
    if (out.has(name)) continue;
    const fnIndex = combined.lastIndexOf('function', match.index + match[0].length);
    if (fnIndex < 0) continue;
    const parenIndex = combined.indexOf('(', fnIndex + 8);
    let i = parenIndex;
    let depth = 0;
    for (; i < combined.length; i++) {
      const c = combined[i];
      if (c === '(') depth++;
      else if (c === ')') { depth--; if (depth === 0) break; }
      else if (c === '"' || c === "'" || c === '`') {
        const quote = c; i++;
        while (i < combined.length && combined[i] !== quote) { if (combined[i] === '\\') i++; i++; }
      }
    }
    const braceIndex = combined.indexOf('{', i);
    if (braceIndex < 0) continue;
    let j = braceIndex;
    let braces = 0;
    for (; j < combined.length; j++) {
      const c = combined[j];
      if (c === '{') braces++;
      else if (c === '}') { braces--; if (braces === 0) break; }
      else if (c === '"' || c === "'" || c === '`') {
        const quote = c; j++;
        while (j < combined.length && combined[j] !== quote) { if (combined[j] === '\\') j++; j++; }
      }
    }
    out.set(name, `function${combined.slice(combined.lastIndexOf('function', parenIndex) + 8, j + 1)}`);
  }
  return out;
}

// --- 3. цепочка замен обработчика «Сохранить» ---
const REPLACEMENTS = [
  [/\u00A0/g, ' '], ['&nbsp;', ' '], [';;', ';'], ['; "', '"'], ['background-color:;', ''],
  ['style=""', ''], ['alt=""', ''], ['data=""', ''], ['="undefined"', ''], [' class=""', ''],
  ['> <', '><'], ['data-bind_grid="1"', ''], ['data-bind_grid="0"', ''],
  ['data-bind_wrapper="1"', ''], ['data-bind_wrapper="0"', ''],
  ['data-bind_obj="1"', ''], ['data-bind_obj="0"', ''],
];

// --- 4. заглушки DOM/jQuery: нужны только чтобы код вендора инициализировался ---
function makeStubNode() {
  const node = {};
  const chain = () => node;
  Object.assign(node, {
    length: 0,
    ready(callback) { if (typeof callback === 'function') callback(); return node; },
    on: chain,
    off: chain,
    one: chain,
    trigger: chain,
    find: chain,
    parent: chain,
    parents: chain,
    closest: chain,
    children: chain,
    siblings: chain,
    filter: chain,
    eq: chain,
    first: chain,
    last: chain,
    add: chain,
    addClass: chain,
    removeClass: chain,
    toggleClass: chain,
    removeAttr: chain,
    append: chain,
    prepend: chain,
    after: chain,
    before: chain,
    remove: chain,
    replaceWith: chain,
    show: chain,
    hide: chain,
    toggle: chain,
    each: chain,
    map() { return { get: () => [] }; },
    html(value) { return value === undefined ? '' : node; },
    text(value) { return value === undefined ? '' : node; },
    val(value) { return value === undefined ? '' : node; },
    data() { return undefined; },
    css(value) { return value === undefined ? '' : node; },
    attr(value) { return value === undefined ? '' : node; },
    prop(name) { return name === 'outerHTML' ? '' : undefined; },
    is() { return false; },
    hasClass() { return false; },
    width() { return 0; },
    height() { return 0; },
    outerWidth() { return 0; },
    outerHeight() { return 0; },
    offset() { return { top: 0, left: 0 }; },
    position() { return { top: 0, left: 0 }; },
  });
  return node;
}

const stubNode = makeStubNode();
const $stub = () => stubNode;
$stub.ajax = (options) => {
  if (options && typeof options.success === 'function') options.success({});
  return stubNode;
};
$stub.each = (collection, callback) => {
  if (Array.isArray(collection)) collection.forEach((value, index) => callback(index, value));
  else if (collection && typeof collection === 'object') {
    Object.keys(collection).forEach((key) => callback(key, collection[key]));
  }
  return stubNode;
};
$stub.parseHTML = (html) => [new JSDOM(`<body>${html}</body>`).window.document.body.firstElementChild];

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function deepSet(target, pathValue, value) {
  const parts = Array.isArray(pathValue) ? pathValue : String(pathValue || '').split('.');
  let cursor = target;
  for (let i = 0; i < parts.length - 1; i++) {
    const key = parts[i];
    if (!cursor[key] || typeof cursor[key] !== 'object') cursor[key] = {};
    cursor = cursor[key];
  }
  if (parts.length) cursor[parts[parts.length - 1]] = value;
  return target;
}

function parseVKVideoLink(url) {
  const value = String(url || '').trim();
  const match = value.match(/(?:video|clip)(-?\d+)[_\/](\d+)/i)
    || value.match(/[?&]oid=(-?\d+).*?[?&]id=(\d+)/i);
  if (!match) return {};
  return { owner_id: match[1], video_id: match[2] };
}

function parseYouTubeLink(url) {
  const value = String(url || '').trim();
  const match = value.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?.*?v=|shorts\/|embed\/))([A-Za-z0-9_-]{6,})/i);
  return match ? match[1] : '';
}

function parseRutubeLink(url) {
  const value = String(url || '').trim();
  const match = value.match(/rutube\.ru\/(?:video|play\/embed)\/([A-Za-z0-9_-]+)/i);
  return match ? match[1] : '';
}

function parsePLVideoLink(url) {
  const value = String(url || '').trim();
  const match = value.match(/plvideo\.ru\/(?:watch\?v=|video\/|embed\/)([A-Za-z0-9_-]+)/i);
  return match ? match[1] : '';
}

function renderVideoFrame(url) {
  const value = String(url || '').trim();
  let src = '';
  let videoId = '';
  if (/(?:vk\.(?:com|ru)|vkvideo\.ru)/i.test(value)) {
    const parsed = parseVKVideoLink(value);
    if (parsed.owner_id !== undefined) {
      videoId = parsed.video_id;
      src = `https://vkvideo.ru/video_ext.php?oid=${parsed.owner_id}&id=${parsed.video_id}`;
    }
  } else if (/rutube\.ru/i.test(value)) {
    videoId = parseRutubeLink(value);
    if (videoId) src = `https://rutube.ru/play/embed/${videoId}`;
  } else if (/plvideo\.ru/i.test(value)) {
    videoId = parsePLVideoLink(value);
    if (videoId) src = `https://plvideo.ru/embed/${videoId}`;
  } else if (/(?:youtube\.com|youtu\.be)/i.test(value)) {
    videoId = parseYouTubeLink(value);
    if (videoId) src = `https://www.youtube.com/embed/${videoId}`;
  } else if (/vimeo\.com/i.test(value)) {
    const match = value.match(/vimeo\.com\/(?:video\/)?(\d+)/i);
    if (match) {
      videoId = match[1];
      src = `https://player.vimeo.com/video/${videoId}`;
    }
  }
  if (!src) return '';
  return `<iframe src="${escapeHtml(src)}" frameborder="0" allowfullscreen loading="lazy" data-video-id="${escapeHtml(videoId)}"></iframe>`;
}

function renderSocialIcons(values = {}) {
  if (!values.show_icons) return '';
  const networks = [
    ['sn-vk', 'show_vk', 'link_vk'],
    ['sn-max', 'show_max', 'link_max'],
    ['sn-whatsapp', 'show_gplus', 'link_whatsup'],
    ['sn-youtube', 'show_youtube', 'link_youtube'],
    ['sn-vimeo', 'show_vimeo', 'link_vimeo'],
    ['sn-zen', 'show_zen', 'link_zen'],
    ['sn-rutube', 'show_rutube', 'link_rutube'],
    ['sn-ok', 'show_o', 'link_o'],
    ['sn-viber', 'show_mail', 'link_viber'],
    ['sn-telegram', 'show_tg', 'link_tg'],
  ];
  const links = networks
    .filter(([, show]) => values[show])
    .map(([className, , href]) => `<a class="${className}" href="${escapeHtml(values[href] || '#')}" target="_blank" rel="noopener"></a>`)
    .join('');
  return `<div class="social_icons social_icons_ng ${escapeHtml(values.icons_figure || '')}">${links}</div>`;
}

function installTobizStubs(sandbox) {
  Object.assign(sandbox.window.tobiz, {
    wrapToBootstrapCard: (_title, body) => body || '',
    getSectionId: () => '',
    getSelectedAttr: (value, current) => String(value) === String(current) ? 'selected' : '',
    getCheckedAttr: (value, current) => String(value) === String(current) ? 'checked' : '',
    syncColorInputs: () => {},
    isValidValue: (v) => v !== null && v !== undefined && v !== '' && v !== 0,
    escapeHtml,
    deepSet,
    getElementInfo: () => ({ top: 0, left: 0, width: 0, height: 0 }),
    sanitizeHtml: (html) => html || '',
    parseYouTubeLinkNG: parseYouTubeLink,
    ParseVKVideoLink: parseVKVideoLink,
    getRutubeVideoId: parseRutubeLink,
    parsePLVideoLink: parsePLVideoLink,
  });
  sandbox.WindowManager = { open: () => {}, close: () => {} };
  sandbox.anime = () => ({ play: () => {}, pause: () => {} });
  sandbox.CodeMirror = { fromTextArea: () => ({ getValue: () => '', setValue: () => {}, on: () => {} }) };
}

function createRuntime(vendorDir, options = {}) {
  const quiet = options.quiet !== false;
  const read = (name) => fs.readFileSync(path.join(vendorDir, name), 'utf8');
  const sandbox = {
    console: quiet ? { log() {}, error() {}, warn() {}, info() {} } : console,
    window: { location: { hash: '', search: '', href: 'https://example.invalid/' }, tobiz: {} },
    document: {
      createElement: () => stubNode,
      getElementById: () => null,
      querySelector: () => null,
      querySelectorAll: () => [],
      addEventListener: () => {},
      cookie: '',
    },
    navigator: { userAgent: 'node' },
    URL,
    URLSearchParams,
    Blob,
    localStorage: { getItem: () => null, setItem: () => {} },
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
  };
  sandbox.window.document = sandbox.document;
  sandbox.tobiz = sandbox.window.tobiz;
  sandbox.$ = $stub;
  sandbox.jQuery = $stub;
  installTobizStubs(sandbox);
  sandbox.A = sandbox.window.tobiz;                       // A = window.tobiz в редакторе
  sandbox.I = (v) => v !== null && v !== undefined && v !== '' && v !== 0; // App.isValidValue
  sandbox.O = sandbox.window.tobiz;                       // O = window.tobiz в editor.min.js
  sandbox.R = sandbox.I;                                  // R = window.tobiz.isValidValue
  vm.createContext(sandbox);

  vm.runInContext(read('underscore-min.js'), sandbox, { filename: 'underscore-min.js' });
  const underscore = sandbox._;
  if (!underscore) throw new Error('underscore не загрузился');

  const editorSrc = read('editor.min.js');
  const blocksSrc = read('blocks2.js');
  const mixin = findMixinObject(editorSrc);
  vm.runInContext(`_;_.mixin(${mixin});`, sandbox, { filename: 'vendor-mixin.js' });
  // getVideoFrame uses a browser jQuery element. Return the same public iframe HTML directly.
  underscore.getVideoFrame = renderVideoFrame;
  // The vendor helper builds this fragment through jQuery; produce the public markup directly.
  underscore.renderSocialIcons = renderSocialIcons;

  const bundleSources = BUNDLES
    .map((name) => path.join(vendorDir, name))
    .filter((file) => fs.existsSync(file))
    .map((file) => fs.readFileSync(file, 'utf8'));
  const needed = new Set();
  for (const source of [blocksSrc, mixin, ...bundleSources]) {
    for (const match of source.matchAll(/\bA\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(/g)) needed.add(match[1]);
  }
  const appMethods = extractAppMethods(bundleSources, [...needed]);
  for (const [name, body] of appMethods) {
    try {
      vm.runInContext(`window.tobiz[${JSON.stringify(name)}] = ${body};`, sandbox);
    } catch (e) {
      if (!quiet) process.stderr.write(`[vendor] App.${name}: ${e.message}\n`);
    }
  }
  sandbox.A = sandbox.window.tobiz;
  sandbox.O = sandbox.window.tobiz;
  sandbox.R = sandbox.window.tobiz.isValidValue || sandbox.I;

  vm.runInContext(blocksSrc, sandbox, { filename: 'blocks2.js' });
  const flexToolsPath = path.join(vendorDir, 'flex_tools.min.js');
  if (fs.existsSync(flexToolsPath)) {
    try {
      vm.runInContext(fs.readFileSync(flexToolsPath, 'utf8'), sandbox, { filename: 'flex_tools.min.js' });
    } catch (e) {
      if (!quiet) process.stderr.write(`[vendor] FlexibleTools: ${e.message}\n`);
    }
  }
  const blocks = sandbox.tobiz.blocks || [];
  const byType = new Map(blocks.map((b) => [Number(b.type_id), b]));

  function renderFlexBlock(root, merged, blockId) {
    const tools = sandbox.FlexibleTools || sandbox.window.FlexibleTools;
    if (Number(root.getAttribute('data-id')) !== Number(blockId)) root.setAttribute('data-id', String(blockId));
    if (!tools || typeof tools.renderFlexblocks !== 'function') return '';

    const userBlock = { id: String(blockId), type_id: '1600', data: merged };
    sandbox.window.tobiz.userBlocks = [userBlock];
    sandbox.tobiz.userBlocks = sandbox.window.tobiz.userBlocks;

    const flexHtml = tools.renderFlexblocks(String(blockId), merged) || '';
    const inner = root.querySelector('.section_inner');
    if (inner && flexHtml) {
      inner.insertAdjacentHTML('afterbegin', flexHtml);
      inner.querySelectorAll('.flexblock_tools').forEach((node) => node.remove());
      inner.querySelectorAll('.flexblock_content').forEach((node) => {
        node.removeAttribute('data-editor');
        node.removeAttribute('data-editor-type');
      });
    }

    if (typeof tools.renderStyles !== 'function') return '';
    return tools.renderStyles(String(blockId), userBlock) || '';
  }

  function render(typeId, values, blockId) {
    const block = byType.get(Number(typeId));
    if (!block) {
      const error = new Error(`тип блока ${typeId} отсутствует в сборке проекта`);
      error.code = 'TEMPLATE_UNAVAILABLE';
      throw error;
    }
    const merged = Object.assign({
      arr1: [], form1: [], form2: [], form_html: '', form_html1: '',
      icons_figure: '', icons_color: '', menu_bg: '',
    }, block.values, values || {});
    const body = underscore.template(block.template)(merged);
    const dom = new JSDOM(`<body>${body}</body>`);
    const doc = dom.window.document;
    const root = doc.body.firstElementChild;
    if (!root) throw new Error(`шаблон ${typeId} вернул пустой HTML`);
    const anchorId = merged.anchor || `a_${blockId}`;
    const span = doc.createElement('span');
    span.setAttribute('id', anchorId);
    span.setAttribute('class', 'block_anchor');
    root.prepend(span);
    root.setAttribute('data-id', String(blockId));
    root.setAttribute('id', `b_${blockId}`);
    let extraHtml = '';
    if (Number(typeId) === 1600) {
      const css = renderFlexBlock(root, merged, blockId);
      if (css) extraHtml = `<style id="s_${blockId}">${css}</style>`;
    }
    let html = root.outerHTML + extraHtml;
    dom.window.close();
    for (const [from, to] of REPLACEMENTS) html = html.replaceAll(from, to);
    const videoEnabled = Object.prototype.hasOwnProperty.call(merged, 'mode')
      ? merged.mode !== 'image'
      : Object.prototype.hasOwnProperty.call(merged, 'use_video')
        ? merged.use_video === true || Number(merged.use_video) === 1
        : true;
    if (block.template.includes('getVideoFrame') && videoEnabled) {
      const videoUrls = Array.isArray(merged.arr1)
        ? merged.arr1.map((item) => item && item.video).filter(Boolean)
        : [];
      if (videoUrls.length && !html.includes('<iframe')) {
        const error = new Error(`видео-ссылки не преобразованы в iframe (${videoUrls.length})`);
        error.code = 'MEDIA_RENDER_EMPTY';
        throw error;
      }
    }
    return html;
  }

  return { underscore, blocks, byType, render, appMethods: [...appMethods.keys()] };
}

module.exports = {
  createRuntime, findMixinObject, extractAppMethods, REPLACEMENTS,
  parseVKVideoLink, parseYouTubeLink, parseRutubeLink, parsePLVideoLink, renderVideoFrame,
  renderSocialIcons,
};
