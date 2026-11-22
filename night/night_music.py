"""Original calm soundtrack for "The most beautiful moments of the night". 80 BPM, 60 s.
Exports the timing of kicks, bells and music-box notes so the animation can follow the music.
Usage: python3 night_music.py out.wav events.json
"""
import sys, json, wave
import numpy as np

SR = 44100; DUR = 60.0; N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(11)
BEAT = 0.75; BAR = 3.0
EV = {'kick': [], 'bell': [], 'mel': [], 'whoosh': []}

def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)

def add(t0, sig, gain=1.0, pan=0.0):
    i0 = int(t0 * SR)
    if i0 >= N: return
    sig = sig[: N - i0]
    L[i0:i0 + len(sig)] += sig * gain * np.sqrt((1 - pan) / 2)
    R[i0:i0 + len(sig)] += sig * gain * np.sqrt((1 + pan) / 2)

def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR); y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc; y[i] = acc
    return y

def piano(t0, midi, gain=0.12, pan=0.0, length=2.2):
    n = int(length * SR); t = np.arange(n) / SR; f = mtof(midi)
    sig = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) * np.exp(-t * 3) + 0.12 * np.sin(6 * np.pi * f * t) * np.exp(-t * 5))
    sig *= np.exp(-t * 2.2) * np.minimum(1, t / 0.004)
    add(t0, sig, gain, pan)

def musicbox(t0, midi, gain=0.08, pan=0.0):
    EV['mel'].append(t0)
    n = int(1.6 * SR); t = np.arange(n) / SR; f = mtof(midi)
    sig = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 4.02 * t) * np.exp(-t * 9)) * np.exp(-t * 3.2) * np.minimum(1, t / 0.002)
    add(t0, sig, gain, pan)

def bell(t0, midi, gain=0.1, pan=0.0):
    EV['bell'].append(t0)
    n = int(3.0 * SR); t = np.arange(n) / SR; f = mtof(midi)
    sig = (np.sin(2 * np.pi * f * t) + 0.45 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 4) + 0.2 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 7)) * np.exp(-t * 1.6)
    add(t0, sig, gain, pan)

def pad(t0, midis, dur, gain=0.05, cutoff=1100):
    n = int((dur + 1.5) * SR); t = np.arange(n) / SR
    sig = sum(np.sin(2 * np.pi * mtof(m) * (1 + d) * t) + 0.3 * np.sin(4 * np.pi * mtof(m) * (1 + d) * t) for m in midis for d in (-0.003, 0.003))
    e = np.minimum(1, t / 0.9) * np.clip((dur + 1.5 - t) / 1.5, 0, 1)
    add(t0, lowpass(sig * e, cutoff), gain, 0.0)

def kick(t0, g=0.5):
    EV['kick'].append(t0)
    n = int(0.4 * SR); t = np.arange(n) / SR
    f = 42 + 70 * np.exp(-t * 22)
    add(t0, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) * g)

def brush(t0, g=0.05, pan=0.3):
    n = int(0.18 * SR); t = np.arange(n) / SR
    nz = rng.standard_normal(n); nz = nz - lowpass(nz, 5000)
    add(t0, nz * np.exp(-t * 22) * g, pan=pan)

def whoosh(t0, g=0.12):
    EV['whoosh'].append(t0)
    n = int(1.1 * SR); t = np.arange(n) / SR
    nz = lowpass(rng.standard_normal(n), 2500)
    add(t0, nz * np.sin(np.pi * t / 1.1) ** 2 * g, pan=-0.4)

# chords: Dmaj7, Bm7, Gmaj7, A6  (2 bars each)
CH = [(50, 54, 57, 61), (47, 50, 54, 57), (43, 47, 50, 54), (45, 49, 52, 54)]
BASS = [38, 35, 31, 33]

for b in range(20):
    t0 = b * BAR
    ch = CH[(b // 2) % 4]
    if b % 2 == 0: pad(t0, ch, 2 * BAR, gain=0.045)
    add_bass = 0.0 if t0 < 3 else 0.22
    if add_bass:
        n = int(BAR * SR); tt = np.arange(n) / SR
        add(t0, np.sin(2 * np.pi * mtof(BASS[(b // 2) % 4]) * tt) * np.minimum(1, tt / 0.05) * np.exp(-tt * 0.7), add_bass)
    # soft piano arpeggio from 6 s, resting in the quiet scene
    if 6 <= t0 < 57 and not (39 <= t0 < 45):
        arp = [ch[0] + 12, ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 12, ch[1] + 12, ch[3] + 12, ch[2] + 12]
        for i, m in enumerate(arp):
            piano(t0 + i * 0.375, m, 0.05 + (0.015 if i % 2 == 0 else 0), pan=(-0.25, 0.25)[i % 2])
    # gentle drums: 12-38 s and 45-57 s
    if (12 <= t0 < 38) or (45 <= t0 < 57):
        kick(t0, 0.45); kick(t0 + 1.5, 0.35)
        if t0 >= 18:
            for q in range(4): brush(t0 + q * BEAT + 0.375, 0.04)

# music-box melody while the city lights switch on (25-32 s)
mel = [74, 73, 71, 69, 71, 73, 74, 76, 78, 76, 74, 73, 71, 73, 74, 69]
for i, m in enumerate(mel):
    musicbox(24.75 + i * 0.4, m, 0.07, pan=(-0.2, 0.2)[i % 2])

# sparkles synced to the sky
bell(12.5, 86, 0.11)                                   # first star
for tb, m in ((18.6, 81), (20.1, 83), (21.6, 85), (23.1, 88)): bell(tb, m, 0.06, 0.3)  # stars fill the sky
whoosh(33.0); bell(33.5, 90, 0.08, 0.3)                # shooting star
whoosh(35.3); bell(35.8, 93, 0.07, 0.4)                # second one
for tb, m in ((39.0, 78), (41.25, 81), (43.5, 76)): bell(tb, m, 0.05)  # the quiet
bell(52.0, 74, 0.09); bell(52.0, 81, 0.06)             # dawn
pad(54, (50, 54, 57, 62, 66), 5.0, gain=0.05, cutoff=1500)
bell(56.0, 86, 0.08); bell(56.5, 90, 0.06); bell(57.0, 93, 0.05)  # good night

# space: a soft stereo echo
mix = np.stack([L, R], 1)
for k, (dl, dr) in enumerate(((0.375, 0.5), (0.75, 1.0), (1.125, 1.5))):
    gk = 0.22 * (0.55 ** k)
    il, ir = int(dl * SR), int(dr * SR)
    mix[il:, 1] += gk * L[:-il]; mix[ir:, 0] += gk * R[:-ir]
fade = np.ones(N); fn = int(2.0 * SR); fade[-fn:] = np.linspace(1, 0, fn) ** 1.4
fade[: int(0.8 * SR)] = np.linspace(0, 1, int(0.8 * SR))
mix *= fade[:, None]
mix = np.tanh(mix * 1.3) / np.tanh(1.3); mix /= np.max(np.abs(mix)) / 0.88
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
with open(sys.argv[2], 'w') as fh:
    json.dump({k: sorted(round(x, 4) for x in v) for k, v in EV.items()}, fh)
print('ok', {k: len(v) for k, v in EV.items()})
