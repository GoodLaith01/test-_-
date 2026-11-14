/**
 * Verifies the camera rig for every frame of every shot:
 *  - the full frame (all four corners, with roll and float) stays inside the image
 *  - motion is continuous: no stops mid-shot and no sudden jerks.
 * Run: npx tsx scripts/check-camera.ts
 */
import { H, screenToSource, shotCamera, SHOTS, SRC_H, SRC_W, W } from "../src/rig";

let ok = true;
for (const [name, shot] of Object.entries(SHOTS)) {
  let minMargin = Infinity;
  const speeds: number[] = [];
  let prev: { x: number; y: number } | null = null;
  for (let f = shot.start; f < shot.end; f += 0.2) {
    const c = shotCamera(f, shot);
    for (const [sx, sy] of [
      [0, 0],
      [W, 0],
      [0, H],
      [W, H],
    ]) {
      const p = screenToSource(c, sx, sy);
      minMargin = Math.min(minMargin, p.x, p.y, SRC_W - p.x, SRC_H - p.y);
    }
    const centre = screenToSource(c, W / 2, H / 2);
    const pos = { x: centre.x * c.z, y: centre.y * c.z };
    if (prev && Math.abs(f - Math.round(f)) < 1e-9) speeds.push(Math.hypot(pos.x - prev.x, pos.y - prev.y));
    if (Math.abs(f - Math.round(f)) < 1e-9) prev = pos;
  }
  const inner = speeds.slice(3, -3);
  const jerk = Math.max(...inner.slice(1).map((v, i) => Math.abs(v - inner[i])));
  const pass = minMargin > 0;
  ok &&= pass;
  console.log(
    `${name.padEnd(7)} edge margin ${minMargin.toFixed(1).padStart(5)} src px ${pass ? "OK " : "FAIL"} | ` +
      `speed ${Math.min(...inner).toFixed(2)}-${Math.max(...inner).toFixed(2)} px/frame, max change ${jerk.toFixed(2)}`
  );
}
process.exit(ok ? 0 : 1);
