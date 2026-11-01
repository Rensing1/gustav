/** Offline diagram adapter. No caller-supplied URLs, files, config, or logs. */
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import puppeteer from 'puppeteer-core';
import { diagramConfig, diagramInputError } from './mermaid-policy.mjs';

const require = createRequire(import.meta.url);
const mermaidJs = await readFile(join(dirname(require.resolve('mermaid')), 'mermaid.js'), 'utf8');
const MAX_BYTES = 50 * 1024 * 1024;
let active = 0;

function send(response, status, value) {
  if (!response.destroyed) response.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }).end(JSON.stringify(value));
}

const server = http.createServer(async (request, response) => {
  if (request.method === 'GET' && request.url === '/health') return send(response, 200, { ok: true });
  if (request.method !== 'POST' || request.url !== '/render') return send(response, 404, { error: 'not_found' });
  if (active >= 2) return send(response, 503, { error: 'busy' });
  active++;
  let browser;
  let timer;
  let expired = false;
  let closing;
  const close = () => {
    if (!browser) return Promise.resolve();
    if (!closing) closing = (async () => {
      const child = browser.process();
      const kill = setTimeout(() => {
        try { if (child?.pid) process.kill(-child.pid, 'SIGKILL'); }
        catch { child?.kill('SIGKILL'); }
      }, 2000);
      try { await browser.close(); } catch { child?.kill('SIGKILL'); }
      finally { clearTimeout(kill); }
    })();
    return closing;
  };
  response.on('close', close);
  try {
    let size = 0;
    const chunks = [];
    for await (const chunk of request) {
      size += chunk.length;
      if (size > MAX_BYTES) { send(response, 413, { error: 'too_large' }); return; }
      chunks.push(chunk);
    }
    const payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (!Array.isArray(payload.diagrams) || !Number.isFinite(payload.budget_ms)) throw new Error('invalid_request');
    if (payload.diagrams.some((d) => typeof d?.source !== 'string' || !/^[a-f0-9]{64}$/.test(d?.id))) throw new Error('invalid_request');
    const budget = Math.min(30_000, Math.max(1, payload.budget_ms));
    timer = setTimeout(() => { expired = true; close(); }, budget);
    browser = await puppeteer.launch({
      executablePath: '/usr/local/bin/gustav-chromium', headless: true,
      // This dedicated, non-root container is the isolation boundary: no secrets,
      // mounted files, public ingress, or outbound network are available to Chrome.
      args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-background-networking'],
      timeout: budget
    });
    if (expired || response.destroyed) throw new Error('expired');
    const page = await browser.newPage();
    await page.setRequestInterception(true);
    page.on('request', (request) => void request.abort());
    await page.setViewport({ width: 1000, height: 800, deviceScaleFactor: 3 });
    await page.setContent('<!doctype html><html><body style="margin:0;background:white"><div id="output"></div></body></html>');
    await page.addScriptTag({ content: mermaidJs });
    const keys = await page.evaluate(() => Object.keys(window.mermaid.mermaidAPI.getConfig()));
    const config = diagramConfig(payload.theme === 'dark' ? 'dark' : 'light', keys);
    const outputLimit = Math.min(50 * 1024 * 1024, payload.max_output_bytes || 50 * 1024 * 1024);
    const results = [];
    let outputBytes = 0;
    for (const diagram of payload.diagrams) {
      const error = diagramInputError(diagram.source);
      if (error) { results.push({ id: diagram.id, error }); continue; }
      const result = await page.evaluate(async ({ source, config }) => {
        window.mermaid.initialize(config);
        const output = document.querySelector('#output');
        output.replaceChildren();
        output.style.width = '';
        output.style.height = '';
        document.body.style.background = config.darkMode ? '#1f2020' : 'white';
        let rendered;
        try {
          await window.mermaid.parse(source);
          // Valid syntax can still fail layout (for example a cyclic Sankey).
          // Browser/transport failures remain outside this per-definition boundary.
          rendered = await window.mermaid.render('print-diagram', source);
        } catch { return { error: 'invalid_diagram' }; }
        output.innerHTML = rendered.svg;
        const element = output.querySelector('svg');
        element.style.maxWidth = 'none';
        const naturalWidth = element.viewBox.baseVal.width;
        if (naturalWidth > 0) element.style.width = `${naturalWidth}px`;
        const box = element.getBoundingClientRect();
        if (box.width * box.height * 9 > 40_000_000 || box.width > 8000 || box.height > 8000) return { error: 'diagram_too_large' };
        output.style.width = `${Math.ceil(box.width)}px`;
        output.style.height = `${Math.ceil(box.height)}px`;
        return {};
      }, { source: diagram.source, config });
      if (result.error) { results.push({ id: diagram.id, error: result.error }); continue; }
      const element = await page.$('#output');
      const bytes = await element.screenshot({ type: 'png' });
      outputBytes += bytes.length;
      if (outputBytes > outputLimit) return send(response, 413, { error: 'output_too_large' });
      results.push({ id: diagram.id, png: Buffer.from(bytes).toString('base64') });
    }
    send(response, 200, { diagrams: results });
  } catch {
    send(response, 503, { error: expired ? 'render_timeout' : 'renderer_unavailable' });
  } finally {
    clearTimeout(timer);
    response.off('close', close);
    await close();
    active--;
  }
});
server.requestTimeout = 35_000;
server.headersTimeout = 5000;
server.listen(3001, '0.0.0.0');
