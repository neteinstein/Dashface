// Renders every Google Play graphic in store-listing/ from the watch face's own preview SVGs.
//
// Usage (from the repo root):
//   python3 tools/generate_watchface.py        # writes build/preview/*.svg
//   node store-listing/tools/render_store_assets.js
//
// Needs Playwright with Chromium (the same setup as tools/render_previews.js).
//
// Writes, for both apps (watchface = "Dashface", dataprovider = "Dashface data"):
//   <app>/en-US/images/icon.png                    512 x 512, 32-bit PNG
//   <app>/en-US/images/featureGraphic.png          1024 x 500, 24-bit PNG (no alpha)
//   <app>/en-US/images/wearScreenshots/*.png       900 x 900, 1:1, no frame, no extra text
//   watchface/en-US/images/phoneScreenshots/*.png  1080 x 1920 (only if Play asks for them)
//
// The previews use sample data. Before release, compare them with the face on a real watch or
// emulator (see SUBMISSION_GUIDE.md, "Screenshots").
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..', '..');
const previewDir = path.join(root, 'build', 'preview');
const outRoot = path.join(root, 'store-listing');
const FACE = 450; // size of the preview SVGs

if (!fs.existsSync(path.join(previewDir, 'preview.svg'))) {
  console.error('build/preview/preview.svg is missing. Run: python3 tools/generate_watchface.py');
  process.exit(1);
}

// Closer to the watch's system font than the browser default sans.
const FONT_CSS = 'svg text{font-family:"Inter","Roboto","DejaVu Sans",sans-serif}';
const svg = (name) => fs.readFileSync(path.join(previewDir, name + '.svg'), 'utf8');

/** A watch face preview scaled to `size` px, clipped to the round screen. */
function face(name, size) {
  return `<div style="width:${FACE}px;height:${FACE}px;clip-path:circle(50%);` +
    `transform:scale(${size / FACE});transform-origin:0 0">${svg(name)}</div>`;
}

function page(body, w, h, bg = '#000') {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${FONT_CSS}
    html,body{margin:0;width:${w}px;height:${h}px;overflow:hidden;background:${bg};
      font-family:"Inter","Roboto",sans-serif;color:#fff}
    .abs{position:absolute}
  </style></head><body>${body}</body></html>`;
}

// The companion's launcher icon (dataprovider/src/main/res/drawable/ic_dashface.xml) on a full
// square, as Play's icon spec asks for apps; Play applies its own rounded mask.
function companionIcon(size) {
  const arc = (d, c) => `<path d="${d}" stroke="${c}" stroke-width="4" stroke-linecap="round" fill="none"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 48 48">
    <rect width="48" height="48" fill="#000"/>
    <g transform="translate(24 24) scale(1.04) translate(-24 -24)">
      ${arc('M22,6A18,18 0,0 0,6 22', '#29B6F6')}
      ${arc('M26,6A18,18 0,0 1,42 22', '#43A047')}
      ${arc('M6,26A18,18 0,0 0,22 42', '#FDD835')}
      ${arc('M42,26A18,18 0,0 1,26 42', '#FF1744')}
    </g></svg>`.replace(/\n\s*/g, ' ');
}

function featureGraphic({ title, tagline, sub, faceName }) {
  const d = 440;
  return page(`
    <div class="abs" style="left:64px;top:0;height:500px;width:500px;display:flex;flex-direction:column;justify-content:center">
      <div style="font-size:76px;font-weight:700;letter-spacing:-1.5px">${title}</div>
      <div style="font-size:30px;font-weight:500;margin-top:14px;line-height:1.25;color:#e6e6e6">${tagline}</div>
      <div style="font-size:22px;margin-top:22px;color:#29B6F6;font-weight:600">${sub}</div>
    </div>
    <div class="abs" style="left:${1024 - d - 54}px;top:${(500 - d) / 2}px;width:${d}px;height:${d}px">${face(faceName, d)}</div>
  `, 1024, 500, 'radial-gradient(circle at 76% 50%, #16222b 0%, #000 62%)');
}

function phoneShot({ caption, detail, faceName }) {
  const d = 920;
  return page(`
    <div class="abs" style="left:0;right:0;top:170px;text-align:center;padding:0 80px">
      <div style="font-size:72px;font-weight:700;letter-spacing:-1px;line-height:1.1">${caption}</div>
      <div style="font-size:38px;margin-top:28px;color:#cfcfcf;line-height:1.3">${detail}</div>
    </div>
    <div class="abs" style="left:${(1080 - d) / 2}px;top:600px;width:${d}px;height:${d}px">${face(faceName, d)}</div>
  `, 1080, 1920, 'linear-gradient(180deg,#0d1820 0%,#000 55%)');
}

const WEAR_SHOTS = {
  watchface: [
    ['1_multicolor', 'preview'],
    ['2_single_amber', 'preview_single_amber'],
    ['3_health_on_top', 'preview_health_top'],
    ['4_mirrored', 'preview_mirrored'],
    ['5_no_more_meetings', 'preview_no_meetings'],
    ['6_single_cyan', 'preview_single_cyan'],
    ['7_ambient', 'preview_ambient'],
  ],
  // The companion's whole UI is the data it puts on the face: meetings, stress, thermometer.
  dataprovider: [
    ['1_meetings_stress_skin', 'preview'],
    ['2_no_more_meetings', 'preview_no_meetings'],
    ['3_single_cyan', 'preview_single_cyan'],
  ],
};

const PHONE_SHOTS = [
  ['1_day_at_a_glance', 'Your day at a glance', 'Weather, time and your next meetings on Wear OS', 'preview'],
  ['2_make_it_yours', 'Make it yours', 'Multicolor or one of five accents', 'preview_single_amber'],
  ['3_any_corner', 'Any metric, any corner', 'Battery, steps, stress and heart rate', 'preview_health_top'],
  ['4_ambient', 'Easy on the battery', 'A minimal always-on mode', 'preview_ambient'],
];

(async () => {
  const browser = await chromium.launch();
  let n = 0;
  // Each page lives next to the SVGs so their relative icon paths resolve.
  async function render(html, w, h, out, { transparent = false } = {}) {
    const file = path.join(previewDir, `_store_${n++}.html`);
    fs.writeFileSync(file, html);
    const p = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    await p.goto('file://' + file);
    await p.waitForLoadState('load');
    await p.evaluate(() => document.fonts.ready);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await p.screenshot({ path: out, omitBackground: transparent, type: 'png' });
    await p.close();
    fs.unlinkSync(file);
    console.log('wrote', path.relative(root, out));
  }
  const img = (app, ...p) => path.join(outRoot, app, 'en-US', 'images', ...p);

  // ---- Watch face (WO-G4: a centered, circular watch face touching the icon's edges) ----
  await render(page(face('preview', 512), 512, 512, 'transparent'), 512, 512,
    img('watchface', 'icon.png'), { transparent: true });
  await render(featureGraphic({
    title: 'Dashface',
    tagline: 'Your day at a glance,<br>on your wrist.',
    sub: 'Watch face for Wear OS',
    faceName: 'preview',
  }), 1024, 500, img('watchface', 'featureGraphic.png'));
  for (const [file, name] of WEAR_SHOTS.watchface) {
    await render(page(face(name, 900), 900, 900), 900, 900, img('watchface', 'wearScreenshots', file + '.png'));
  }
  for (const [file, caption, detail, name] of PHONE_SHOTS) {
    await render(phoneShot({ caption, detail, faceName: name }), 1080, 1920,
      img('watchface', 'phoneScreenshots', file + '.png'));
  }

  // ---- Companion: Dashface data ----
  await render(page(companionIcon(512), 512, 512), 512, 512, img('dataprovider', 'icon.png'));
  await render(featureGraphic({
    title: 'Dashface data',
    tagline: 'Meetings, stress and<br>skin temperature.',
    sub: 'Complications for the Dashface watch face',
    faceName: 'preview',
  }), 1024, 500, img('dataprovider', 'featureGraphic.png'));
  for (const [file, name] of WEAR_SHOTS.dataprovider) {
    await render(page(face(name, 900), 900, 900), 900, 900, img('dataprovider', 'wearScreenshots', file + '.png'));
  }

  await browser.close();
})();
