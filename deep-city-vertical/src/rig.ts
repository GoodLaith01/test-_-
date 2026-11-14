/**
 * Cinematic camera rig.
 *
 * Each shot is a smooth cubic (Catmull-Rom style Hermite) path through a few
 * keys of (centre x, centre y, zoom) in source units, played back with a soft
 * time-warp so the camera eases in/out but never stops mid-shot. On top sits a
 * low-frequency "operator float" (drift, roll and breathing zoom) like a
 * camera held by a diver. Keys are chosen so the frame never leaves the image;
 * scripts/check-camera.ts verifies that for every frame, including the float.
 */

export const FPS = 24;
export const DURATION = 15 * FPS; // 360 frames
export const W = 1080;
export const H = 1920;
export const SRC_W = 864; // Figma keyframes, served as 2x upscales
export const SRC_H = 1536;

export type Key = { u: number; x: number; y: number; z: number };
export type Shot = { start: number; end: number; keys: Key[]; seed: number };
export type Cam = { cx: number; cy: number; z: number; rot: number; dx: number; dy: number };

export const SHOTS = {
  // 0.0-4.7 s: push in on the diver, then tilt down to the city as he rushes the lens
  dive: {
    start: 0,
    end: 112,
    seed: 1,
    keys: [
      { u: 0, x: 432, y: 775, z: 1.35 },
      { u: 0.55, x: 432, y: 712, z: 1.47 },
      { u: 1, x: 432, y: 915, z: 1.64 },
    ],
  },
  // 4.0-9.6 s: over-the-shoulder; crane up and pull back from his head to the towers
  city: {
    start: 96,
    end: 230,
    seed: 2,
    keys: [
      { u: 0, x: 352, y: 900, z: 1.64 },
      { u: 0.5, x: 400, y: 800, z: 1.55 },
      { u: 1, x: 448, y: 700, z: 1.46 },
    ],
  },
  // 9.0-15 s: street level: follow the people walking, then tilt up the avenue to the towers and swimmers
  street: {
    start: 216,
    end: DURATION,
    seed: 3,
    keys: [
      { u: 0, x: 430, y: 1040, z: 2.0 },
      { u: 0.4, x: 450, y: 1000, z: 1.92 },
      { u: 1, x: 468, y: 640, z: 1.74 },
    ],
  },
} satisfies Record<string, Shot>;

export const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
export const smooth = (x: number) => {
  const t = clamp01(x);
  return t * t * (3 - 2 * t);
};

/** Shot progress 0..1 with a soft ease: 55 % linear + 45 % sine, so ends never fully stop. */
export const progress = (f: number, s: Shot) => {
  const p = clamp01((f - s.start) / (s.end - s.start));
  return 0.55 * p + 0.45 * (0.5 - 0.5 * Math.cos(Math.PI * p));
};

const hermite = (p0: number, p1: number, m0: number, m1: number, t: number, dt: number) => {
  const t2 = t * t;
  const t3 = t2 * t;
  return (
    (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 * dt + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1 * dt
  );
};

/** Smooth path through the keys (C1 continuous). */
export const samplePath = (keys: Key[], u: number) => {
  const n = keys.length;
  const uu = Math.min(Math.max(u, keys[0].u), keys[n - 1].u);
  let i = 0;
  while (i < n - 2 && keys[i + 1].u < uu) i++;
  const a = keys[i];
  const b = keys[i + 1];
  const tangent = (j: number, c: "x" | "y" | "z") => {
    const lo = keys[Math.max(0, j - 1)];
    const hi = keys[Math.min(n - 1, j + 1)];
    return (hi[c] - lo[c]) / (hi.u - lo.u);
  };
  const dt = b.u - a.u;
  const t = (uu - a.u) / dt;
  const out = { x: 0, y: 0, z: 0 };
  (["x", "y", "z"] as const).forEach((c) => {
    out[c] = hermite(a[c], b[c], tangent(i, c), tangent(i + 1, c), t, dt);
  });
  return out;
};

/** Low-frequency operator float: screen-space drift (px), roll (deg) and zoom breathing. */
export const float = (t: number, seed: number) => {
  const n = (a: number, b: number, c: number, ph: number) =>
    Math.sin(t * a + ph) * 0.5 + Math.sin(t * b + ph * 1.7) * 0.3 + Math.sin(t * c + ph * 2.3) * 0.2;
  return {
    dx: 5 * n(0.31, 0.73, 1.13, seed * 1.3),
    dy: 6 * n(0.27, 0.61, 1.37, seed * 2.1 + 1),
    rot: 0.32 * n(0.21, 0.53, 0.97, seed * 0.7 + 2),
    dz: 0.004 * n(0.17, 0.43, 0.81, seed * 1.9 + 3),
  };
};

export const shotCamera = (f: number, s: Shot): Cam => {
  const p = samplePath(s.keys, progress(f, s));
  const fl = float(f / FPS, s.seed);
  return { cx: p.x, cy: p.y, z: p.z * (1 + fl.dz), rot: fl.rot, dx: fl.dx, dy: fl.dy };
};

/** CSS transform for a stage (transform-origin 0 0) placed in source units. */
export const stageTransform = (c: Cam) =>
  `translate(${W / 2 + c.dx}px, ${H / 2 + c.dy}px) rotate(${c.rot}deg) scale(${c.z}) translate(${-c.cx}px, ${-c.cy}px)`;

/** Map a screen point back to source units (used by the bounds check). */
export const screenToSource = (c: Cam, sx: number, sy: number) => {
  const x = sx - W / 2 - c.dx;
  const y = sy - H / 2 - c.dy;
  const r = (-c.rot * Math.PI) / 180;
  const rx = x * Math.cos(r) - y * Math.sin(r);
  const ry = x * Math.sin(r) + y * Math.cos(r);
  return { x: c.cx + rx / c.z, y: c.cy + ry / c.z };
};
