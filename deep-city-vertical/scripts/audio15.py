"""Synthesize the 15 s underwater soundtrack for the vertical cut (48 kHz stereo WAV).

Layers: plunge whoosh at the start, muffled ocean bed, breath bubbles synced to
the visual bubble bursts, a dark drone that blooms into a major "wonder" chord
at the city reveal, a sub-boom on the cut, distant city hum, and a synthetic
reverb tail.  Usage: python3 audio.py out.wav
"""
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR, DUR = 48000, 15.0
N = int(SR * DUR)
t = np.arange(N) / SR
rng = np.random.default_rng(3)


def lp(x, fc, order=4):
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=3):
    return sosfilt(butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def env(a, b, attack, release):
    """Window active on [a, b] seconds with smooth attack/release."""
    up = np.clip((t - a) / attack, 0, 1)
    down = np.clip((b - t) / release, 0, 1)
    e = np.minimum(up, down)
    return e * e * (3 - 2 * e)


def stereo(x, width=0.0):
    d = int(SR * 0.011)
    r = np.concatenate([np.zeros(d), x[:-d]])
    return np.stack([x * (1 - width) + r * width, r * (1 - width) + x * width], 1)


L = np.zeros((N, 2))

# 1. Plunge: noise burst sweeping down, plus fizz.
noise = rng.standard_normal(N)
plunge = np.zeros(N)
seg = int(SR * 1.2)
fcs = np.geomspace(3500, 250, 6)
for k, fc in enumerate(fcs):
    a, b = int(k * seg / 6), int((k + 1) * seg / 6)
    plunge[a:b] = lp(noise, fc)[a:b]
plunge *= np.exp(-t / 0.45) * (t < 1.4) * np.clip(t / 0.02, 0, 1)
fizz = bp(rng.standard_normal(N), 2500, 9000) * np.exp(-t / 0.7) * (rng.random(N) < 0.02) * 6
L += stereo(plunge * 0.32 + fizz * 0.12, 0.3)

# 2. Ocean bed: brown noise, heavily low-passed, slow swell.
brown = np.cumsum(rng.standard_normal(N))
brown -= lp(brown, 0.3, 2)
brown = lp(brown, 380) / np.abs(brown).max()
swell = 0.75 + 0.25 * np.sin(2 * np.pi * 0.13 * t) * np.sin(2 * np.pi * 0.07 * t + 1)
L += stereo(brown * swell * 0.16, 0.5)

# 3. Breath bubbles in sync with the picture's bubble bursts.
bub = np.zeros(N)
for t0, n, vol in [(0.1, 14, 1.0), (1.4, 11, 0.9), (2.7, 15, 1.0), (4.0, 12, 0.8), (5.3, 10, 0.7),
                   (6.2, 10, 0.4), (7.8, 12, 0.4), (9.4, 10, 0.35), (11.0, 9, 0.3), (12.6, 9, 0.3)]:
    for j in range(n):
        ts = t0 + j * rng.uniform(0.03, 0.09) + rng.uniform(0, 0.05)
        f0 = rng.uniform(380, 1200)
        dur = rng.uniform(0.03, 0.08)
        i0 = int(ts * SR)
        m = int(dur * SR * 3)
        if i0 + m >= N:
            continue
        tt = np.arange(m) / SR
        f = f0 * (1 + 1.6 * tt / dur)
        bub[i0:i0 + m] += np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / dur) * vol * rng.uniform(0.3, 1.0)
bub = lp(bub, 2600)
L += stereo(bub * 0.34, 0.6)


# 4. Music: dark drone -> wonder chord at the reveal.
def pad(freqs, detune=0.004, bright=1500):
    out = np.zeros(N)
    for f in freqs:
        for d in (-detune, 0, detune):
            ph = rng.uniform(0, 6.28)
            ff = f * (1 + d)
            # soft saw from a few harmonics
            for h in range(1, 7):
                out += np.sin(2 * np.pi * ff * h * t + ph * h) / h ** 1.3
    return lp(out, bright) / (len(freqs) * 3 * 2.5)


note = lambda m: 440.0 * 2 ** ((m - 69) / 12)
dark = pad([note(38), note(45), note(53)], bright=700)                     # D2 A2 F3
wonder = pad([note(38), note(45), note(54), note(57), note(64), note(69)], bright=2600)  # D maj add9
shimmer = sum(np.sin(2 * np.pi * note(m) * t) * (0.5 + 0.5 * np.sin(2 * np.pi * r * t))
              for m, r in [(81, 0.9), (86, 1.3), (88, 0.7), (93, 1.1)]) / 4
music = dark * env(0.2, 6.8, 1.8, 1.0) * 0.55
music += wonder * env(6.0, 15.0, 2.0, 1.6) * 0.75
music += shimmer * env(7.0, 15.0, 2.5, 1.8) * 0.05
L += stereo(music * 3.2, 0.35)

# 5. Sub boom on the reveal cut.
tb = np.clip(t - 6.3, 0, None)
boom = np.sin(2 * np.pi * (52 * tb - 6 * tb * tb)) * np.exp(-tb / 0.9) * (t >= 6.3)
boom += lp(rng.standard_normal(N), 160) * np.exp(-tb / 0.35) * (t >= 6.3) * 0.6
L += stereo(boom * 0.5, 0.0)

# 6. Distant city: low hum + soft traffic swish.
hum = (np.sin(2 * np.pi * 58 * t) * 0.4 + np.sin(2 * np.pi * 116 * t) * 0.15) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.5 * t))
swish = bp(rng.standard_normal(N), 180, 900) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * t + 2))
L += stereo((hum * 0.2 + swish * 0.25) * env(6.4, 15, 2.0, 1.4), 0.8)

# 6b. Title chime at 11.0 s: soft inharmonic bell (D6 family).
tc = np.clip(t - 11.0, 0, None)
chime = sum(a * np.sin(2 * np.pi * fr * tc) * np.exp(-tc / d)
            for fr, a, d in [(1174.7, 1.0, 1.6), (1761.0, 0.5, 1.1), (2349.3, 0.35, 0.8), (3227.0, 0.18, 0.5)]) * (t >= 11.0)
chime *= np.clip(tc / 0.004, 0, 1)
L += stereo(chime * 0.12, 0.5)

# 7. Reverb: exponentially decaying noise IR, per channel.
ir_len = int(SR * 2.6)
for c in range(2):
    ir = rng.standard_normal(ir_len) * np.exp(-np.arange(ir_len) / (SR * 0.55))
    ir = lp(ir, 3000)
    ir /= np.sqrt((ir ** 2).sum())
    wet = fftconvolve(L[:, c], ir)[:N]
    L[:, c] = L[:, c] * 0.75 + wet * 0.45

# fades + normalise
L *= (np.clip(t / 0.15, 0, 1) * np.clip((DUR - t) / 1.0, 0, 1))[:, None]
L = np.tanh(L / np.abs(L).max() * 1.1) / np.tanh(1.1) * 0.89
wavfile.write(sys.argv[1] if len(sys.argv) > 1 else "soundtrack.wav", SR, (L * 32767).astype(np.int16))
print("ok", L.shape)
