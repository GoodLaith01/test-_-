"""Bake the character animation into video layers for Remotion.

Outputs (in public/, 2x the 864x1536 source = 1728x3072 canvas units):
  street_anim.mp4  opaque street plate: pedestrians walking (slow motion), swimmers swimming,
                   sharks gliding, over a LaMa-inpainted clean plate
  dive_man.webm    the diver with alpha: flutter kick, arm strokes, hair moving in the water
  city_man.webm    the man over the city with alpha: breathing and a slight head turn

Usage: PPHUMANSEG=<pphumanseg.onnx> python3 scripts/animate_layers.py <lama.onnx> [street|dive|city ...]
"""
import math
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, "scripts")
from actors import SKY_ACTORS, STREET_ACTORS, segment  # noqa: E402
from lama import inpaint  # noqa: E402

LAMA = sys.argv[1]
FPS = 24
UP = 2
VP = np.array([530.0, 1100.0])  # vanishing point of the avenue (source units)


def upscale(img):
    big = cv2.resize(img, None, fx=UP, fy=UP, interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(big, (0, 0), 1.2)
    return cv2.addWeighted(big, 1.35, blur, -0.35, 0)


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def ffmpeg_writer(path, w, h, alpha):
    if alpha:
        args = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "20", "-row-mt", "1",
                "-deadline", "good", "-cpu-used", "4"]
        pix = "bgra"
    else:
        args = ["-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p"]
        pix = "bgr24"
    return subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", pix,
                             "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", *args, path], stdin=subprocess.PIPE)


# ------------------------------------------------------------------ sprites
class Sprite:
    """An actor cut out of the 2x frame with a padded local canvas (BGRA float)."""

    def __init__(self, big, mask_big, actor, pad=0.45):
        self.a = actor
        x0, y0, x1, y1 = [v * UP for v in actor["box"]]
        pw, ph = int((x1 - x0) * pad), int((y1 - y0) * pad)
        X0, Y0 = max(0, x0 - pw), max(0, y0 - ph)
        X1, Y1 = min(big.shape[1], x1 + pw), min(big.shape[0], y1 + ph)
        self.origin = np.array([X0, Y0], np.float64)
        rgb = big[Y0:Y1, X0:X1].astype(np.float32) / 255
        al = mask_big[Y0:Y1, X0:X1].astype(np.float32)[..., None] / 255
        self.rgba = np.concatenate([rgb * al, al], axis=2)  # premultiplied
        self.h, self.w = al.shape[:2]
        self.box = np.array([x0 - X0, y0 - Y0, x1 - X0, y1 - Y0], np.float64)  # actor box in local coords
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        self.xx, self.yy = xx, yy

    def warp(self, dx, dy):
        """Inverse-map warp: output(x, y) = input(x - dx, y - dy)."""
        return cv2.remap(self.rgba, self.xx - dx.astype(np.float32), self.yy - dy.astype(np.float32),
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def paste(dst, rgba, M):
    """Alpha-composite premultiplied local rgba into dst (float BGR) through affine M (local -> dst)."""
    h, w = dst.shape[:2]
    corners = np.array([[0, 0, 1], [rgba.shape[1], 0, 1], [0, rgba.shape[0], 1], [rgba.shape[1], rgba.shape[0], 1]]) @ M.T
    X0, Y0 = np.floor(corners.min(0)).astype(int)
    X1, Y1 = np.ceil(corners.max(0)).astype(int)
    X0, Y0, X1, Y1 = max(0, X0), max(0, Y0), min(w, X1), min(h, Y1)
    if X1 <= X0 or Y1 <= Y0:
        return
    Mr = M.copy()
    Mr[:, 2] -= [X0, Y0]
    roi = cv2.warpAffine(rgba, Mr, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    a = roi[..., 3:4]
    dst[Y0:Y1, X0:X1] = dst[Y0:Y1, X0:X1] * (1 - a) + roi[..., :3]


def walker_frame(sp, t):
    """Return (warped rgba, affine local->2x frame) for a pedestrian at time t (s)."""
    a = sp.a
    bx0, by0, bx1, by1 = sp.box
    hs = by1 - by0
    xc = (bx0 + bx1) / 2
    hip = by0 + 0.53 * hs
    feet_local = np.array([xc, by1])
    w_leg = smoothstep((sp.yy - hip) / (by1 - hip)).astype(np.float32)
    if a["kind"] == "side":
        speed = 0.22 * hs  # px/s at 2x (slow motion)
        phi = 2 * math.pi * 0.275 * t
        dx = 0.065 * hs * math.cos(phi) * w_leg * np.sign(sp.xx - xc)
        lift = 0.02 * hs * np.maximum(0, np.sin(phi * 2)) * w_leg
        bob = -0.012 * hs * (1 - math.cos(2 * phi)) / 2
        dy = -lift + bob * (1 - w_leg)
        rgba = sp.warp(dx, dy)
        shift = np.array([a["dir"] * speed * t, 0.0])
        s = 1.0
    else:  # walking away toward the vanishing point
        phi = 2 * math.pi * 0.3 * t
        left = (sp.xx < xc).astype(np.float32)
        dy = -0.04 * hs * w_leg * (left * max(0, math.sin(phi)) + (1 - left) * max(0, -math.sin(phi)))
        dx = 0.008 * hs * math.sin(phi) * (1 - w_leg) + 0 * sp.xx
        dy = dy - 0.008 * hs * abs(math.sin(phi)) * (1 - w_leg)
        rgba = sp.warp(dx, dy)
        k = a.get("k", 0.045)
        s = 1.0 / (1.0 + k * t)
        feet0 = (sp.origin + feet_local) / UP
        feet = VP + (feet0 - VP) * s
        shift = (feet - feet0) * UP
    # affine: scale s about the feet, then shift
    fx, fy = feet_local
    M = np.array([[s, 0, fx - s * fx], [0, s, fy - s * fy]], np.float64)
    M[:, 2] += sp.origin + shift
    return rgba, M


def reflection(rgba, strength=0.22):
    """Wet-road reflection: flipped, blurred, darker, fading with distance."""
    r = rgba[::-1].copy()
    h = r.shape[0]
    fade = np.linspace(1, 0, h, dtype=np.float32)[:, None, None] ** 1.5
    r = cv2.GaussianBlur(r, (0, 0), 3) * fade * strength
    return r


def swimmer_frame(sp, t):
    a = sp.a
    hd = np.array(a["heading"], np.float64)
    hd /= np.linalg.norm(hd)
    perp = np.array([-hd[1], hd[0]])
    bx0, by0, bx1, by1 = sp.box
    c = np.array([(bx0 + bx1) / 2, (by0 + by1) / 2])
    L = max(bx1 - bx0, by1 - by0)
    u = ((sp.xx - c[0]) * hd[0] + (sp.yy - c[1]) * hd[1]) / L + 0.5  # 0 = tail/feet, 1 = head
    if a["kind"] == "swim":
        amp, freq, k, speed = 0.06 * L, 1.1, 7.0, 0.32 * L
        tail = np.clip(1 - u / 0.65, 0, 1) ** 2
    else:  # shark glide
        amp, freq, k, speed = 0.05 * L, 0.55, 5.0, 0.22 * L
        tail = np.clip(1 - u / 0.5, 0, 1) ** 2
    d = amp * np.sin(2 * math.pi * freq * t - k * u) * tail
    rgba = sp.warp(d * perp[0], d * perp[1])
    shift = hd * speed * t + perp * 0.02 * L * math.sin(2 * math.pi * 0.3 * t)
    M = np.array([[1, 0, 0], [0, 1, 0]], np.float64)
    M[:, 2] += sp.origin + shift
    return rgba, M


# ------------------------------------------------------------------ street layer
def bake_street(n_frames):
    img = cv2.imread("figma-src/street.png")
    actors = SKY_ACTORS + STREET_ACTORS
    masks = {a["name"]: segment(img, a) for a in actors}
    allm = np.zeros(img.shape[:2], np.uint8)
    for m in masks.values():
        allm |= (m > 40).astype(np.uint8) * 255
    clean = inpaint(LAMA, img, cv2.dilate(allm, np.ones((13, 13), np.uint8)))
    big = upscale(img)
    plate = upscale(clean).astype(np.float32) / 255
    sprites = []
    for a in actors:
        mb = cv2.resize(masks[a["name"]], None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
        mb = cv2.GaussianBlur(mb, (0, 0), 0.9)
        sprites.append(Sprite(big, mb, a))
    # draw order: sky first, then pedestrians far -> near (by feet y)
    order = [s for s in sprites if s.a in SKY_ACTORS] + sorted(
        [s for s in sprites if s.a in STREET_ACTORS], key=lambda s: s.a["box"][3])
    H, W = plate.shape[:2]
    ff = ffmpeg_writer("public/street_anim.mp4", W, H, alpha=False)
    for i in range(n_frames):
        t = i / FPS
        frame = plate.copy()
        for sp in order:
            if sp.a["kind"] in ("swim", "glide"):
                rgba, M = swimmer_frame(sp, t)
                paste(frame, rgba, M)
            else:
                rgba, M = walker_frame(sp, t)
                # wet-road reflection, mirrored about the feet line
                paste(frame, reflection(rgba), _flip_affine(M, rgba.shape[0], sp.box[3]))
                paste(frame, rgba, M)
        ff.stdin.write((np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
        if i % 24 == 0:
            print("street", i, flush=True)
    ff.stdin.close()
    ff.wait()


def _flip_affine(M, h, fy):
    """Affine for the flipped sprite (rgba[::-1]) so its top edge sits on the feet line, mirrored."""
    # flipped local y' = h-1-y ; mirrored about feet line fy (local): y_m = 2*fy - y = 2*fy - (h-1-y')
    F = np.array([[1, 0, 0], [0, 1, 2 * fy - (h - 1)], [0, 0, 1]], np.float64)
    M3 = np.vstack([M, [0, 0, 1]])
    return (M3 @ F)[:2]


# ------------------------------------------------------------------ swimmer layers
def bake_man(name, box, n_frames, anim):
    img = cv2.imread(f"figma-src/{name}.png")
    big = upscale(img)
    # reuse the cut-out made by prep_figma.py (full-canvas alpha, 2x)
    man = cv2.imread(f"public/{name}_man.png", cv2.IMREAD_UNCHANGED)
    x0, y0 = int(box[0] * UP), int(box[1] * UP)
    alpha = np.zeros(big.shape[:2], np.float32)
    alpha[y0:y0 + man.shape[0], x0:x0 + man.shape[1]] = man[..., 3] / 255.0
    pad = 60
    X0, Y0 = max(0, x0 - pad), max(0, y0 - pad)
    X1, Y1 = min(big.shape[1], x0 + man.shape[1] + pad), min(big.shape[0], y0 + man.shape[0] + pad)
    rgb = big[Y0:Y1, X0:X1].astype(np.float32) / 255
    al = alpha[Y0:Y1, X0:X1][..., None]
    rgba = np.concatenate([rgb * al, al], axis=2)
    h, w = al.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    sx = (xx + X0) / UP  # source-unit coords of each local pixel
    sy = (yy + Y0) / UP
    ff = ffmpeg_writer(f"public/{name}_man_anim.webm", w, h, alpha=True)
    for i in range(n_frames):
        t = i / FPS
        dxs, dys = anim(sx, sy, t)
        out = cv2.remap(rgba, xx - dxs * UP, yy - dys * UP, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        a = np.clip(out[..., 3:4], 1e-6, 1)
        straight = np.where(out[..., 3:4] > 1e-4, out[..., :3] / a, 0)
        bgra = np.concatenate([straight, out[..., 3:4]], axis=2)
        ff.stdin.write((np.clip(bgra, 0, 1) * 255 + 0.5).astype(np.uint8).tobytes())
    ff.stdin.close()
    ff.wait()
    print(name, "layer", (X0 / UP, Y0 / UP, X1 / UP, Y1 / UP), flush=True)
    return (X0 / UP, Y0 / UP, X1 / UP, Y1 / UP)


def rot_field(sx, sy, pivot, theta, weight):
    """Displacement (dx, dy) rotating points about pivot by theta*weight (radians)."""
    px, py = sx - pivot[0], sy - pivot[1]
    th = theta * weight
    c, s = np.cos(th), np.sin(th)
    return (px * c - py * s) - px, (px * s + py * c) - py


def dive_anim(sx, sy, t):
    # flutter kick: legs at the top of the frame (feet at y=0, hips ~y=300)
    w_leg = np.clip((300 - sy) / 300, 0, 1) ** 1.5
    side = np.where(sx < 425, 0.0, math.pi)
    dx = 9 * w_leg * np.sin(2 * math.pi * 1.3 * t + side - sy / 120)
    dy = 3 * w_leg * np.cos(2 * math.pi * 1.3 * t + side)
    # arm strokes: slow breaststroke sweep around the shoulders
    theta = math.radians(5.5) * math.sin(2 * math.pi * 0.45 * t)
    for pivot, sgn, zone in (((250, 485), 1, sx < 335), ((625, 490), -1, sx > 545)):
        dist = np.hypot(sx - pivot[0], sy - pivot[1])
        w = smoothstep((dist - 50) / 220) * zone * (sy > 470)
        w = cv2.GaussianBlur(w.astype(np.float32), (0, 0), 6)
        ax, ay = rot_field(sx, sy, pivot, sgn * theta, w)
        dx = dx + ax
        dy = dy + ay
    # hair drifting in the water
    w_hair = np.clip((400 - sy) / 110, 0, 1) * ((sx > 320) & (sx < 570)) * (sy > 280)
    dx = dx + 3.5 * w_hair * np.sin(2 * math.pi * 0.8 * t + sx / 40)
    dy = dy + 1.5 * w_hair * np.cos(2 * math.pi * 0.6 * t + sx / 55)
    return dx.astype(np.float32), dy.astype(np.float32)


def city_anim(sx, sy, t):
    # breathing: shoulders and head rise and fall, bottom of frame fixed
    breath = math.sin(2 * math.pi * 0.25 * t)
    w = smoothstep((1536 - sy) / 520)
    dy = -2.6 * breath * w
    # head turns slightly to look around the city
    w_head = smoothstep((1110 - sy) / 120)
    dx = 3.0 * math.sin(2 * math.pi * 0.11 * t) * w_head + 0.6 * breath * w
    # hair drifting
    w_hair = smoothstep((940 - sy) / 40)
    dx = dx + 2.0 * w_hair * np.sin(2 * math.pi * 0.7 * t + sx / 30)
    return dx.astype(np.float32), dy.astype(np.float32)


if __name__ == "__main__":
    what = sys.argv[2:] or ["street", "dive", "city"]
    if "dive" in what:
        bake_man("dive", (137, 0), 116, dive_anim)
    if "city" in what:
        bake_man("city", (0, 888), 150, city_anim)
    if "street" in what:
        bake_street(150)
