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
  Particles,
  SRC_H,
  SRC_W,
  Traffic,
  Vignette,
  W,
} from "./effects";

export const FPS = 30;
export const DURATION = 15 * FPS; // 450 frames

// Scene boundaries (frames)
export const DIVE_END = 205; // dive sinks into deep blue by ~6.8s
export const CITY_START = 180; // city emerges from the blue at 6.0s
export const TITLE_IN = 330; // 11.0s

const ease = Easing.bezier(0.45, 0, 0.25, 1);
const k = (f: number, inp: number[], out: number[]) =>
  interpolate(f, inp, out, { easing: ease, extrapolateLeft: "clamp", extrapolateRight: "clamp" });

/** A SRC_W x SRC_H stage moved by the camera; children are placed in source pixels. */
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
    <Img src={staticFile(src)} style={{ position: "absolute", left: box[0], top: box[1], width: box[2] - box[0], height: box[3] - box[1] }} />
    {children}
  </div>
);

/* ------------------------------------------------------------------ Scene A: the dive */
const DiveScene: React.FC = () => {
  const f = useCurrentFrame();
  const t = f / FPS;
  const z = k(f, [0, 100, DIVE_END], [1.3, 1.42, 1.68]);
  const cx = k(f, [0, 100, DIVE_END], [1190, 1120, 960]);
  const cy = k(f, [0, 100, DIVE_END], [640, 760, 960]);
  const manScale = k(f, [0, DIVE_END], [1, 1.07]);
  const bob: [number, number] = [4 * Math.sin(t * 1.3), 3 * Math.sin(t * 1.9 + 1)];
  // camera sinks -> world rises past the lens, faster towards the end
  const sink = 2.0 * t + Math.max(0, t - 4.5) ** 2 * 1.2;
  const deep = interpolate(f, [165, DIVE_END], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <Stage cx={cx} cy={cy} z={z} filter="saturate(1.05) contrast(1.04)">
        <Img src={staticFile("dive_plate.jpg")} style={{ position: "absolute", width: SRC_W, height: SRC_H }} />
        <GodRays frame={f} sun={[1160, -140]} seed="dive" opacity={0.55} length={2300} />
        <Swimmer src="dive_man.png" box={[646, 0, 2222, 1536]} anchor={[1300, 700]} scale={manScale} shift={bob}>
          <Bubbles frame={f} mouth={[1082, 800]} bursts={[[0.1, 14], [1.4, 11], [2.7, 15], [4.0, 12], [5.3, 10]]} seed="db" />
        </Swimmer>
      </Stage>
      <Particles frame={f} cam={[0, sink, 0]} focus={2.5} gain={0.9} />
      <AbsoluteFill style={{ background: COLORS.navy, opacity: deep * 0.92 }} />
    </AbsoluteFill>
  );
};

/* ------------------------------------------------------------------ Scene B: the city reveal */
const CityScene: React.FC = () => {
  const f = useCurrentFrame() + CITY_START; // absolute frame
  const t = f / FPS;
  const z = k(f, [CITY_START, 330, DURATION], [1.3, 1.34, 1.62]);
  const cx = k(f, [CITY_START, 330, DURATION], [700, 1720, 2010]);
  const cy = k(f, [CITY_START, 330, DURATION], [790, 790, 700]);
  const p = k(f, [CITY_START, DURATION], [0, 1]);
  const manScale = 1 + 0.18 * p;
  const shift: [number, number] = [-260 * p * p + 5 * Math.sin(t * 1.2), 70 * p * p + 4 * Math.sin(t * 1.7 + 0.5)];
  const fog = interpolate(f, [CITY_START, 245], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <Stage cx={cx} cy={cy} z={z} filter="saturate(1.06) contrast(1.05)">
        <Img src={staticFile("city_plate.jpg")} style={{ position: "absolute", width: SRC_W, height: SRC_H }} />
        <Traffic frame={f} />
        <GodRays frame={f} sun={[1600, -420]} seed="city" opacity={0.42} length={2600} count={18} />
        <Swimmer src="city_man.png" box={[0, 470, 1184, 1536]} anchor={[880, 1080]} scale={manScale} shift={shift}>
          <Bubbles frame={f} mouth={[1098, 690]} bursts={[[6.2, 10], [7.8, 12], [9.4, 10], [11, 9], [12.6, 9]]} seed="cb" />
        </Swimmer>
      </Stage>
      <Particles frame={f} cam={[1.2 * p, 0.4 * p, 5.5 * p + 0.2 * t]} focus={3.5} gain={0.7} />
      <AbsoluteFill style={{ background: COLORS.navy, opacity: fog * 0.92 }} />
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
      {/* soft navy wash so the title reads over the light rays */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 900,
          background: `linear-gradient(to bottom, rgba(4,23,38,${0.55 * a1}), rgba(4,23,38,0))`,
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
      <Sequence from={CITY_START}>
        <CityScene />
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
