// Renders the preview SVGs written by tools/generate_watchface.py into PNGs.
//
// Usage (from the repo root, after running the generator):
//   node tools/render_previews.js
//
// Writes watchface/src/main/res/drawable-nodpi/preview.png (shown in the watch face picker)
// and docs/screenshots/*.png (used by the README).
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const previewDir = path.join(root, 'build', 'preview');
const shotsDir = path.join(root, 'docs', 'screenshots');
const pickerPreview = path.join(root, 'watchface', 'src', 'main', 'res', 'drawable-nodpi', 'preview.png');

(async () => {
  fs.mkdirSync(shotsDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 450, height: 450 }, deviceScaleFactor: 1 });
  const svgs = fs.readdirSync(previewDir).filter((f) => f.endsWith('.svg'));
  for (const svg of svgs) {
    // Inline the SVG in an HTML page next to it so relative icon paths resolve, and clip it
    // to a circle like the real screen.
    const html = path.join(previewDir, svg.replace('.svg', '.html'));
    fs.writeFileSync(html, '<!doctype html><html><body style="margin:0;background:#000">' +
      '<div style="width:450px;height:450px;clip-path:circle(50%)">' +
      fs.readFileSync(path.join(previewDir, svg), 'utf8') + '</div></body></html>');
    await page.goto('file://' + html);
    await page.waitForLoadState('load');
    const out = path.join(shotsDir, svg.replace('.svg', '.png'));
    await page.screenshot({ path: out, omitBackground: false });
    if (svg === 'preview.svg') fs.copyFileSync(out, pickerPreview);
    console.log('wrote', path.relative(root, out));
  }
  await browser.close();
})();
