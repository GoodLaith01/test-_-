"""Original soundtrack for the AC -> DC reel. 120 BPM, 50 s, written to sync with the visuals.

Story told by the music:
  0-4 s   intro pad
  4-28 s  AC section: each bar is one AC cycle. First half (A is +) plays high / rising (amber),
          second half (B is +) plays low / falling (cyan).
  28-30 s capacitor drops in (whoosh + impact)
  30-38 s frequency sweep 0.5 -> 50 Hz: one note per half-cycle, so the arpeggio speeds up with the AC
  38-46 s DC drop: the sub-bass holds ONE steady note (that's DC), bright major groove
  46-54 s outro (summary + device card)
Usage: python3 music.py out.wav [events.json]
"""
import sys, wave
import numpy as np

SR = 44100
DUR = 54.0
N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(7)
BEAT = 0.5
EV = {'kick': [], 'snare': [], 'bell': [], 'sq': [], 'tri': []}  # event times, exported for the animation

def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)

def env(n, a=0.005, d=0.1, s=0.6, r=0.05, hold=None):
    t = np.arange(n) / SR
    hold = n / SR - r if hold is None else hold
    e = np.where(t < a, t / max(a, 1e-6), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-6)))
    rel = np.clip((t - hold) / max(r, 1e-6), 0, 1)
    return e * (1 - rel)

def osc(kind, freq, n):
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(freq, (n,))) / SR
    if kind == 'sine': return np.sin(ph)
    if kind == 'square':  # band-limited-ish: few odd harmonics
        return sum(np.sin(k * ph) / k for k in (1, 3, 5, 7, 9)) * 0.9
    if kind == 'tri':
        return sum(((-1) ** ((k - 1) // 2)) * np.sin(k * ph) / k ** 2 for k in (1, 3, 5, 7)) * 0.95
    if kind == 'saw':
        return sum(((-1) ** (k + 1)) * np.sin(k * ph) / k for k in range(1, 12)) * 0.6
    raise ValueError(kind)

def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc; y[i] = acc
    return y

def add(t0, sig, gain=1.0, pan=0.0):
    i0 = int(t0 * SR)
    if i0 >= N: return
    sig = sig[: N - i0]
    gl, gr = gain * np.sqrt((1 - pan) / 2), gain * np.sqrt((1 + pan) / 2)
    L[i0:i0 + len(sig)] += sig * gl; R[i0:i0 + len(sig)] += sig * gr

def note(t0, midi, dur, kind='square', gain=0.2, pan=0.0, a=0.004, d=0.12, s=0.5, r=0.04):
    if kind == 'square': EV['sq'].append(t0)
    if kind == 'tri': EV['tri'].append(t0)
    n = int((dur + r) * SR)
    add(t0, osc(kind, mtof(midi), n) * env(n, a, d, s, r, hold=dur), gain, pan)

# ---------- drums ----------
def kick(t0, g=0.9):
    EV['kick'].append(t0)
    n = int(0.35 * SR); t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    add(t0, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * g)
    duck(t0)

def snare(t0, g=0.35):
    EV['snare'].append(t0)
    n = int(0.25 * SR); t = np.arange(n) / SR
    nz = rng.standard_normal(n); nz = nz - lowpass(nz, 1500)
    add(t0, (nz * np.exp(-t * 18) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25)) * g)

def clap(t0, g=0.3):
    EV['snare'].append(t0)
    for k, dt in enumerate((0, 0.011, 0.022)):
        n = int(0.18 * SR); t = np.arange(n) / SR
        nz = rng.standard_normal(n); nz = nz - lowpass(nz, 1200)
        add(t0 + dt, nz * np.exp(-t * (30 if k < 2 else 14)) * g, pan=(-0.2, 0.2, 0)[k])

def hat(t0, g=0.12, open_=False, pan=0.25):
    n = int((0.25 if open_ else 0.05) * SR); t = np.arange(n) / SR
    nz = rng.standard_normal(n); nz = nz - lowpass(nz, 7000)
    add(t0, nz * np.exp(-t * (14 if open_ else 70)) * g, pan=pan)

duck_env = np.ones(N)
def duck(t0, depth=0.55, length=0.22):
    i0 = int(t0 * SR); n = int(length * SR)
    seg = 1 - depth * (1 - np.arange(n) / n) ** 2
    end = min(N, i0 + n)
    duck_env[i0:end] = np.minimum(duck_env[i0:end], seg[: end - i0])

# separate bus for sidechained instruments (pads, chords)
PL = np.zeros(N); PR = np.zeros(N)
def pad(t0, midis, dur, gain=0.06, cutoff=1400):
    n = int((dur + 0.6) * SR)
    sig = sum(osc('saw', mtof(m) * (1 + det), n) for m in midis for det in (-0.004, 0.004))
    sig = lowpass(sig, cutoff) * env(n, a=0.35, d=0.5, s=0.85, r=0.6, hold=dur)
    i0 = int(t0 * SR); sig = sig[: N - i0]
    PL[i0:i0 + len(sig)] += sig * gain; PR[i0:i0 + len(sig)] += sig * gain * 0.95

def bell(t0, midi, g=0.12, pan=0.0):
    EV['bell'].append(t0)
    n = int(1.2 * SR); t = np.arange(n) / SR; f = mtof(midi)
    sig = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)) * np.exp(-t * 3.5)
    add(t0, sig, g, pan)

# ---------- harmony ----------
A2, C3, D3, E3, F2, G2 = 45, 48, 50, 52, 41, 43
minor_prog = [(57, 60, 64), (53, 57, 60), (48, 52, 55), (55, 59, 62)]   # Am F C G
minor_root = [A2, F2, C3 - 12 + 12, G2]                                    # A2 F2 C3 G2
major_prog = [(57, 61, 64), (52, 56, 59), (54, 57, 61), (50, 54, 57)]   # A E F#m D
BAR = 2.0

# intro 0-4
pad(0, (57, 60, 64), 3.9, gain=0.05, cutoff=700)
for k in range(8): hat(2 + k * 0.25, g=0.05 + k * 0.01)
bell(3.5, 76, 0.08)

# AC section 4-28 (bars 2..13). Bar = one AC cycle: [A positive][B positive]
for b in range(12):
    t0 = 4 + b * BAR
    chord = minor_prog[b % 4]; root = minor_root[b % 4]
    # drums
    for q in range(4):
        if q in (0, 2): kick(t0 + q * BEAT)
        if q in (1, 3): snare(t0 + q * BEAT)
        hat(t0 + q * BEAT + 0.25, g=0.1)
        if b >= 3: hat(t0 + q * BEAT, g=0.06, pan=-0.25)
    # bass: positive half bounces up (root+12), negative half drops low (root)
    for e in range(4):
        note(t0 + e * 0.25, root + 12 + (12 if e % 2 else 0), 0.2, 'square', 0.13, a=0.002, d=0.08, s=0.4)
    for e in range(4):
        note(t0 + 1 + e * 0.25, root - (0 if e % 2 else 0) - (12 if e % 2 else 0) + 12, 0.2, 'tri', 0.22, a=0.002, d=0.1, s=0.6)
    if b >= 3: pad(t0, chord, BAR - 0.05, gain=0.035, cutoff=1100)
    # bridge 14-28: amber arpeggio climbs (D1+D3), cyan arpeggio falls (D2+D4)
    if b >= 5:
        up = [chord[0] + 12, chord[1] + 12, chord[2] + 12, chord[0] + 24]
        for i, m in enumerate(up * 2):
            note(t0 + i * 0.125, m, 0.1, 'square', 0.055, pan=-0.35, a=0.002, d=0.06, s=0.3)
        for i, m in enumerate(list(reversed(up)) * 2):
            note(t0 + 1 + i * 0.125, m - 12, 0.1, 'tri', 0.11, pan=0.35, a=0.002, d=0.06, s=0.4)
    # pulsating DC 22-28: a bell on every peak = every lamp flash
    if b >= 9:
        bell(t0 + 0.5, chord[2] + 12, 0.09, -0.2)
        bell(t0 + 1.5, chord[2] + 12, 0.09, 0.2)

# capacitor drop 28-30
n = int(0.6 * SR); t = np.arange(n) / SR
nz = rng.standard_normal(n); sweep = lowpass(nz, 3000) * (t / 0.6) ** 2 * 0.25
add(28.0, sweep)
kick(28.6, 1.1); bell(28.6, 57, 0.15); bell(28.6, 69, 0.1)
pad(28.6, (45, 52, 57), 1.3, gain=0.06, cutoff=600)
note(28.6, 33, 1.3, 'sine', 0.35, a=0.01, d=0.6, s=0.5, r=0.2)

# frequency sweep 30-38: f goes 0.5 -> 50 Hz exponentially, one note per AC half-cycle
f0, f1, T0, T1 = 0.5, 50.0, 30.0, 38.0
k = np.log(f1 / f0) / (T1 - T0)
times = []
t = T0
while t < T1:
    times.append(t)
    f = f0 * np.exp(k * (t - T0))
    t += 1 / (2 * f)
arp = [57, 60, 64, 69, 72, 76]
for i, tn in enumerate(times):
    if tn > T1 - 0.02: break
    prog = (tn - T0) / (T1 - T0)
    dur = max(0.02, min(0.2, 1 / (2 * f0 * np.exp(k * (tn - T0))) * 0.8))
    m = arp[i % len(arp)] + int(prog * 12)
    note(tn, m, dur, 'square' if i % 2 == 0 else 'tri', 0.06 + 0.04 * prog, pan=-0.3 if i % 2 == 0 else 0.3, a=0.001, d=0.04, s=0.5, r=0.01)
# noise riser and drums building
n = int(8 * SR); tt = np.arange(n) / SR
riser = rng.standard_normal(n); riser = riser - lowpass(riser, 800)
add(30, riser * (tt / 8) ** 2.5 * 0.14)
for q in range(16):
    tq = 30 + q * BEAT
    kick(tq, 0.7 + 0.2 * q / 16)
    if q >= 8: hat(tq + 0.25, 0.08)
for q in range(16):  # snare roll in the last 2 s
    snare(36 + q * 0.125, 0.12 + 0.2 * q / 16)

# DC drop 38-46: bright major groove, sub-bass holds ONE steady A (DC = constant)
note(38, 33, 8.0, 'sine', 0.42, a=0.02, d=0.3, s=0.9, r=0.3)
note(38, 45, 8.0, 'tri', 0.07, a=0.02, d=0.3, s=0.8, r=0.3)
melody = [76, 76, 73, 76, 78, 76, 73, 71,  71, 71, 68, 71, 73, 71, 68, 64,
          73, 73, 69, 73, 76, 73, 69, 66,  74, 73, 71, 69, 71, 73, 76, 81]
for b in range(4):
    t0 = 38 + b * BAR
    chord = major_prog[b]
    for q in range(4):
        kick(t0 + q * BEAT, 0.95)
        if q in (1, 3): clap(t0 + q * BEAT)
        hat(t0 + q * BEAT + 0.25, 0.1, open_=True)
        hat(t0 + q * BEAT + 0.125, 0.05, pan=-0.3); hat(t0 + q * BEAT + 0.375, 0.05, pan=-0.3)
        for m in chord:  # off-beat stabs
            note(t0 + q * BEAT + 0.25, m + 12, 0.12, 'saw', 0.03, a=0.002, d=0.08, s=0.3)
    pad(t0, chord, BAR - 0.05, gain=0.03, cutoff=1800)
    for i in range(8):
        note(t0 + i * 0.25, melody[b * 8 + i], 0.2, 'square', 0.07, pan=0.1, a=0.003, d=0.1, s=0.55)

# outro 46-54: summary and device card on screen
kick(46, 1.0); clap(46)
pad(46, (57, 61, 64, 69), 3.9, gain=0.06, cutoff=1600)
pad(50, (50, 54, 57, 62), 3.6, gain=0.055, cutoff=1400)
note(46, 33, 3.8, 'sine', 0.3, a=0.01, d=1.2, s=0.45, r=0.6)
note(50, 38, 3.4, 'sine', 0.26, a=0.05, d=1.2, s=0.45, r=0.8)
for i, m in enumerate([69, 73, 76, 81]): bell(46.5 + i * 0.25, m, 0.1, (-0.3, -0.1, 0.1, 0.3)[i])
for i, m in enumerate([81, 76, 73, 69]): bell(50.0 + i * 0.25, m, 0.07, (0.3, 0.1, -0.1, -0.3)[i])
bell(52.0, 57, 0.08)

# ---------- mix ----------
L += PL * duck_env; R += PR * duck_env
fade = np.ones(N); fn = int(1.6 * SR); fade[-fn:] = np.linspace(1, 0, fn) ** 1.5
fi = int(0.05 * SR); fade[:fi] = np.linspace(0, 1, fi)
mix = np.stack([L, R], 1) * fade[:, None]
mix = np.tanh(mix * 1.6) / np.tanh(1.6)
mix /= np.max(np.abs(mix)) / 0.89
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
# ---------- export events + per-frame spectrum for the animation ----------
import json
mono = mix.mean(1); FPS = 30; WIN = 2048; NB = 32
edges = np.geomspace(40, 12000, NB + 1)
freqs = np.fft.rfftfreq(WIN, 1 / SR); win = np.hanning(WIN)
spec = []; prev = np.zeros(NB)
for f in range(int(DUR * FPS)):
    c = int(f / FPS * SR); seg = mono[max(0, c - WIN // 2): c + WIN // 2]
    seg = np.pad(seg, (0, WIN - len(seg)))
    mag = np.abs(np.fft.rfft(seg * win))
    bands = np.array([mag[(freqs >= edges[i]) & (freqs < edges[i + 1])].mean() if np.any((freqs >= edges[i]) & (freqs < edges[i + 1])) else 0 for i in range(NB)])
    db = np.clip((20 * np.log10(bands + 1e-9) + 10) / 50, 0, 1)
    prev = np.where(db > prev, db, prev * 0.8 + db * 0.2)
    spec.append([round(float(x), 3) for x in prev])
out = {k: sorted(round(t, 4) for t in v) for k, v in EV.items()}
out['spec'] = spec
pathlib_out = (sys.argv[2] if len(sys.argv) > 2 else 'events.json')
with open(pathlib_out, 'w') as fh: json.dump(out, fh, separators=(',', ':'))
print('ok', DUR, 's', {k: len(v) for k, v in EV.items()})
