// Render the motion comic to an MP4 (with its synthesised soundtrack) using headless Chromium.
// Usage: node render-video.mjs OUT.mp4 [--fps 30] [--width 1080] [--workers 3]
// Env: IQ_ASSETS (default ../assets), FFMPEG (default ffmpeg), PLAYWRIGHT (module path, default 'playwright'),
//      THREE_LOCAL / FONTS_DIR to serve three.js and Google Fonts from disk when offline.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf('--' + k); return i >= 0 ? args[i + 1] : d; };
const OUT = path.resolve(args[0] || 'iq-the-best-motion-comic.mp4');
const FPS = +opt('fps', 30), WIDTH = +opt('width', 1080), HEIGHT = Math.round(WIDTH * 1.5), WORKERS = +opt('workers', 3), DURATION = 30;
const HTML = path.join(here, '..', 'iq-the-best-motion-comic.html');
const ASSETS = process.env.IQ_ASSETS || path.join(here, '..', 'assets');
const FFMPEG = process.env.FFMPEG || 'ffmpeg';
const { chromium } = await import(process.env.PLAYWRIGHT || 'playwright');

async function openPage() {
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1, ignoreHTTPSErrors: true });
  page.on('pageerror', e => console.error('page error:', e.message));
  if (process.env.THREE_LOCAL) await page.route('https://cdn.jsdelivr.net/npm/three@0.160.0/**', r => r.fulfill({ contentType: 'text/javascript', body: fs.readFileSync(process.env.THREE_LOCAL) }));
  if (process.env.FONTS_DIR) {
    await page.route('https://fonts.googleapis.com/**', r => r.fulfill({ contentType: 'text/css', body: fs.readFileSync(path.join(process.env.FONTS_DIR, 'fonts.css')) }));
    await page.route('https://fonts.gstatic.com/**', r => r.fulfill({ contentType: 'font/woff2', body: fs.readFileSync(path.join(process.env.FONTS_DIR, new URL(r.request().url()).pathname.slice(1).replaceAll('/', '_'))) }));
  }
  await page.route('http://iq.local/assets/**', r => { const f = path.join(ASSETS, path.basename(new URL(r.request().url()).pathname)); r.fulfill({ contentType: f.endsWith('.json') ? 'application/json' : f.endsWith('.jpg') ? 'image/jpeg' : 'image/webp', body: fs.readFileSync(f) }); });
  await page.route('http://iq.local/', r => r.fulfill({ contentType: 'text/html', body: '<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + fs.readFileSync(HTML, 'utf8') + '</body></html>' }));
  await page.addInitScript(() => { window.__IQ_CAPTURE__ = true; });
  await page.goto('http://iq.local/');
  await page.waitForFunction(() => window.__iq && window.__iq.ready, null, { timeout: 120000 });
  await page.evaluate(() => window.__iq.ready);
  return { browser, page };
}

const total = Math.round(DURATION * FPS);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'iq-frames-'));
const chunks = Array.from({ length: WORKERS }, (_, w) => [Math.floor(w * total / WORKERS), Math.floor((w + 1) * total / WORKERS)]);
let done = 0;
await Promise.all(chunks.map(async ([a, b]) => {
  const { browser, page } = await openPage();
  for (let f = a; f < b; f++) {
    await page.evaluate(t => window.__iq.renderAt(t), f / FPS);
    await page.screenshot({ path: path.join(tmp, `f${String(f).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 93 });
    if (++done % 60 === 0) console.log(`frames ${done}/${total}`);
  }
  await browser.close();
}));
{
  const { browser, page } = await openPage();
  const b64 = await page.evaluate(() => window.__iq.audioWav());
  fs.writeFileSync(path.join(tmp, 'audio.wav'), Buffer.from(b64, 'base64'));
  await browser.close();
}
await new Promise((res, rej) => {
  const p = spawn(FFMPEG, ['-y', '-framerate', String(FPS), '-i', path.join(tmp, 'f%05d.jpg'), '-i', path.join(tmp, 'audio.wav'), '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', OUT], { stdio: ['ignore', 'ignore', 'inherit'] });
  p.on('exit', c => c === 0 ? res() : rej(new Error('ffmpeg exited ' + c)));
});
fs.rmSync(tmp, { recursive: true, force: true });
console.log('wrote', OUT);
