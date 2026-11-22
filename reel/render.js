// Renders reel.html frame by frame and encodes an MP4 with the soundtrack.
// node render.js <three-dir> <music.wav> <out.mp4> [frames-dir] [only: comma list of seconds for preview]
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs'), { execFileSync } = require('child_process');
const [threeDir, wav, out, framesDir = path.join(path.dirname(out), 'frames'), only] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ args:['--use-gl=swiftshader','--enable-webgl','--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport:{ width:1080, height:1920 }, deviceScaleFactor:1 });
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.route('**/cdn.jsdelivr.net/**', r => r.fulfill({ path: path.join(threeDir, r.request().url().split('three@0.147.0/')[1]), contentType:'application/javascript' }));
  await p.goto('file://' + path.join(__dirname, 'reel.html'));
  await p.waitForFunction(() => window.ready);
  await p.evaluate(() => window.ready);
  fs.mkdirSync(framesDir, { recursive:true });
  const FPS = 30, DUR = 50, total = FPS*DUR;
  const want = only ? new Set(only.split(',').map(s => Math.round(parseFloat(s)*FPS))) : null;
  const t0 = Date.now();
  for (let f = 0; f < total; f++){
    if (want && f > Math.max(...want)) break;
    await p.evaluate(t => window.renderAt(t), f/FPS);
    if (!want || want.has(f)) await p.screenshot({ path: path.join(framesDir, String(f).padStart(5,'0') + '.jpg'), type:'jpeg', quality:92 });
    if (f % 150 === 0) console.log('frame', f, ((Date.now()-t0)/1000).toFixed(0) + 's');
  }
  console.log(errs.length ? 'ERRORS:\n' + errs.join('\n') : 'no page errors');
  await b.close();
  if (!want){
    execFileSync('ffmpeg', ['-y','-loglevel','error','-framerate',String(FPS),'-i',path.join(framesDir,'%05d.jpg'),'-i',wav,
      '-c:v','libx264','-preset','slow','-crf','18','-pix_fmt','yuv420p','-r','30','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',out]);
    console.log('wrote', out);
  }
})();
