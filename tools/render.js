// Render video/index.html frame-by-frame with Playwright and encode with ffmpeg.
//   node tools/render.js                       -> out/seismic-ecosystem.mp4 (60 fps)
//   node tools/render.js --stills 1,4,9.5      -> out/stills/t-<sec>.png
//   node tools/render.js --fps 30 --workers 6
const http = require('http');
const fs = require('fs');
const path = require('path');
const {spawn} = require('child_process');
const {chromium} = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) =>
  v.startsWith('--') ? [...a, [v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]] : a, []));
const FPS = Number(args.fps || 60);
const WORKERS = Number(args.workers || 6);
const OUT = path.resolve(ROOT, args.out || 'out/seismic-ecosystem.mp4');
const TYPES = {'.html': 'text/html', '.svg': 'image/svg+xml', '.js': 'text/javascript', '.json': 'application/json'};

function serve() {
  return new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
      if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { rsp.writeHead(404); return rsp.end(); }
      rsp.writeHead(200, {'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream'});
      fs.createReadStream(p).pipe(rsp);
    }).listen(0, () => res(srv));
  });
}

async function openPage(browser, url) {
  const page = await browser.newPage({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1});
  page.on('pageerror', e => console.error('pageerror', e));
  await page.goto(url);
  const dur = await page.evaluate(() => window.ready);
  return {page, dur};
}

async function main() {
  const srv = await serve();
  const url = `http://127.0.0.1:${srv.address().port}/video/index.html`;
  const browser = await chromium.launch();

  if (args.stills) {
    const dir = path.join(ROOT, 'out/stills'); fs.mkdirSync(dir, {recursive: true});
    const {page} = await openPage(browser, url);
    for (const t of String(args.stills).split(',').map(Number)) {
      await page.evaluate(t => window.seek(t), t);
      await page.screenshot({path: path.join(dir, `t-${t.toFixed(2)}.png`)});
    }
    await browser.close(); srv.close(); return;
  }

  const {page: probe, dur} = await openPage(browser, url); await probe.close();
  const total = Math.ceil(dur * FPS);
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'seis-'));
  console.log(`${total} frames @ ${FPS}fps (${dur.toFixed(2)}s), ${WORKERS} workers`);
  const per = Math.ceil(total / WORKERS);
  let done = 0; const t0 = Date.now();

  await Promise.all([...Array(WORKERS)].map(async (_, w) => {
    const from = w * per, to = Math.min(total, from + per);
    if (from >= to) return null;
    const {page} = await openPage(browser, url);
    const part = path.join(tmp, `part-${w}.mp4`);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
      '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', '-profile:v', 'high', part],
      {stdio: ['pipe', 'inherit', 'inherit']});
    const closed = new Promise(r => ff.on('close', r));
    for (let f = from; f < to; f++) {
      await page.evaluate(t => window.seek(t), f / FPS);
      const buf = await page.screenshot({type: 'png'});
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (++done % 120 === 0) console.log(`${done}/${total}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
    }
    ff.stdin.end(); await closed; await page.close();
    return part;
  }));

  const list = path.join(tmp, 'list.txt');
  fs.writeFileSync(list, [...Array(WORKERS)].map((_, w) => path.join(tmp, `part-${w}.mp4`)).filter(fs.existsSync).map(p => `file '${p}'`).join('\n'));
  fs.mkdirSync(path.dirname(OUT), {recursive: true});
  await new Promise((res, rej) => spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list,
    '-c', 'copy', '-movflags', '+faststart', OUT], {stdio: 'inherit'}).on('close', c => c ? rej(c) : res()));
  fs.rmSync(tmp, {recursive: true, force: true});
  await browser.close(); srv.close();
  console.log('wrote', OUT);
}
main().catch(e => { console.error(e); process.exit(1); });
