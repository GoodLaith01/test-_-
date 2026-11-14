import "@fontsource/montserrat/300.css";
import "@fontsource/montserrat/600.css";
import { CameraMotionBlur } from "@remotion/motion-blur";
import React from "react";
import { AbsoluteFill, Audio, Easing, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame } from "remotion";
import { Bubbles, COLORS, GodRays, Grain, Lane, Particles, polyline, Traffic, Vignette } from "./effects";
import { Cam, clamp01, DURATION, FPS, shotCamera, SHOTS, smooth, SRC_H, SRC_W, stageTransform, W } from "./rig";

export { DURATION, FPS };
export const TITLE_IN = Math.round(11.2 * FPS);

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ramp = (f: number, a: number, b: number) => clamp01((f - a) / (b - a));

/** A SRC_W x SRC_H stage seen through the camera; children are placed in source units. */
const Stage: React.FC<{ cam: Cam; children: React.ReactNode; filter?: string }> = ({ cam, children, filter }) => (
  <div
    style={{
      position: "absolute",
      width: SRC_W,
      height: SRC_H,
      transformOrigin: "0 0",
      transform: stageTransform(cam),
      filter,
    }}
  >
    {children}
  </div>
);

const isVideo = (src: string) => /\.(mp4|webm)$/.test(src);

/** Image or baked animation layer placed in source units. */
const Layer: React.FC<{ src: string; style: React.CSSProperties }> = ({ src, style }) =>
  isVideo(src) ? (
    <OffthreadVideo src={staticFile(src)} muted transparent={src.endsWith(".webm")} style={{ position: "absolute", ...style }} />
  ) : (
    <Img src={staticFile(src)} style={{ position: "absolute", ...style }} />
  );

/** Background layer with optional depth-of-field blur (in source px). */
const Plate: React.FC<{ src: string; blur?: number; children?: React.ReactNode }> = ({ src, blur = 0, children }) => (
  <div style={{ position: "absolute", inset: 0, filter: blur > 0.05 ? `blur(${blur}px)` : undefined }}>
    <Layer src={src} style={{ left: 0, top: 0, width: SRC_W, height: SRC_H }} />
    {children}
  </div>
);

/** Foreground swimmer: scales about an anchor (nearer than the background -> parallax). */
const Swimmer: React.FC<{
  src: string;
  box: [number, number, number, number];
  anchor: [number, number];
  scale: number;
  shift: [number, number];
  blur?: number;
  children?: React.ReactNode;
}> = ({ src, box, anchor, scale, shift, blur = 0, children }) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      transformOrigin: `${anchor[0]}px ${anchor[1]}px`,
      transform: `translate(${shift[0]}px, ${shift[1]}px) scale(${scale})`,
      filter: blur > 0.05 ? `blur(${blur}px)` : undefined,
    }}
  >
    <Layer src={src} style={{ left: box[0], top: box[1], width: box[2] - box[0], height: box[3] - box[1] }} />
    {children}
  </div>
);

/** Teal shadows / warm highlights, like a film grade. */
const Grade: React.FC = () => (
  <AbsoluteFill
    style={{
      background: "linear-gradient(to bottom, rgba(0,150,190,0.22), rgba(0,90,140,0.08) 45%, rgba(255,170,90,0.14))",
      mixBlendMode: "soft-light",
    }}
  />
);

/* ------------------------------------------------------------------ Shot 1: the dive */
const DiveScene: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / FPS;
  const shot = SHOTS.dive;
  const cam = shotCamera(f, shot);
  const s = clamp01(f / shot.end);
  // he swims toward the lens, then rushes into it (too close to focus -> defocus)
  const rush = Math.pow(ramp(s, 0.6, 1), 3);
  const manScale = 1 + 0.16 * s + 3.3 * rush;
  const shift: [number, number] = [3 * Math.sin(t * 1.3), 3 * Math.sin(t * 1.9 + 1) + 150 * rush];
  const sink = 2.0 * t + Math.max(0, t - 2.8) ** 2 * 1.5;
  const deep = smooth(ramp(s, 0.8, 1));
  return (
    <AbsoluteFill>
      <Stage cam={cam} filter="saturate(1.06) contrast(1.06)">
        <Plate src="dive_plate.jpg" blur={0.9} />
        <GodRays frame={f} sun={[600, -160]} seed="dive" opacity={0.5} length={1500} count={14} />
        <Swimmer
          src="dive_man_anim.webm"
          box={[107, 0, 741, 1062]}
          anchor={[430, 640]}
          scale={manScale}
          shift={shift}
          blur={rush * 7}
        >
          <Bubbles frame={f} mouth={[432, 578]} bursts={[[0.1, 14], [1.4, 12], [2.7, 15], [3.5, 12]]} seed="db" />
        </Swimmer>
      </Stage>
      <Particles frame={f} cam={[0, sink, 0]} focus={2.5} gain={0.9} />
      <AbsoluteFill style={{ background: COLORS.navy, opacity: deep * 0.92 }} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Shot 2: over-the-shoulder city reveal */
const CITY_LANES: Lane[] = (() => {
  const big = polyline([[330, 820], [450, 862], [560, 920], [650, 980], [740, 1040], [830, 1115], [870, 1152]]);
  const low = polyline([[355, 1110], [500, 1120], [620, 1150], [720, 1200], [800, 1250], [870, 1302]]);
  const far = polyline([[420, 690], [560, 700], [700, 728], [790, 762]]);
  return [
    { pl: big, n: 16, lane: -0.25, speed: 0.07, wNear: 40, wFar: 120, sz: [3.0, 1.2], key: "ba" },
    { pl: big, n: 16, lane: 0.25, speed: -0.065, wNear: 40, wFar: 120, sz: [3.0, 1.2], key: "bb" },
    { pl: low, n: 10, lane: -0.25, speed: 0.05, wNear: 40, wFar: 70, sz: [2.4, 1.2], key: "la" },
    { pl: low, n: 10, lane: 0.25, speed: -0.055, wNear: 40, wFar: 70, sz: [2.4, 1.2], key: "lb" },
    { pl: far, n: 8, lane: -0.4, speed: 0.04, wNear: 16, wFar: 20, sz: [1.0, 0.9], key: "fa" },
    { pl: far, n: 8, lane: 0.4, speed: -0.04, wNear: 16, wFar: 20, sz: [1.0, 0.9], key: "fb" },
  ];
})();

const CityScene: React.FC = () => {
  const shot = SHOTS.city;
  const f = useCurrentFrame() + shot.start; // absolute frame
  const t = f / FPS;
  const cam = shotCamera(f, shot);
  const s = ramp(f, shot.start, shot.end);
  // rack focus: from his head to the city
  const pull = smooth(ramp(s, 0.1, 0.45));
  const plateBlur = lerp(2.4, 0, pull);
  const manBlur = lerp(0, 2.8, pull);
  const manScale = 1 + 0.12 * s;
  const shift: [number, number] = [4 * Math.sin(t * 1.2), 30 * s + 3 * Math.sin(t * 1.7)];
  const appear = smooth(ramp(f, shot.start, shot.start + 18));
  const fog = 1 - smooth(ramp(f, shot.start, shot.start + 48));
  return (
    <AbsoluteFill style={{ opacity: appear }}>
      <Stage cam={cam} filter="saturate(1.06) contrast(1.06)">
        <Plate src="city_plate.jpg" blur={plateBlur}>
          <Traffic frame={f} lanes={CITY_LANES} />
        </Plate>
        <GodRays frame={f} sun={[430, -260]} seed="city" opacity={0.34} length={1500} count={16} />
        <Swimmer src="city_man_anim.webm" box={[0, 858, 399, 1536]} anchor={[190, 1000]} scale={manScale} shift={shift} blur={manBlur}>
          <Bubbles frame={f} mouth={[300, 985]} bursts={[[4.6, 8], [6.3, 9], [8.0, 8]]} seed="cb" />
        </Swimmer>
      </Stage>
      <Particles frame={f} cam={[0.3 * s, -3.5 * s, 1.5 * s + 0.15 * t]} focus={3.2} gain={0.7} />
      <AbsoluteFill style={{ background: COLORS.navy, opacity: fog * 0.85 }} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Shot 3: street level */
const STREET_LANES: Lane[] = (() => {
  const left = polyline([[490, 1185], [523, 1108]]);
  const right = polyline([[572, 1185], [540, 1108]]);
  return [
    { pl: left, n: 4, lane: 0, speed: -0.12, wNear: 0, wFar: 0, sz: [0.7, 1.6], key: "sl", fadeIn: 0.3 },
    { pl: right, n: 4, lane: 0, speed: 0.1, wNear: 0, wFar: 0, sz: [0.7, 1.6], key: "sr", fadeIn: 0.3 },
  ];
})();

const StreetScene: React.FC = () => {
  const shot = SHOTS.street;
  const f = useCurrentFrame() + shot.start;
  const t = f / FPS;
  const cam = shotCamera(f, shot);
  const s = ramp(f, shot.start, shot.end);
  const appear = smooth(ramp(f, shot.start, shot.start + 26));
  const focusIn = lerp(1.6, 0, smooth(ramp(s, 0, 0.3)));
  return (
    <AbsoluteFill style={{ opacity: appear }}>
      <Stage cam={cam} filter="saturate(1.06) contrast(1.06)">
        <Plate src="street_anim.mp4" blur={focusIn}>
          <Traffic frame={f} lanes={STREET_LANES} />
        </Plate>
        <GodRays frame={f} sun={[560, -220]} seed="street" opacity={0.32} length={1500} count={12} />
      </Stage>
      <Particles frame={f} cam={[0.2 * s, -2.2 * s, 2.5 * s + 0.15 * t]} focus={3.0} gain={0.6} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Title */
const Title: React.FC = () => {
  const t = useCurrentFrame() / FPS; // seconds since TITLE_IN
  const io = (a: number, b: number, from: number, to: number, ease = Easing.out(Easing.cubic)) =>
    interpolate(t, [a, b], [from, to], { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const a1 = io(0, 1.0, 0, 1);
  const a2 = io(0.4, 1.6, 0, 1);
  const spread1 = io(0, 3.0, 0.9, 0.55);
  const spread2 = io(0.4, 3.3, 0.34, 0.16);
  const line = io(1.0, 2.5, 0, 1);
  const rise = io(0.4, 2.0, 26, 0);
  const glow = 0.55 + 0.15 * Math.sin(t * 2.6);
  // anamorphic light sweep across the title
  const sweep = io(1.0, 2.4, -0.3, 1.3, Easing.inOut(Easing.sin));
  const sweepA = Math.sin(clamp01((t - 1.0) / 1.4) * Math.PI) * 0.85;
  return (
    <AbsoluteFill style={{ fontFamily: "Montserrat", alignItems: "center" }}>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 900,
          background: `linear-gradient(to bottom, rgba(4,23,38,${0.6 * a1}), rgba(4,23,38,0))`,
        }}
      />
      <div style={{ position: "absolute", top: 300, width: W, textAlign: "center" }}>
        <div
          style={{
            color: COLORS.gold,
            fontWeight: 300,
            fontSize: 58,
            letterSpacing: `${spread1}em`,
            marginRight: `-${spread1}em`,
            opacity: a1,
            textShadow: "0 2px 18px rgba(4,23,38,0.8)",
          }}
        >
          THE DEEP
        </div>
        <div
          style={{
            color: COLORS.cyan,
            fontWeight: 600,
            fontSize: 210,
            lineHeight: 1.05,
            letterSpacing: `${spread2}em`,
            marginRight: `-${spread2}em`,
            opacity: a2,
            transform: `translateY(${rise}px)`,
            textShadow: `0 0 28px rgba(92,225,255,${glow}), 0 0 70px rgba(92,225,255,${glow * 0.5}), 0 4px 24px rgba(4,23,38,0.9)`,
          }}
        >
          CITY
        </div>
        <div
          style={{
            margin: "34px auto 0",
            width: 560 * line,
            height: 3,
            background: `linear-gradient(to right, rgba(255,196,107,0), ${COLORS.gold}, rgba(255,196,107,0))`,
            boxShadow: `0 0 16px ${COLORS.gold}`,
          }}
        />
      </div>
      {/* light sweep */}
      <div
        style={{
          position: "absolute",
          top: 300 + 175,
          left: sweep * W - 450,
          width: 900,
          height: 10,
          background: "linear-gradient(to right, rgba(160,235,255,0), rgba(220,250,255,0.95), rgba(160,235,255,0))",
          filter: "blur(4px)",
          opacity: sweepA,
          mixBlendMode: "screen",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 300 + 80,
          left: sweep * W - 160,
          width: 320,
          height: 200,
          background: "radial-gradient(ellipse at center, rgba(180,240,255,0.55), rgba(180,240,255,0) 70%)",
          opacity: sweepA * 0.8,
          mixBlendMode: "screen",
        }}
      />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Main composition */
const Picture: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ background: COLORS.navy, overflow: "hidden" }}>
      <Sequence durationInFrames={SHOTS.dive.end + 2}>
        <DiveScene />
      </Sequence>
      <Sequence from={SHOTS.city.start} durationInFrames={SHOTS.city.end - SHOTS.city.start + 12}>
        <CityScene />
      </Sequence>
      <Sequence from={SHOTS.street.start}>
        <StreetScene />
      </Sequence>
      <Grade />
      <Sequence from={TITLE_IN}>
        <Title />
      </Sequence>
      <Vignette />
      <Grain frame={f} />
    </AbsoluteFill>
  );
};

export const DeepCity: React.FC = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 12], [1, 0], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(f, [DURATION - 20, DURATION - 1], [0, 1], { extrapolateLeft: "clamp" });
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      <CameraMotionBlur shutterAngle={180} samples={6}>
        <Picture />
      </CameraMotionBlur>
      <AbsoluteFill style={{ background: "#000", opacity: Math.max(fadeIn, fadeOut) }} />
      <Audio src={staticFile("soundtrack_15s.wav")} />
    </AbsoluteFill>
  );
};

