"""Render "The Deep City" — a 10 s cinematic underwater video from two AI keyframes.

2.5D compositing: each keyframe is split into a background plate and a cut-out
swimmer (see segment.py). Per frame we move a virtual camera over both layers
with parallax and add procedural life: animated god rays, caustics on the
swimmer, kicking legs, breath bubbles, marine-snow particles in true 3D
perspective, moving car lights on the highway and bridge, water-refraction
shimmer, bloom, grade, grain and vignette.

Usage: python3 render.py <assets_dir> <out_video_without_audio.mp4>
"""
import math
import subprocess
import sys

import cv2
import numpy as np

ASSETS = sys.argv[1] if len(sys.argv) > 1 else "assets"
OUT = sys.argv[2] if len(sys.argv) > 2 else "video_noaudio.mp4"
PREVIEW = len(sys.argv) > 3  # any 3rd arg: only dump a few stills

W, H, FPS, DUR = 1920, 1080, 24, 10.0
NF = int(FPS * DUR)
SRC_W, SRC_H = 2752, 1536
rng = np.random.default_rng(7)


# ---------------------------------------------------------------- utilities
def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * x)


def lerp(a, b, t):
    return a + (b - a) * t


def cam_matrix(cx, cy, z):
    """Affine src->out for a camera centred on (cx, cy) in source px with zoom z."""
    hw, hh = W / 2 / z, H / 2 / z
    cx = min(max(cx, hw), SRC_W - hw)
    cy = min(max(cy, hh), SRC_H - hh)
    return np.array([[z, 0, W / 2 - z * cx], [0, z, H / 2 - z * cy]], np.float64)


def apply(M, p):
    return (M[0, 0] * p[0] + M[0, 1] * p[1] + M[0, 2], M[1, 0] * p[0] + M[1, 1] * p[1] + M[1, 2])


def scale_about(M_bg, anchor_src, k, extra=(0.0, 0.0)):
    """Foreground matrix: same as M_bg at the anchor, but zoomed by k around it."""
    ax, ay = apply(M_bg, anchor_src)
    ax += extra[0]
    ay += extra[1]
    z = M_bg[0, 0] * k
    return np.array([[z, 0, ax - z * anchor_src[0]], [0, z, ay - z * anchor_src[1]]], np.float64)


def warp(img, M, interp=cv2.INTER_LINEAR):
    return cv2.warpAffine(img, M, (W, H), flags=interp, borderMode=cv2.BORDER_REFLECT)


def load(name):
    img = cv2.imread(f"{ASSETS}/{name}.png", cv2.IMREAD_COLOR).astype(np.float32) / 255.0
    plate = cv2.imread(f"{ASSETS}/{name}_plate.png", cv2.IMREAD_COLOR).astype(np.float32) / 255.0
    mask = cv2.imread(f"{ASSETS}/{name}_mask.png", cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    return img, plate, mask


DIVE = load("dive")
CITY = load("city")

# Output-res coordinate grids (shared)
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
HY, HX = np.mgrid[0:H // 2, 0:W // 2].astype(np.float32)

# ------------------------------------------------------------- god rays
RAY_NOISE = rng.standard_normal(4096).astype(np.float32)
RAY_NOISE = cv2.GaussianBlur(RAY_NOISE.reshape(1, -1), (0, 0), 6).ravel()
RAY_NOISE = (RAY_NOISE - RAY_NOISE.min()) / (RAY_NOISE.max() - RAY_NOISE.min())


def god_rays(sun_out, t, strength, reach):
    sx, sy = sun_out[0] / 2, sun_out[1] / 2
    dx, dy = HX - sx, HY - sy
    ang = np.arctan2(dx, dy)  # 0 = straight down
    r = np.sqrt(dx * dx + dy * dy)
    idx = (ang * 900 + t * 18) % 4096
    i0 = idx.astype(np.int32)
    f = idx - i0
    n = RAY_NOISE[i0] * (1 - f) + RAY_NOISE[(i0 + 1) % 4096] * f
    idx2 = (ang * 2300 - t * 31) % 4096
    n2 = RAY_NOISE[idx2.astype(np.int32)]
    shafts = np.clip(n * 0.65 + n2 * 0.5 - 0.42, 0, 1) ** 2.2
    fall = np.exp(-r / (reach / 2)) * np.clip(np.cos(ang), 0, 1) ** 2
    rays = shafts * fall * strength
    rays = cv2.resize(rays, (W, H), interpolation=cv2.INTER_LINEAR)
    return rays[..., None] * np.array([1.0, 0.97, 0.80], np.float32)  # BGR: cool white-cyan


# ------------------------------------------------------------- caustics
def caustics(t, scale=1.0):
    x, y = HX * scale / 60.0, HY * scale / 60.0
    a = np.sin(x * 1.3 + np.sin(y * 0.9 + t * 1.1) * 1.6 + t * 0.9)
    b = np.sin(y * 1.1 + np.sin(x * 0.7 - t * 0.8) * 1.8 - t * 0.7)
    c = np.sin((x + y) * 0.8 + np.sin(x * 0.5 + t) + t * 1.3)
    v = (a + b + c) / 3.0
    ridges = np.exp(-(v * v) * 22.0)
    return cv2.resize(ridges, (W, H))[..., None]


# ------------------------------------------------------------- particles (3D)
NP = 1400
P = np.stack([rng.uniform(-9, 9, NP), rng.uniform(-6, 6, NP), rng.uniform(0.6, 14, NP)], 1).astype(np.float32)
P_SIZE = rng.uniform(0.6, 1.6, NP).astype(np.float32)
P_BRIGHT = rng.uniform(0.25, 1.0, NP).astype(np.float32)
P_PHASE = rng.uniform(0, 6.28, NP).astype(np.float32)
BOX = np.array([18, 12, 13.4], np.float32)


def particles(cam, t, focus=3.0, gain=1.0):
    """cam = world (x, y, z) of camera. Returns additive BGR layer."""
    rel = P - np.asarray(cam, np.float32)
    rel[:, 0] += 0.25 * np.sin(t * 0.6 + P_PHASE)
    rel[:, 1] += 0.18 * np.sin(t * 0.8 + P_PHASE * 1.7) - 0.05 * t  # gentle drift
    lo = np.array([-9, -6, 0.6], np.float32)
    rel = (rel - lo) % BOX + lo
    f = 1150.0
    u = W / 2 + f * rel[:, 0] / rel[:, 2]
    v = H / 2 + f * rel[:, 1] / rel[:, 2]
    rad = P_SIZE * 7.0 / rel[:, 2]
    defocus = np.abs(1 / rel[:, 2] - 1 / focus) * 9
    layers = [np.zeros((H // 2, W // 2), np.float32) for _ in range(3)]
    sig = [0.6, 2.0, 5.5]
    for i in range(NP):
        if not (-40 < u[i] < W + 40 and -40 < v[i] < H + 40):
            continue
        d = defocus[i]
        k = 0 if d < 0.6 else (1 if d < 2.0 else 2)
        r = max(0.6, rad[i] / 2 + d * 0.9)
        a = P_BRIGHT[i] * (0.9 if k == 0 else (0.55 if k == 1 else 0.28))
        cv2.circle(layers[k], (int(u[i] / 2 * 4), int(v[i] / 2 * 4)), int(r * 4), float(a), -1, cv2.LINE_AA, 2)
    out = np.zeros((H // 2, W // 2), np.float32)
    for k in range(3):
        out += cv2.GaussianBlur(layers[k], (0, 0), sig[k])
    out = cv2.resize(out, (W, H)) * gain
    return out[..., None] * np.array([0.95, 0.92, 0.78], np.float32)


# ------------------------------------------------------------- bubbles
class Bubbles:
    def __init__(self, seed, bursts):
        r = np.random.default_rng(seed)
        self.items = []
        for t0, n in bursts:
            for j in range(n):
                self.items.append(dict(
                    t0=t0 + j * r.uniform(0.03, 0.09),
                    r=r.uniform(2.5, 6.5) if j % 5 else r.uniform(7, 11),
                    vx=r.uniform(-30, 45), vy=r.uniform(-240, -130),
                    ph=r.uniform(0, 6.28), wob=r.uniform(3, 9)))

    def draw(self, img, t, M, mouth_src):
        """Bubbles live in layer-source coordinates and rise; drawn in output space."""
        ov = np.zeros((H, W), np.float32)
        hi = np.zeros((H, W), np.float32)
        for b in self.items:
            age = t - b["t0"]
            if age < 0 or age > 3.5:
                continue
            sx = mouth_src[0] + b["vx"] * age + b["wob"] * math.sin(age * 9 + b["ph"])
            sy = mouth_src[1] + b["vy"] * age - 40 * age * age
            x, y = apply(M, (sx, sy))
            rr = b["r"] * M[0, 0] * (1 + 0.25 * age)
            if not (-30 < x < W + 30 and -30 < y < H + 30):
                continue
            c = (int(x * 4), int(y * 4))
            cv2.circle(ov, c, int(rr * 4), 0.30, max(2, int(rr * 0.8)), cv2.LINE_AA, 2)
            cv2.circle(ov, c, int(rr * 4), 0.05, -1, cv2.LINE_AA, 2)
            cv2.circle(hi, (int((x - rr * 0.35) * 4), int((y - rr * 0.4) * 4)), int(max(0.6, rr * 0.22) * 4), 0.75, -1, cv2.LINE_AA, 2)
        ov = cv2.GaussianBlur(ov, (0, 0), 0.7)
        hi = cv2.GaussianBlur(hi, (0, 0), 1.0)
        tint = np.array([1.0, 0.98, 0.9], np.float32)
        return img + ov[..., None] * tint * 0.8 + hi[..., None] * 0.8


# ------------------------------------------------------------- traffic
def polyline(pts):
    pts = np.array(pts, np.float64)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    return pts, cum


def along(pl, s):
    pts, cum = pl
    d = s * cum[-1]
    i = int(np.clip(np.searchsorted(cum, d) - 1, 0, len(pts) - 2))
    f = (d - cum[i]) / max(cum[i + 1] - cum[i], 1e-6)
    p = pts[i] + (pts[i + 1] - pts[i]) * f
    tan = (pts[i + 1] - pts[i]) / max(np.linalg.norm(pts[i + 1] - pts[i]), 1e-6)
    return p, np.array([-tan[1], tan[0]])


# Highway centreline (full-res source px), near (bottom-left) -> far (right)
HIGHWAY = polyline([(1200, 1494), (1320, 1360), (1440, 1266), (1560, 1214), (1680, 1180),
                    (1840, 1146), (2000, 1120), (2160, 1104), (2280, 1086)])
BRIDGE = polyline([(220, 974), (900, 984), (1160, 986), (1600, 1014)])


def make_cars(n, lane, speed, seed):
    r = np.random.default_rng(seed)
    return [dict(s0=r.uniform(0, 1), v=speed * r.uniform(0.8, 1.2), lane=lane + r.uniform(-0.05, 0.05)) for _ in range(n)]


CARS = make_cars(12, -0.22, 0.055, 1) + make_cars(13, 0.22, -0.06, 2)
BRIDGE_CARS = make_cars(10, -0.5, 0.035, 3) + make_cars(10, 0.5, -0.04, 4)


def traffic(M, t):
    core = np.zeros((H, W, 3), np.float32)
    for cars, pl, wfar, wnear, sz in ((CARS, HIGHWAY, 34, 150, (1.3, 4.2)), (BRIDGE_CARS, BRIDGE, 10, 10, (1.2, 1.2))):
        for c in cars:
            s = (c["s0"] + c["v"] * t) % 1.0
            p, nrm = along(pl, s)
            width = lerp(wnear, wfar, s)
            p = p + nrm * width * c["lane"]
            x, y = apply(M, p)
            if not (0 <= x < W and 0 <= y < H):
                continue
            rad = lerp(sz[1], sz[0], s) * M[0, 0]
            toward = c["v"] < 0  # driving toward camera -> headlights
            col = (0.80, 0.92, 1.0) if toward else (0.22, 0.25, 0.95)
            sep = rad * 1.5
            for sgn in (-1, 1):
                q = (int((x + nrm[0] * sep * sgn) * 4), int((y + nrm[1] * sep * sgn * 0.3) * 4))
                cv2.circle(core, q, max(2, int(rad * 0.8 * 4)), col, -1, cv2.LINE_AA, 2)
    glow = cv2.GaussianBlur(core, (0, 0), 5)
    return core * 0.9 + glow * 1.4


# ------------------------------------------------------------- leg kick warp (dive)
def kick_warp(img, mask, t):
    """Flutter-kick: sway the legs (top-right of the dive frame) in source space."""
    x0, x1, y0, y1 = 1600, 2300, 0, 720
    sub_y, sub_x = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    w = np.clip((560 - sub_y) / 560.0, 0, 1) ** 1.6  # 1 at feet, 0 at hips
    left_leg = sub_x < 2000
    phase = np.where(left_leg, 0.0, math.pi)
    dx = 22 * w * np.sin(t * 5.2 + phase - sub_y / 260.0)
    dy = 6 * w * np.cos(t * 5.2 + phase)
    mx, my = (sub_x - dx).astype(np.float32), (sub_y - dy).astype(np.float32)
    img = img.copy()
    mask = mask.copy()
    img[y0:y1, x0:x1] = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    mask[y0:y1, x0:x1] = cv2.remap(mask, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return img, mask


# ------------------------------------------------------------- shots
DIVE_BUBBLES = Bubbles(11, [(0.05, 14), (1.25, 11), (2.45, 15), (3.4, 8)])
CITY_BUBBLES = Bubbles(12, [(3.2, 10), (4.7, 12), (6.2, 10), (7.8, 9)])
T_A_END = 3.9
T_B_START = 3.4


def shot_dive(t):
    u = ease_io(t / T_A_END)
    cx, cy, z = lerp(1376, 1300, u), lerp(740, 840, u), lerp(0.745, 0.80, u)
    # accelerate the tilt-down at the end into the transition
    tail = smooth((t - 3.0) / 0.9)
    cy += tail * 90
    Mb = cam_matrix(cx, cy, z)
    img, plate, mask = DIVE
    img_k, mask_k = kick_warp(img, mask, t)
    anchor = (1450, 640)
    k = 1.0 + 0.055 * u + 0.02 * tail
    bob = (4 * math.sin(t * 1.3), 3 * math.sin(t * 1.9 + 1))
    Mf = scale_about(Mb, anchor, k, bob)
    bg = warp(plate, Mb)
    bg += god_rays(apply(Mb, (1160, -120)), t, 0.20, 1700)
    fg = warp(img_k, Mf)
    a = warp(mask_k, Mf)[..., None]
    # caustics dancing on the swimmer (stronger on top-lit parts)
    lum = fg.mean(axis=2, keepdims=True)
    fg = fg + caustics(t) * 0.22 * np.clip(lum * 2.2, 0.2, 1.0) * np.array([1.0, 1.0, 0.92], np.float32)
    out = bg * (1 - a) + fg * a
    out = DIVE_BUBBLES.draw(out, t, Mf, (1082, 800))
    out += god_rays(apply(Mb, (1160, -120)), t + 3, 0.07, 1500)
    # camera descends -> world moves up past us
    out += particles((0.0, 2.2 * t + 1.6 * tail * tail, 0.0), t, focus=2.5, gain=0.75)
    return out


def shot_city(t):
    tb = t - T_B_START
    u = ease_io(tb / (DUR - T_B_START))
    lin = tb / (DUR - T_B_START)
    z = lerp(0.73, 1.18, u)
    cx = lerp(1400, 1900, u)
    cy = lerp(760, 1020, u)
    Mb = cam_matrix(cx, cy, z)
    img, plate, mask = CITY
    anchor = (880, 1080)
    k = 1.0 + 0.16 * u  # swimmer is nearer: grows faster than the city
    grow_shift = -0.8 * (k - 1) * 300 * Mb[0, 0]
    bob = (5 * math.sin(tb * 1.2), 4 * math.sin(tb * 1.7 + 0.5))
    Mf = scale_about(Mb, anchor, k, (grow_shift + bob[0] - 120 * u * u, bob[1] + 60 * u * u))
    bg = warp(plate, Mb)
    bg += traffic(Mb, t)
    bg += god_rays(apply(Mb, (1500, -380)), t, 0.16, 2100)
    fg = warp(img, Mf)
    a = warp(mask, Mf)[..., None]
    out = bg * (1 - a) + fg * a
    out = CITY_BUBBLES.draw(out, t, Mf, (1098, 690))
    out += god_rays(apply(Mb, (1500, -380)), t + 5, 0.05, 1800)
    # camera glides forward into the city
    out += particles((1.4 * lin, 0.6 * lin, 5.0 * u + 0.25 * tb), t, focus=3.5, gain=0.6)
    return out


DEEP = np.array([0.32, 0.17, 0.03], np.float32)  # deep ocean blue (BGR)


def frame(i):
    t = i / FPS
    if t < T_B_START:
        out = shot_dive(t)
    elif t >= T_A_END:
        out = shot_city(t)
    else:
        m = smooth((t - T_B_START) / (T_A_END - T_B_START))
        a, b = shot_dive(t), shot_city(t)
        # A sinks into deep blue, B emerges from it
        deep = np.broadcast_to(DEEP, a.shape)
        a = lerp(a, deep, smooth(m * 1.6))
        b = lerp(deep, b, smooth(m * 1.4 - 0.4))
        out = lerp(a, b, m)
    # haze lifting off the city just after the cut
    if t >= T_B_START:
        fog = 1 - smooth((t - T_A_END) / 1.2)
        out = lerp(out, np.broadcast_to(DEEP, out.shape), 0.35 * fog)
    return finish(out, t)


# ------------------------------------------------------------- finishing
VIGNETTE = None


def finish(img, t):
    global VIGNETTE
    if VIGNETTE is None:
        r = np.sqrt(((XX - W / 2) / (W / 2)) ** 2 + ((YY - H / 2) / (H / 2)) ** 2)
        VIGNETTE = (1 - 0.38 * np.clip(r - 0.35, 0, 1) ** 1.5)[..., None].astype(np.float32)
    img = np.clip(img, 0, 4)
    # water refraction shimmer
    dx = 1.4 * np.sin(YY / 41.0 + t * 1.9) + 0.9 * np.sin(XX / 67.0 - t * 1.3 + YY / 90.0)
    dy = 1.1 * np.sin(XX / 53.0 + t * 1.5) + 0.7 * np.sin(YY / 37.0 - t * 2.1)
    img = cv2.remap(img, XX + dx, YY + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    # bloom
    lum = img.max(axis=2, keepdims=True)
    bright = img * np.clip((lum - 0.62) / 0.5, 0, 1)
    small = cv2.resize(bright, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    bloom = cv2.GaussianBlur(small, (0, 0), 6) * 0.6 + cv2.GaussianBlur(small, (0, 0), 18) * 0.5
    img = img + cv2.resize(bloom, (W, H)) * 0.55
    # grade: gentle filmic curve, cool shadows, cyan mids
    img = img / (1 + img * 0.28) * 1.18
    img = img * np.array([1.03, 1.0, 0.94], np.float32) + np.array([0.012, 0.006, 0.0], np.float32)
    img = np.clip(img, 0, 1)
    img = img * img * (3 - 2 * img) * 0.35 + img * 0.65  # mild S-curve
    img *= VIGNETTE
    # subtle chromatic aberration at the edges
    b, g, r = cv2.split(img)
    s = 1.0015
    Mr = np.array([[s, 0, W / 2 * (1 - s)], [0, s, H / 2 * (1 - s)]], np.float32)
    Mbb = np.array([[1 / s, 0, W / 2 * (1 - 1 / s)], [0, 1 / s, H / 2 * (1 - 1 / s)]], np.float32)
    r = cv2.warpAffine(r, Mr, (W, H), borderMode=cv2.BORDER_REFLECT)
    b = cv2.warpAffine(b, Mbb, (W, H), borderMode=cv2.BORDER_REFLECT)
    img = cv2.merge([b, g, r])
    # fade in / fade out
    img *= smooth(t / 0.45) * (1 - smooth((t - (DUR - 0.6)) / 0.6))
    # film grain
    grain = np.random.default_rng(int(t * 1000)).standard_normal((H // 2, W // 2)).astype(np.float32)
    grain = cv2.resize(grain, (W, H))[..., None] * 0.018
    img = img + grain * (0.4 + img)
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def main():
    if PREVIEW:
        for t in (0.6, 2.0, 3.3, 3.65, 4.4, 6.0, 8.0, 9.3):
            cv2.imwrite(f"still_{t:04.1f}.jpg", frame(int(t * FPS)), [cv2.IMWRITE_JPEG_QUALITY, 90])
            print("still", t, flush=True)
        return
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-tune", "grain", OUT], stdin=subprocess.PIPE)
    for i in range(NF):
        ff.stdin.write(frame(i).tobytes())
        if i % 24 == 0:
            print(f"frame {i}/{NF}", flush=True)
    ff.stdin.close()
    ff.wait()


if __name__ == "__main__":
    main()
