// Мост Python -> Node: читает один JSON-запрос из stdin, пишет один JSON-ответ в stdout.
//
// Запросы:
//   {"op":"meta","vendor_dir":"..."}                       -> {"ok":true,"types":[...]}
//   {"op":"render","vendor_dir":"...","items":[{...}]}     -> {"ok":true,"html":{block_id:html}}
//   {"op":"check","vendor_dir":"..."}                       -> {"ok":true,"checked":N,"failed":[...]}
//   {"op":"audit","vendor_dir":"..."}                       -> render matrix report
//
// Диагностика — только в stderr, чтобы stdout оставался валидным JSON.
const fs = require('fs');
const path = require('path');
const { createRuntime } = require('./vendor-runtime');

function readStdin() {
  return new Promise((resolve, reject) => {
    const chunks = [];
    process.stdin.on('data', (c) => chunks.push(c));
    process.stdin.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    process.stdin.on('error', reject);
  });
}

function reply(payload) {
  process.stdout.write(JSON.stringify(payload));
}

(async () => {
  let request;
  try {
    request = JSON.parse(await readStdin());
  } catch (e) {
    reply({ ok: false, error: `не разобран запрос: ${e.message}` });
    process.exitCode = 1;
    return;
  }
  const vendorDir = request.vendor_dir;
  if (!vendorDir || !fs.existsSync(vendorDir)) {
    reply({ ok: false, error: `каталог сборки не найден: ${vendorDir}` });
    process.exitCode = 1;
    return;
  }
  let runtime;
  try {
    runtime = createRuntime(vendorDir, { quiet: true });
  } catch (e) {
    reply({ ok: false, error: `не удалось поднять рантайм вендора: ${e.message}` });
    process.exitCode = 1;
    return;
  }

  try {
    if (request.op === 'meta') {
      const types = runtime.blocks.map((b) => ({
        type_id: String(b.type_id),
        values: b.values || {},
        settings: b.settings || [],
        vars: b.vars || [],
        has_template: typeof b.template === 'string' && b.template.length > 0,
        template_bytes: (b.template || '').length,
      }));
      reply({ ok: true, types, count: types.length });
      return;
    }

    if (request.op === 'render' || request.op === 'check') {
      const html = {};
      const failed = [];
      for (const item of request.items || []) {
        try {
          html[String(item.block_id)] = runtime.render(item.type_id, item.values, item.block_id);
        } catch (e) {
          failed.push({
            block_id: String(item.block_id),
            type_id: String(item.type_id),
            error: String(e.message || e),
            code: e.code || 'RENDER_FAILED',
          });
        }
      }
      if (request.op === 'check') {
        reply({ ok: failed.length === 0, checked: (request.items || []).length, failed });
        return;
      }
      reply({
        ok: failed.length === 0,
        html,
        failed,
        rendered: Object.keys(html).length,
      });
      if (failed.length) process.exitCode = 0; // ошибки блоков передаются в JSON, а не кодом
      return;
    }

    if (request.op === 'audit') {
      const failures = [];
      const byType = {};
      let casesChecked = 0;
      const selectedTypes = new Set((request.type_ids || []).map(Number));
      for (const block of runtime.blocks) {
        const typeId = Number(block.type_id);
        if (selectedTypes.size && !selectedTypes.has(typeId)) continue;
        const samples = (request.samples_by_type || {})[String(typeId)] || [];
        const defaults = { ...(block.values || {}), ...(samples[0] || {}) };
        const cases = [{ name: 'vendor_default', values: block.values || {} }];
        if (typeId === 1600) {
          const emptyModes = { m: {}, s: {}, xs: {}, xxs: {} };
          const style = (l) => ({ l, ...emptyModes });
          cases.push({ name: 'all_flex_element_types', values: {
            ...defaults,
            flexblocks: [
              { type: 'text', content: '<p>Text</p>', style: style({ top: 10, left: 10, width: 200 }) },
              { type: 'html', html: '<div>HTML</div>', style: style({ top: 40, left: 10, width: 200 }) },
              { type: 'mdicon', icon: 'svg-icon-aper-plane', style: style({ top: 70, left: 10, width: 40, height: 40 }) },
              { type: 'figure', style: style({ top: 120, left: 10, width: 80, height: 80, backgroundColor: '#ffffff' }) },
              { type: 'hint', hintTitle: 'Hint', hintText: 'Text', style: style({ top: 210, left: 10, width: 25, height: 25 }) },
              { type: 'image', src: 'placeholder.png', link: '', style: style({ top: 10, left: 250, width: 200, height: 120 }) },
              { type: 'video', src: 'https://www.youtube.com/watch?v=PUl_8_jYUiM', style: style({ top: 140, left: 250, width: 200, height: 120 }) },
              { type: 'form', formBtnText: 'Send', nameTitle: 'Name', phoneTitle: 'Phone', nameUse: 1, phoneUse: 1, style: style({ top: 10, left: 500, width: 300 }) },
              { type: 'btn', title: 'Button', action: '2', formTitle: 'Form', formBtnText: 'Send', nameUse: 1, phoneUse: 1, style: style({ top: 250, left: 500, width: 200, height: 50 }) },
            ],
          } });
        }
        for (let sampleIndex = 0; sampleIndex < samples.length; sampleIndex++) {
          cases.push({ name: `server_sample_${sampleIndex + 1}`,
            values: { ...(block.values || {}), ...samples[sampleIndex] } });
        }
        for (const setting of block.settings || []) {
          if (!setting || !setting.name) continue;
          if (setting.type === 'checkbox') {
            for (const value of [0, 1]) {
              cases.push({ name: `${setting.name}=${value}`, values: { ...defaults, [setting.name]: value } });
            }
          }
          if (setting.type === 'select' && Array.isArray(setting.vars)) {
            for (const option of setting.vars) {
              if (!option || option.val === undefined) continue;
              cases.push({ name: `${setting.name}=${option.val}`, values: { ...defaults, [setting.name]: option.val } });
            }
          }
        }
        const report = { cases: cases.length, passed: 0, failed: 0 };
        for (let index = 0; index < cases.length; index++) {
          const item = cases[index];
          casesChecked++;
          try {
            runtime.render(typeId, item.values, `audit_${typeId}_${index}`);
            report.passed++;
          } catch (e) {
            report.failed++;
            failures.push({ type_id: String(typeId), case: item.name, error: String(e.message || e), code: e.code || 'RENDER_FAILED' });
          }
        }
        byType[String(typeId)] = report;
      }
      reply({ ok: failures.length === 0, types_checked: Object.keys(byType).length,
        cases_checked: casesChecked, passed: casesChecked - failures.length,
        failed: failures.length, failures, by_type: byType });
      return;
    }

    reply({ ok: false, error: `неизвестная операция: ${request.op}` });
    process.exitCode = 1;
  } catch (e) {
    reply({ ok: false, error: String(e.message || e) });
    process.exitCode = 1;
  }
})();
