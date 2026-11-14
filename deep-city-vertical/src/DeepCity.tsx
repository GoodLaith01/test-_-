import "@fontsource/montserrat/300.css";
import "@fontsource/montserrat/600.css";
import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
} from "remotion";
import {
  Bubbles,
  camera,
  COLORS,
  GodRays,
  Grain,
  Lane,
  Particles,
  polyline,
  SRC_H,
  SRC_W,
  Traffic,
  Vignette,
  W,
} from "./effects";

export const FPS = 30;
export const DURATION = 15 * FPS; // 450 frames

// Scene timing (frames). Keyframes: Figma-generated, 864x1536 source units.
export const DIVE_END = 162; // dive sinks into deep navy by 5.4 s
export const CITY_START = 140; // over-the-shoulder city reveal from 4.7 s
export const CITY_END = 302;
export const STREET_START = 275; // street level from 9.2 s
export const TITLE_IN = 315; // 10.5 s

const ease = Easing.bezier(0.45, 0, 0.25, 1);
const k = (f: number, inp: number[], out: number[]) =>
  interpolate(f, inp, out, { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });
const lin = (f: number, inp: number[], out: number[]) =>
  interpolate(f, inp, out, { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

/** A SRC_W x SRC_H stage moved by the camera; children are placed in source units. */
const Stage: React.FC<{ cx: number; cy: number; z: number; children: React.ReactNode; filter?: string }> = ({
  cx,
  cy,
  z,
  children,
  filter,
}) => {
  const c = camera(cx, cy, z);
  return (
    <div
      style={{
        position: "absolute",
        width: SRC_W,
        height: SRC_H,
        transformOrigin: "0 0",
        transform: `translate(${c.tx}px, ${c.ty}px) scale(${c.z})`,
        filter,
      }}
    >
      {children}
    </div>
  );
};

const Plate: React.FC<{ src: string }> = ({ src }) => (
  <Img src={staticFile(src)} style={{ position: "absolute", left: 0, top: 0, width: SRC_W, height: SRC_H }} />
);

/** Foreground swimmer: scales about an anchor (nearer than the background -> parallax). */
const Swimmer: React.FC<{
  src: string;
  box: [number, number, number, number];
  anchor: [number, number];
  scale: number;
  shift: [number, number];
  children?: React.ReactNode;
}> = ({ src, box, anchor, scale, shift, children }) => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      transformOrigin: `${anchor[0]}px ${anchor[1]}px`,
      transform: `translate(${shift[0]}px, ${shift[1]}px) scale(${scale})`,
    }}
  >
    <Img
      src={staticFile(src)}
      style={{ position: "absolute", left: box[0], top: box[1], width: box[2] - box[0], height: box[3] - box[1] }}
    />
    {children}
  </div>
);

/* ------------------------------------------------------------------ Scene A: the dive */
const DiveScene: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / FPS;
  // push in on his face, then tilt down past his hands to the city glowing below
  const z = k(f, [0, 85, DIVE_END], [1.25, 1.42, 1.72]);
  const cy = k(f, [0, 85, DIVE_END], [768, 690, 980]);
  const cx = 432;
  // he swims toward the lens, then rushes into it: his dark body fills the frame as a wipe
  const rush = interpolate(f, [92, DIVE_END], [0, 1], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const manScale = lin(f, [0, 92], [1, 1.1]) + rush * 3.4;
  // keep his chest near the frame centre while the camera tilts down past him
  const bob: [number, number] = [3 * Math.sin(t * 1.3), 3 * Math.sin(t * 1.9 + 1) + rush * 150];
  const sink = 2.0 * t + Math.max(0, t - 3.0) ** 2 * 1.4;
  const deep = lin(f, [128, DIVE_END], [0, 1]);
  return (
    <AbsoluteFill>
      <Stage cx={cx} cy={cy} z={z} filter="saturate(1.04) contrast(1.04)">
        <Plate src="dive_plate.jpg" />
        <GodRays frame={f} sun={[600, -160]} seed="dive" opacity={0.45} length={1500} count={14} />
        <Swimmer src="dive_man.png" box={[137, 0, 711, 1032]} anchor={[430, 640]} scale={manScale} shift={bob}>
          <Bubbles frame={f} mouth={[432, 585]} bursts={[[0.1, 14], [1.4, 12], [2.7, 15], [3.9, 12]]} seed="db" />
        </Swimmer>
      </Stage>
      <Particles frame={f} cam={[0, sink, 0]} focus={2.5} gain={0.9} />
      <AbsoluteFill style={{ background: COLORS.navy, opacity: deep * 0.9 }} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Scene B: over-the-shoulder city reveal */
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
  const f = useCurrentFrame() + CITY_START; // absolute frame
  const t = f / FPS;
  // crane up from his shoulder and the traffic bridges to the towers
  const z = k(f, [CITY_START, CITY_END], [1.6, 1.3]);
  const cx = k(f, [CITY_START, CITY_END], [300, 470]);
  const cy = k(f, [CITY_START, CITY_END], [1110, 650]);
  const p = lin(f, [CITY_START, CITY_END], [0, 1]);
  const manScale = 1 + 0.14 * p;
  const shift: [number, number] = [4 * Math.sin(t * 1.2), 22 * p + 3 * Math.sin(t * 1.7)];
  const fog = lin(f, [CITY_START, 185], [1, 0]);
  return (
    <AbsoluteFill>
      <Stage cx={cx} cy={cy} z={z} filter="saturate(1.05) contrast(1.04)">
        <Plate src="city_plate.jpg" />
        <Traffic frame={f} lanes={CITY_LANES} />
        <GodRays frame={f} sun={[430, -260]} seed="city" opacity={0.32} length={1500} count={16} />
        <Swimmer src="city_man.png" box={[0, 888, 369, 1536]} anchor={[190, 1000]} scale={manScale} shift={shift}>
          <Bubbles frame={f} mouth={[300, 985]} bursts={[[5.0, 8], [6.6, 9], [8.2, 8]]} seed="cb" />
        </Swimmer>
      </Stage>
      <Particles frame={f} cam={[0.3 * p, -3.5 * p, 1.5 * p + 0.15 * t]} focus={3.2} gain={0.7} />
      <AbsoluteFill style={{ background: COLORS.navy, opacity: fog * 0.9 }} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Scene C: street level + title */
const STREET_LANES: Lane[] = (() => {
  const left = polyline([[490, 1185], [523, 1108]]);
  const right = polyline([[572, 1185], [540, 1108]]);
  return [
    { pl: left, n: 4, lane: 0, speed: -0.12, wNear: 0, wFar: 0, sz: [0.7, 1.6], key: "sl", fadeIn: 0.3 },
    { pl: right, n: 4, lane: 0, speed: 0.1, wNear: 0, wFar: 0, sz: [0.7, 1.6], key: "sr", fadeIn: 0.3 },
  ];
})();

const StreetScene: React.FC = () => {
  const f = useCurrentFrame() + STREET_START;
  const t = f / FPS;
  // slow push up the avenue, tilting up to the towers and swimmers
  const z = k(f, [STREET_START, DURATION], [1.3, 1.52]);
  const cx = k(f, [STREET_START, DURATION], [440, 470]);
  const cy = k(f, [STREET_START, DURATION], [1060, 640]);
  const p = lin(f, [STREET_START, DURATION], [0, 1]);
  const fadeIn = lin(f, [STREET_START, STREET_START + 27], [0, 1]);
  return (
    <AbsoluteFill style={{ opacity: fadeIn }}>
      <Stage cx={cx} cy={cy} z={z} filter="saturate(1.05) contrast(1.04)">
        <Plate src="street.jpg" />
        <Traffic frame={f} lanes={STREET_LANES} />
        <GodRays frame={f} sun={[560, -220]} seed="street" opacity={0.3} length={1500} count={12} />
      </Stage>
      <Particles frame={f} cam={[0.2 * p, -2.2 * p, 2.5 * p + 0.15 * t]} focus={3.0} gain={0.6} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Title */
const Title: React.FC = () => {
  const f = useCurrentFrame(); // relative to TITLE_IN
  const a1 = interpolate(f, [0, 30], [0, 1], { extrapolateRight: "clamp" });
  const a2 = interpolate(f, [12, 48], [0, 1], { extrapolateRight: "clamp" });
  const spread1 = interpolate(f, [0, 90], [0.9, 0.55], { easing: Easing.out(Easing.cubic), extrapolateRight: "clamp" });
  const spread2 = interpolate(f, [12, 100], [0.34, 0.16], { easing: Easing.out(Easing.cubic), extrapolateRight: "clamp" });
  const line = interpolate(f, [30, 75], [0, 1], { easing: Easing.out(Easing.cubic), extrapolateRight: "clamp" });
  const rise = interpolate(f, [12, 60], [26, 0], { easing: Easing.out(Easing.cubic), extrapolateRight: "clamp" });
  const glow = 0.55 + 0.15 * Math.sin(f / 9);
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
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Main composition */
export const DeepCity: React.FC = () => {
  const f = useCurrentFrame();
  const fadeIn = interpolate(f, [0, 14], [1, 0], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(f, [DURATION - 24, DURATION - 1], [0, 1], { extrapolateLeft: "clamp" });
  return (
    <AbsoluteFill style={{ background: COLORS.navy, overflow: "hidden" }}>
      <Sequence durationInFrames={DIVE_END + 5}>
        <DiveScene />
      </Sequence>
      <Sequence from={CITY_START} durationInFrames={CITY_END - CITY_START}>
        <CityScene />
      </Sequence>
      <Sequence from={STREET_START}>
        <StreetScene />
      </Sequence>
      <Sequence from={TITLE_IN}>
        <Title />
      </Sequence>
      <Vignette />
      <Grain frame={f} />
      <AbsoluteFill style={{ background: "#000", opacity: Math.max(fadeIn, fadeOut) }} />
      <Audio src={staticFile("soundtrack_15s.wav")} />
    </AbsoluteFill>
  );
};
