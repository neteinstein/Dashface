// Renders the README video from build/video/frames.json (written by tools/video/make_frames.py).
//
// Usage (from the repo root):
//   python3 tools/generate_watchface.py && python3 tools/video/make_frames.py
//   node tools/video/render_video.js
//
// Writes docs/video/dashface.mp4 (1920x1080, 30 fps, with tools/video/soundtrack.m4a),
// docs/video/dashface.gif (720x405, 12 fps) and docs/video/dashface.jpg (cover frame).
// Needs Playwright with Chromium and ffmpeg with libx264.
const path = require('path');
const fs = require('fs');
const { spawn, execFileSync } = require('child_process');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..', '..');
const videoDir = path.join(root, 'build', 'video');
const outDir = path.join(root, 'docs', 'video');
const { fps, frames, captions } = JSON.parse(fs.readFileSync(path.join(videoDir, 'frames.json'), 'utf8'));
const COVER_FRAME = Math.round(3.0 * fps); // intro caption, everything filled in

const W = 1920, H = 1080, FACE = 450, FACE_D = 780, CX = 1340, CY = 540;

const page = `<!doctype html><html><head><meta charset="utf-8"><base href="../preview/"><style>
  html,body{margin:0;width:${W}px;height:${H}px;overflow:hidden;background:#07090c}
  #bg{position:absolute;inset:0;background:radial-gradient(900px 700px at ${CX}px ${CY}px,#18202b 0%,#0b0f14 55%,#07090c 100%)}
  #cap{position:absolute;left:150px;top:0;height:${H}px;width:640px;display:flex;flex-direction:column;justify-content:center;
       font-family:Inter,"DejaVu Sans",sans-serif;color:#fff}
  .kicker{font-size:17px;font-weight:600;letter-spacing:.32em;text-transform:uppercase;color:#8a94a3;margin-bottom:22px}
  .head{font-size:74px;font-weight:700;line-height:1.06;letter-spacing:-.02em}
  .brand{font-size:116px;letter-spacing:-.03em}
  .small{font-size:23px;line-height:1.45;color:#a3acb7;margin-top:26px;font-weight:400}
  .mono{font-family:"DejaVu Sans Mono",monospace;font-size:20px;color:#29B6F6}
  b{color:#29B6F6;font-weight:700} o{color:#FFA726} r{color:#EF5350} a{color:var(--accent)}
  #rig{position:absolute;left:0;top:0;width:${FACE}px;height:${FACE}px;transform-origin:0 0}
  #bezel{position:absolute;left:-13px;top:-13px;width:${FACE + 26}px;height:${FACE + 26}px;border-radius:50%;
         background:conic-gradient(from 210deg,#3a414b,#5d6670,#2a3038,#4b535d,#3a414b);
         box-shadow:0 30px 80px rgba(0,0,0,.6),0 0 0 1px #11151a}
  #face{position:absolute;left:0;top:0;width:${FACE}px;height:${FACE}px;clip-path:circle(50%);background:#000}
  #face text{font-family:"Google Sans","Product Sans",Roboto,Inter,"DejaVu Sans",sans-serif}
</style></head><body><div id="bg"></div>
<div id="rig"><div id="bezel"></div><div id="face"></div></div><div id="cap"></div></body></html>`;

(async () => {
  const html = path.join(videoDir, 'index.html');
  fs.writeFileSync(html, page);
  const faces = {};
  for (const f of new Set(frames.map((fr) => fr.face))) {
    faces[f] = fs.readFileSync(path.join(videoDir, `face_${f}.svg`), 'utf8');
  }

  const silent = path.join(videoDir, 'silent.mp4');
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'png',
    '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '18', '-pix_fmt', 'yuv420p', silent],
    { stdio: ['pipe', 'inherit', 'inherit'] });
  const ffDone = new Promise((res, rej) => ff.on('close', (c) => (c ? rej(new Error('ffmpeg ' + c)) : res())));

  const browser = await chromium.launch();
  const p = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  await p.goto('file://' + html);
  await p.evaluate(() => document.fonts.ready);

  let lastFace = null, lastCap = null;
  for (let i = 0; i < frames.length; i++) {
    const fr = frames[i];
    const s = (FACE_D / FACE) * fr.zoom;
    const tf = `translate(${CX}px,${CY}px) scale(${s}) translate(${-FACE / 2}px,${-(FACE / 2 + fr.focus)}px)`;
    const capHtml = fr.caption === lastCap ? null : (() => {
      const [k, head, small] = captions[fr.caption];
      return (k ? `<div class="kicker">${k}</div>` : '') + `<div class="head">${head}</div>` +
        (small ? `<div class="small">${small}</div>` : '');
    })();
    await p.evaluate(({ svg, tf, capHtml, op, slide, accent }) => {
      if (svg !== null) document.getElementById('face').innerHTML = svg;
      document.getElementById('rig').style.transform = tf;
      const cap = document.getElementById('cap');
      if (capHtml !== null) cap.innerHTML = capHtml;
      cap.style.opacity = op;
      cap.style.transform = `translateY(${slide}px)`;
      cap.style.setProperty('--accent', accent);
    }, { svg: fr.face === lastFace ? null : faces[fr.face], tf, capHtml, op: fr.op, slide: fr.slide, accent: fr.accent });
    if (fr.face !== lastFace) await p.waitForFunction(() => [...document.images].every((im) => im.complete));
    lastFace = fr.face; lastCap = fr.caption;
    const buf = await p.screenshot({ type: 'png' });
    if (i === COVER_FRAME) fs.writeFileSync(path.join(outDir, 'dashface.jpg.png'), buf);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await browser.close();
  await ffDone;

  const run = (args) => execFileSync('ffmpeg', ['-v', 'error', '-y', ...args], { stdio: 'inherit' });
  run(['-i', silent, '-i', path.join(__dirname, 'soundtrack.m4a'), '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
    '-c:a', 'copy', '-shortest', '-movflags', '+faststart', path.join(outDir, 'dashface.mp4')]);
  run(['-i', silent, '-vf', 'fps=12,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192[p];' +
    '[b][p]paletteuse=dither=bayer:bayer_scale=4', path.join(outDir, 'dashface.gif')]);
  run(['-i', path.join(outDir, 'dashface.jpg.png'), '-q:v', '3', path.join(outDir, 'dashface.jpg')]);
  fs.unlinkSync(path.join(outDir, 'dashface.jpg.png'));
  console.log('wrote docs/video/dashface.mp4, dashface.gif, dashface.jpg');
})();
