"""8-bit chiptune soundtrack + sound effects for the retro "night" reel starring Clawd. 100 BPM, 60 s.
Every sound effect is placed on the same timeline the animation uses (jumps, landings, the coin, twinkles),
and all times are exported so the picture and the sound stay locked together.
Usage: python3 chip_music.py out.wav events.json
"""
import sys, json, wave
import numpy as np

SR = 44100; DUR = 60.0; N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(3)
BEAT = 0.6; BAR = 2.4
EV = {'beat': [], 'hop_land': [], 'hop_off': [], 'coin': [], 'twinkle': [], 'blip': [], 'sfx': []}

def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)

def add(t0, sig, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if i0 >= N or i0 < 0: return
    sig = sig[: N - i0]
    L[i0:i0 + len(sig)] += sig * gain * np.sqrt((1 - pan) / 2)
    R[i0:i0 + len(sig)] += sig * gain * np.sqrt((1 + pan) / 2)

def env(n, a=0.002, d=0.08, s=0.6, rel=0.03, hold=None):
    t = np.arange(n) / SR; hold = n / SR - rel if hold is None else hold
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / d))
    return e * (1 - np.clip((t - hold) / rel, 0, 1))

def pulse(freq, n, duty=0.25):
    ph = np.cumsum(np.broadcast_to(freq, (n,))) / SR
    return np.where((ph % 1.0) < duty, 1.0, -1.0)

def tri(freq, n):
    ph = np.cumsum(np.broadcast_to(freq, (n,))) / SR
    x = 4 * np.abs((ph % 1.0) - 0.5) - 1
    return np.round(x * 8) / 8            # 4-bit stepped triangle, like the NES

def noise(n, period=1):
    v = rng.choice([-1.0, 1.0], size=n // period + 1)
    return np.repeat(v, period)[:n]

def note(t0, midi, dur, wave='pulse', gain=0.1, duty=0.25, pan=0.0, d=0.1, s=0.55):
    n = int((dur + 0.03) * SR)
    sig = pulse(mtof(midi), n, duty) if wave == 'pulse' else tri(mtof(midi), n)
    add(t0, sig * env(n, d=d, s=s, hold=dur), gain, pan)

def kick(t0, g=0.35):
    EV['beat'].append(t0)
    n = int(0.12 * SR); t = np.arange(n) / SR
    add(t0, tri(160 * np.exp(-t * 30) + 40, n) * np.exp(-t * 18), g)

def snare(t0, g=0.12):
    n = int(0.12 * SR); t = np.arange(n) / SR
    add(t0, noise(n, 2) * np.exp(-t * 28), g)

def hat(t0, g=0.05):
    n = int(0.04 * SR); t = np.arange(n) / SR
    add(t0, noise(n, 1) * np.exp(-t * 90), g, 0.2)

def slide(t0, f0, f1, dur, g=0.12, duty=0.5, pan=0.0):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    add(t0, pulse(f, n, duty) * np.exp(-t * 3), g, pan)

# ---------- sound effects ----------
def sfx_jump(t0): EV['sfx'].append(('jump', t0)); slide(t0, 300, 900, 0.16, 0.10, 0.5)
def sfx_land(t0): EV['sfx'].append(('land', t0)); n = int(0.07 * SR); add(t0, noise(n, 6) * np.exp(-np.arange(n) / SR * 60), 0.12)
def sfx_coin(t0):
    EV['coin'].append(t0)
    note(t0, 83, 0.07, 'pulse', 0.12, 0.5, d=0.5, s=1); note(t0 + 0.07, 88, 0.45, 'pulse', 0.12, 0.5, d=0.25, s=0.4)
def sfx_twinkle(t0, base=84):
    EV['twinkle'].append(t0)
    for i, m in enumerate((base, base + 4, base + 7, base + 12)): note(t0 + i * 0.05, m, 0.08, 'pulse', 0.06, 0.125, 0.3, d=0.06)
def sfx_select(t0): EV['sfx'].append(('select', t0)); note(t0, 79, 0.06, 'pulse', 0.1, 0.5); note(t0 + 0.06, 91, 0.12, 'pulse', 0.1, 0.5)
def sfx_whoosh(t0, g=0.07):
    n = int(0.7 * SR); t = np.arange(n) / SR
    per = np.clip((1 + 6 * t / 0.7).astype(int), 1, 8)
    sig = np.concatenate([noise(1, p) for p in per]) if False else noise(n, 3)
    add(t0, sig * np.sin(np.pi * t / 0.7) ** 2, g, -0.3)
def sfx_yawn(t0): EV['sfx'].append(('yawn', t0)); slide(t0, 520, 180, 0.9, 0.08, 0.25)
def sfx_alert(t0): EV['sfx'].append(('alert', t0)); note(t0, 88, 0.06, 'pulse', 0.1, 0.5); note(t0 + 0.08, 88, 0.1, 'pulse', 0.1, 0.5)

# ---------- music ----------
PROG = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]   # Am F C G
ROOT = [45, 41, 48, 43]
MAJ = [(60, 64, 67), (55, 59, 62), (57, 60, 64), (53, 57, 60)]     # C G Am F (sunrise)
MROOT = [48, 43, 45, 41]
THEME = [76, 74, 72, 74, 76, 79, 76, 74,  72, 69, 72, 74, 72, 69, 67, 69,
         72, 74, 76, 74, 72, 76, 79, 81,  79, 76, 74, 72, 74, 72, 71, 72]

# title jingle 0-2.4
for i, m in enumerate((60, 64, 67, 72, 76, 79, 84)): note(0.35 + i * 0.09, m, 0.09, 'pulse', 0.08, 0.25)
sfx_select(2.0)

for b in range(25):
    t0 = b * BAR
    if t0 < 2.4: continue
    sun = t0 >= 52.8
    ch = (MAJ if sun else PROG)[b % 4]; root = (MROOT if sun else ROOT)[b % 4]
    quiet = 38.4 <= t0 < 45.6
    sleepy = 45.6 <= t0 < 52.8
    end = t0 >= 57.6
    # bass (triangle)
    for q in range(4):
        if quiet and q % 2: continue
        note(t0 + q * BEAT, root - 12 + (12 if q % 2 and not sleepy else 0), BEAT * 0.9, 'tri', 0.28, d=0.3, s=0.7)
    # drums
    if not quiet and not sleepy and not end:
        for q in range(4):
            if q in (0, 2): kick(t0 + q * BEAT)
            if q in (1, 3): snare(t0 + q * BEAT)
            hat(t0 + q * BEAT + 0.3)
    # arpeggio (pulse 12.5%)
    step = 0.3 if not (quiet or sleepy) else 0.6
    k = 0
    while k * step < BAR - 0.01:
        m = ch[k % 3] + 12 + (12 if k % 6 >= 3 else 0)
        note(t0 + k * step, m - (12 if sleepy else 0), step * 0.8, 'pulse', 0.045 if not quiet else 0.035, 0.125, pan=-0.25, d=0.08, s=0.3)
        k += 1
    # main theme (pulse 25%) during the rooftop hops and the sunrise
    if 24.0 <= t0 < 33.6 or 52.8 <= t0 < 57.6:
        idx = int(round((t0 - (24.0 if t0 < 40 else 52.8)) / BAR))
        for i in range(8):
            m = THEME[(idx * 8 + i) % len(THEME)]
            note(t0 + i * 0.3, m, 0.26, 'pulse', 0.07, 0.25, pan=0.15, d=0.12, s=0.5)
            EV['blip'].append(round(t0 + i * 0.3, 4))
    # sleepy melody: slow and falling
    if sleepy:
        for i, m in enumerate((76, 72, 69, 67)):
            note(t0 + i * 0.6, m - (b % 2) * 2, 0.5, 'pulse', 0.05, 0.125, pan=0.2, d=0.3, s=0.4)

# moments
sfx_twinkle(12.5)                      # first star
for tb in (18.6, 19.8, 21.0): sfx_twinkle(tb, 79)   # moon rising
HOPS = [25.8, 27.0, 28.2, 29.4, 30.6, 31.8]
for tl in HOPS:
    EV['hop_off'].append(round(tl - 0.45, 4)); EV['hop_land'].append(tl)
    sfx_jump(tl - 0.45); sfx_land(tl)
sfx_whoosh(33.2)
sfx_alert(33.0)
sfx_jump(33.6); sfx_coin(34.0); sfx_land(34.45)
sfx_whoosh(35.8, 0.05)
for tb in (39.0, 41.4, 43.8): sfx_twinkle(tb, 91)
sfx_yawn(46.5)
sfx_alert(52.6)
sfx_jump(52.75); sfx_land(53.2)
# ending jingle
for i, m in enumerate((72, 76, 79, 84, 79, 84, 88)): note(57.6 + i * 0.12, m, 0.11, 'pulse', 0.09, 0.25, d=0.1)
note(58.5, 60, 1.2, 'pulse', 0.06, 0.5, d=0.5, s=0.5); note(58.5, 64, 1.2, 'pulse', 0.05, 0.25, d=0.5, s=0.5); note(58.5, 48, 1.3, 'tri', 0.3, d=0.6, s=0.6)

mix = np.stack([L, R], 1)
fade = np.ones(N); fn = int(0.8 * SR); fade[-fn:] = np.linspace(1, 0, fn)
mix *= fade[:, None]
mix /= np.max(np.abs(mix)) / 0.85
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
out = {k: (sorted(v) if k != 'sfx' else [[a, round(b, 4)] for a, b in v]) for k, v in EV.items()}
with open(sys.argv[2], 'w') as fh: json.dump(out, fh)
print('ok', {k: len(v) for k, v in EV.items()})
