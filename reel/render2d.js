// node render2d.js <music.wav> <out.mp4> <frames-dir> [preview seconds, comma separated]
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs'), { execFileSync } = require('child_process');
const [wav, out, framesDir, only] = process.argv.slice(2);
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport:{ width:1080, height:1920 } });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + path.join(__dirname, 'reel2d.html'));
  await p.waitForFunction(() => window.ready);
  fs.mkdirSync(framesDir, { recursive:true });
  const FPS = 30, total = 50*FPS;
  const want = only ? new Set(only.split(',').map(s => Math.round(parseFloat(s)*FPS))) : null;
  const last = want ? Math.max(...want) : total - 1;
  for (let f = 0; f <= last; f++){
    const data = await p.evaluate(([t, keep]) => { window.renderAt(t); return keep ? window.grab() : null; }, [f/FPS, !want || want.has(f)]);
    if (data) fs.writeFileSync(path.join(framesDir, String(f).padStart(5,'0') + '.jpg'), Buffer.from(data.split(',')[1], 'base64'));
  }
  console.log(errs.length ? 'ERRORS:\n' + errs.join('\n') : 'no page errors');
  await b.close();
  if (!want){
    execFileSync('ffmpeg', ['-y','-loglevel','error','-framerate',String(FPS),'-i',path.join(framesDir,'%05d.jpg'),'-i',wav,
      '-c:v','libx264','-preset','slow','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',out]);
    console.log('wrote', out);
  }
})();
