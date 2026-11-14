import React from "react";
import { random } from "remotion";
import { FPS, H, W } from "./rig";

export const COLORS = {
  navy: "#041726",
  cyan: "#5CE1FF",
  gold: "#FFC46B",
};

export { FPS, H, SRC_H, SRC_W, W } from "./rig";

/* ------------------------------------------------------------------ god rays */
export const GodRays: React.FC<{
  frame: number;
  sun: [number, number];
  count?: number;
  length?: number;
  opacity?: number;
  seed: string;
}> = ({ frame, sun, count = 16, length = 2200, opacity = 0.5, seed }) => {
  const t = frame / FPS;
  return (
    <>
      {new Array(count).fill(0).map((_, i) => {
        const base = (random(`${seed}-a${i}`) - 0.5) * 70;
        const sway = Math.sin(t * (0.25 + random(`${seed}-s${i}`) * 0.35) + i) * 2.2;
        const width = 30 + random(`${seed}-w${i}`) * 140;
        const flicker = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t * (0.6 + random(`${seed}-f${i}`)) + i * 1.7));
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: sun[0] - width / 2,
              top: sun[1],
              width,
              height: length * (0.7 + random(`${seed}-l${i}`) * 0.5),
              transformOrigin: "50% 0%",
              transform: `rotate(${base + sway}deg)`,
              background:
                "linear-gradient(to bottom, rgba(220,250,255,0.55), rgba(160,230,255,0.18) 45%, rgba(120,200,255,0))",
              maskImage: "linear-gradient(to right, transparent, black 40%, black 60%, transparent)",
              WebkitMaskImage: "linear-gradient(to right, transparent, black 40%, black 60%, transparent)",
              filter: "blur(10px)",
              mixBlendMode: "screen",
              opacity: opacity * flicker,
            }}
          />
        );
      })}
    </>
  );
};

/* ------------------------------------------------------------------ bubbles */
export const Bubbles: React.FC<{
  frame: number;
  mouth: [number, number];
  bursts: [number, number][]; // [startSecond, count]
  seed: string;
}> = ({ frame, mouth, bursts, seed }) => {
  const t = frame / FPS;
  const items: React.ReactNode[] = [];
  bursts.forEach(([t0, n], b) => {
    for (let j = 0; j < n; j++) {
      const k = `${seed}-${b}-${j}`;
      const start = t0 + j * (0.03 + random(`${k}d`) * 0.06);
      const age = t - start;
      if (age < 0 || age > 3.2) continue;
      const r = j % 5 ? 2.5 + random(`${k}r`) * 4 : 7 + random(`${k}R`) * 4;
      const vx = -30 + random(`${k}x`) * 75;
      const vy = -130 - random(`${k}y`) * 110;
      const x = mouth[0] + vx * age + (3 + random(`${k}w`) * 6) * Math.sin(age * 9 + j);
      const y = mouth[1] + vy * age - 40 * age * age;
      const rr = r * (1 + 0.25 * age);
      items.push(
        <div
          key={k}
          style={{
            position: "absolute",
            left: x - rr,
            top: y - rr,
            width: rr * 2,
            height: rr * 2,
            borderRadius: "50%",
            border: `${Math.max(1, rr * 0.18)}px solid rgba(225,248,255,0.55)`,
            background:
              "radial-gradient(circle at 32% 30%, rgba(255,255,255,0.95) 0 16%, rgba(255,255,255,0.08) 22%, rgba(180,235,255,0.04) 70%)",
            opacity: Math.min(1, (3.2 - age) * 2),
          }}
        />
      );
    }
  });
  return <>{items}</>;
};

/* ------------------------------------------------------------------ traffic */
export type Pt = [number, number];
export const polyline = (pts: Pt[]) => {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  }
  return { pts, cum };
};
const along = (pl: ReturnType<typeof polyline>, s: number) => {
  const d = s * pl.cum[pl.cum.length - 1];
  let i = 0;
  while (i < pl.pts.length - 2 && pl.cum[i + 1] < d) i++;
  const f = (d - pl.cum[i]) / Math.max(pl.cum[i + 1] - pl.cum[i], 1e-6);
  const [ax, ay] = pl.pts[i];
  const [bx, by] = pl.pts[i + 1];
  const len = Math.hypot(bx - ax, by - ay) || 1;
  return { p: [ax + (bx - ax) * f, ay + (by - ay) * f] as Pt, n: [-(by - ay) / len, (bx - ax) / len] as Pt };
};

export type Lane = {
  pl: ReturnType<typeof polyline>;
  n: number;
  lane: number; // offset across the road, as a fraction of its width
  speed: number; // fraction of the path per second; negative = towards the camera
  wNear: number; // road width at s=0
  wFar: number; // road width at s=1
  sz: [number, number]; // light radius [far, near]
  key: string;
  fadeIn?: number; // fade lights in over the first part of the path (e.g. from a vanishing point)
};

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

export const Traffic: React.FC<{ frame: number; lanes: Lane[] }> = ({ frame, lanes }) => {
  const t = frame / FPS;
  const lights: React.ReactNode[] = [];
  for (const L of lanes) {
    for (let i = 0; i < L.n; i++) {
      const k = `${L.key}${i}`;
      const v = L.speed * (0.8 + random(`${k}v`) * 0.4);
      const s = (((random(`${k}s`) + v * t) % 1) + 1) % 1;
      const { p, n } = along(L.pl, s);
      const lane = L.lane + (random(`${k}l`) - 0.5) * 0.1;
      const width = lerp(L.wNear, L.wFar, s);
      const x = p[0] + n[0] * width * lane;
      const y = p[1] + n[1] * width * lane;
      const rad = lerp(L.sz[1], L.sz[0], s) * 0.9;
      const fade = L.fadeIn ? Math.min(1, (1 - s) / L.fadeIn) : 1;
      const toward = v < 0;
      const core = toward ? "rgba(255,244,220,1)" : "rgba(255,70,55,1)";
      const glow = toward ? "rgba(255,236,200,0.75)" : "rgba(255,40,30,0.75)";
      lights.push(
        <div
          key={`${k}streak`}
          style={{
            position: "absolute",
            left: x - rad * 9,
            top: y - Math.max(0.35, rad * 0.18),
            width: rad * 18,
            height: Math.max(0.7, rad * 0.36),
            background: "linear-gradient(to right, rgba(110,200,255,0), rgba(150,215,255,0.55), rgba(110,200,255,0))",
            opacity: 0.55 * fade,
          }}
        />
      );
      for (const sgn of [-1, 1]) {
        lights.push(
          <div
            key={`${k}${sgn}`}
            style={{
              position: "absolute",
              left: x + n[0] * rad * 1.5 * sgn - rad,
              top: y + n[1] * rad * 0.45 * sgn - rad,
              width: rad * 2,
              height: rad * 2,
              borderRadius: "50%",
              background: core,
              boxShadow: `0 0 ${rad * 3}px ${rad * 1.2}px ${glow}`,
              opacity: fade,
            }}
          />
        );
      }
    }
  }
  return <>{lights}</>;
};

/* ------------------------------------------------------------------ particles (3D marine snow) */
export const Particles: React.FC<{
  frame: number;
  cam: [number, number, number];
  focus?: number;
  gain?: number;
  count?: number;
}> = ({ frame, cam, focus = 3, gain = 1, count = 320 }) => {
  const t = frame / FPS;
  const box = [18, 24, 13.4];
  const lo = [-9, -12, 0.6];
  const f = 1100;
  const out: React.ReactNode[] = [];
  for (let i = 0; i < count; i++) {
    const ph = random(`p${i}ph`) * 6.28;
    let x = lo[0] + random(`p${i}x`) * box[0] - cam[0] + 0.25 * Math.sin(t * 0.6 + ph);
    let y = lo[1] + random(`p${i}y`) * box[1] - cam[1] + 0.18 * Math.sin(t * 0.8 + ph * 1.7) - 0.05 * t;
    let z = lo[2] + random(`p${i}z`) * box[2] - cam[2];
    x = ((((x - lo[0]) % box[0]) + box[0]) % box[0]) + lo[0];
    y = ((((y - lo[1]) % box[1]) + box[1]) % box[1]) + lo[1];
    z = ((((z - lo[2]) % box[2]) + box[2]) % box[2]) + lo[2];
    const u = W / 2 + (f * x) / z;
    const v = H / 2 + (f * y) / z;
    if (u < -60 || u > W + 60 || v < -60 || v > H + 60) continue;
    const size = (0.6 + random(`p${i}s`)) * 7 / z;
    const defocus = Math.abs(1 / z - 1 / focus) * 9;
    const r = Math.max(0.7, size / 2 + defocus * 1.1);
    const a = (0.25 + random(`p${i}b`) * 0.75) * (defocus < 0.6 ? 0.85 : defocus < 2 ? 0.5 : 0.25) * gain;
    out.push(
      <div
        key={i}
        style={{
          position: "absolute",
          left: u - r,
          top: v - r,
          width: r * 2,
          height: r * 2,
          borderRadius: "50%",
          background: `radial-gradient(circle, rgba(225,245,255,${a}) 0%, rgba(225,245,255,${a * 0.5}) 45%, rgba(225,245,255,0) 72%)`,
        }}
      />
    );
  }
  return <>{out}</>;
};

/* ------------------------------------------------------------------ finishing overlays */
export const Grain: React.FC<{ frame: number }> = ({ frame }) => {
  const seed = Math.floor(frame);
  return (
    <svg width={W} height={H} style={{ position: "absolute", inset: 0, opacity: 0.11, mixBlendMode: "overlay" }}>
      <filter id={`grain${seed}`}>
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} seed={seed} stitchTiles="stitch" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter={`url(#grain${seed})`} />
    </svg>
  );
};

export const Vignette: React.FC = () => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      background: "radial-gradient(ellipse 75% 60% at 50% 50%, rgba(4,23,38,0) 55%, rgba(4,23,38,0.55) 100%)",
    }}
  />
);
