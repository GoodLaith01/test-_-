"""Skeleton-driven walking for people cut out of a still image.

Joints come from MediaPipe Pose (OpenCV Zoo ONNX). Every pixel of a person is
skinned to the nearest bones (2D linear-blend skinning, done as per-bone affine
warps of weighted sprites). A gait model then animates the skeleton with
planted feet: the stance foot stays fixed on the ground while the hips move,
the swing foot lifts and travels forward, knees are solved with 2-bone IK
(side view) or foreshorten (walking away), the body bobs twice per cycle and
the arms swing against the legs. People walking away shrink with perspective.

All image coordinates here are in the 2x canvas (1728x3072) unless noted.
"""
import math
import os

import cv2
import numpy as np

UP = 2
# BlazePose landmark indices
IDX = dict(Ls=11, Rs=12, Le=13, Re=14, Lw=15, Rw=16, Lh=23, Rh=24, Lk=25, Rk=26, La=27, Ra=28, Lhe=29, Rhe=30, Lt=31, Rt=32)

_POSE = None


def _pose_session():
    global _POSE
    if _POSE is None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        _POSE = ort.InferenceSession(os.environ["MPPOSE"], opts, providers=["CPUExecutionProvider"])
    return _POSE


def detect_pose(img1x, box):
    """Joint positions (2x canvas coords) and depth z for one person inside `box` (1x coords)."""
    x0, y0, x1, y1 = box
    cx, cy, side = (x0 + x1) / 2, (y0 + y1) / 2, (y1 - y0) * 1.25
    big = cv2.resize(img1x, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    sz = int(side * 4)
    X0, Y0 = int((cx - side / 2) * 4), int((cy - side / 2) * 4)
    pad = cv2.copyMakeBorder(big, sz, sz, sz, sz, cv2.BORDER_REPLICATE)
    crop = pad[Y0 + sz:Y0 + 2 * sz, X0 + sz:X0 + 2 * sz]
    inp = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_AREA)[:, :, ::-1].astype(np.float32) / 255
    lm = _pose_session().run(None, {"input_1": inp[None]})[0][0].reshape(39, 5)
    j, z = {}, {}
    for k, i in IDX.items():
        px = X0 / 4 + lm[i, 0] / 256 * sz / 4
        py = Y0 / 4 + lm[i, 1] / 256 * sz / 4
        j[k] = np.array([px * UP, py * UP], np.float64)
        z[k] = float(lm[i, 2])
    return j, z


# ------------------------------------------------------------------ geometry helpers
def seg_dist(px, py, a, b):
    ab = b - a
    t = np.clip(((px - a[0]) * ab[0] + (py - a[1]) * ab[1]) / max(ab @ ab, 1e-6), 0, 1)
    return np.hypot(px - (a[0] + t * ab[0]), py - (a[1] + t * ab[1]))


def bone_affine(p0, p1, q0, q1, perp_scale=1.0):
    """Affine mapping segment p0->p1 onto q0->q1: rotate, stretch along the bone, scale across it."""
    u = p1 - p0
    v = q1 - q0
    lu, lv = max(np.linalg.norm(u), 1e-6), max(np.linalg.norm(v), 1e-6)
    eu, ev = u / lu, v / lv
    nu, nv = np.array([-eu[1], eu[0]]), np.array([-ev[1], ev[0]])
    # x -> q0 + ev * (eu.(x-p0)) * (lv/lu) + nv * (nu.(x-p0)) * perp_scale
    A = np.outer(ev, eu) * (lv / lu) + np.outer(nv, nu) * perp_scale
    b = q0 - A @ p0
    return np.hstack([A, b[:, None]])


def ik_knee(hip, ankle, l1, l2, forward):
    """2-bone IK in the image plane; the knee bends toward `forward` (unit x direction sign)."""
    d = ankle - hip
    dist = np.linalg.norm(d)
    dist_c = min(dist, (l1 + l2) * 0.999)
    a = (l1 * l1 + dist_c * dist_c - l2 * l2) / (2 * dist_c)
    h = math.sqrt(max(l1 * l1 - a * a, 0))
    e = d / max(dist, 1e-6)
    base = hip + e * a
    n = np.array([-e[1], e[0]])
    k1, k2 = base + n * h, base - n * h
    return k1 if (k1[0] - base[0]) * forward >= (k2[0] - base[0]) * forward else k2


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ------------------------------------------------------------------ walker
class Walker:
    """One person: skinned sprite + gait model."""

    STANCE = 0.6

    def __init__(self, big, alpha, joints, z, cfg, vp):
        self.cfg = cfg
        self.j = joints
        self.vp = np.asarray(vp, np.float64) * UP
        self.kind = cfg["kind"]
        self.dir = cfg.get("dir", 0)
        j = joints
        self.mid_hip = (j["Lh"] + j["Rh"]) / 2
        self.mid_sh = (j["Ls"] + j["Rs"]) / 2
        head_top = self.mid_sh + (self.mid_sh - self.mid_hip) * 0.62
        ground = max(j["La"][1], j["Ra"][1], j["Lt"][1], j["Rt"][1])
        self.h = ground - head_top[1]
        h = self.h
        # near/far side from pose depth (smaller z = closer to camera)
        zl = z["Lh"] + z["Lk"] + z["La"]
        zr = z["Rh"] + z["Rk"] + z["Ra"]
        self.near = "L" if zl < zr else "R"
        # which foot is in front at rest
        if self.kind == "side":
            front = "L" if j["La"][0] * self.dir > j["Ra"][0] * self.dir else "R"
            step = abs(j["La"][0] - j["Ra"][0])
        else:
            front = "L" if j["La"][1] < j["Ra"][1] else "R"
            step = 0.38 * h
        self.phase0 = {front: 0.0, ("R" if front == "L" else "L"): 0.5}
        self.stride = max(2 * step, 0.55 * h)  # cycle length (two steps)
        self.freq = cfg.get("freq", 0.82)  # gait cycles per second
        self.speed = self.stride * self.freq
        self.len = {s: (np.linalg.norm(j[s + "h"] - j[s + "k"]), np.linalg.norm(j[s + "k"] - j[s + "a"])) for s in "LR"}
        self.hold = set(cfg.get("hold", []))

        # bones: name -> (joint a, joint b, group)
        def ext(a, b, f):
            return b + (b - a) * f

        self.rest_pts = dict(j)
        self.rest_pts["hip"] = self.mid_hip
        self.rest_pts["neck"] = self.mid_sh
        self.rest_pts["head"] = head_top
        for s in "LR":
            self.rest_pts[s + "hand"] = ext(j[s + "e"], j[s + "w"], 0.35)
            self.rest_pts[s + "toe"] = ext(j[s + "he"], j[s + "t"], 0.15)
        self.skirt = cfg.get("skirt", False)
        self.rest_pts["knees"] = (j["Lk"] + j["Rk"]) / 2
        self.bones = {"torso": ("hip", "head", "body")}
        if self.skirt:  # a dress/skirt hangs from the hips and follows the knees
            self.bones["skirt"] = ("hip", "knees", "body")
        for s in "LR":
            grp = "near" if s == self.near else "far"
            if not self.skirt:
                self.bones[s + "thigh"] = (s + "h", s + "k", grp)
            self.bones[s + "shin"] = (s + "k", s + "a", grp)
            self.bones[s + "foot"] = (s + "he", s + "toe", grp)
            self.bones[s + "upper"] = (s + "s", s + "e", grp + "arm")
            self.bones[s + "fore"] = (s + "e", s + "hand", grp + "arm")

        # sprite crop around the person
        xs = [p[0] for p in self.rest_pts.values()]
        ys = [p[1] for p in self.rest_pts.values()]
        pad = 0.35 * h
        X0 = int(max(0, min(xs) - pad))
        Y0 = int(max(0, min(ys) - pad))
        X1 = int(min(big.shape[1], max(xs) + pad))
        Y1 = int(min(big.shape[0], max(ys) + 0.1 * h))
        self.O = np.array([X0, Y0], np.float64)
        rgb = big[Y0:Y1, X0:X1].astype(np.float32) / 255
        al = alpha[Y0:Y1, X0:X1].astype(np.float32) / 255
        hh, ww = al.shape
        yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        px, py = xx + X0, yy + Y0
        d = {b: seg_dist(px, py, self.rest_pts[a], self.rest_pts[c]) for b, (a, c, _) in self.bones.items()}
        # torso is wide: measure it to the torso quad instead of the spine
        quad = np.array([j["Ls"], j["Rs"], j["Rh"], j["Lh"]], np.float32)
        cen = quad.mean(0)
        quad = cen + (quad - cen) * np.array([1.25, 1.05], np.float32)
        tq = np.zeros((hh, ww), np.uint8)
        cv2.fillPoly(tq, [np.round(quad - self.O).astype(np.int32)], 1)
        cv2.circle(tq, tuple(np.round((self.mid_sh + head_top) / 2 - self.O).astype(int)), int(0.11 * h), 1, -1)
        d["torso"] = np.where(tq > 0, 0, d["torso"] * 0.6)
        if self.skirt:  # the skirt owns everything between the hips and the hem
            sk = np.zeros((hh, ww), np.uint8)
            hem_y = self.rest_pts["knees"][1] + 0.02 * h
            sq = np.array([j["Lh"] + [-0.09 * h, 0], j["Rh"] + [0.09 * h, 0],
                           [max(j["Lk"][0], j["Rk"][0]) + 0.16 * h, hem_y], [min(j["Lk"][0], j["Rk"][0]) - 0.16 * h, hem_y]])
            cv2.fillPoly(sk, [np.round(sq - self.O).astype(np.int32)], 1)
            d["skirt"] = np.where(sk > 0, 0, d["skirt"] + 0.05 * h)
            d["torso"] = np.where(sk > 0, d["torso"] + 1e3, d["torso"])
        names = list(d.keys())
        lab = np.argmin(np.stack([d[b] for b in names]), axis=0)
        seam = max(2, int(0.006 * h))
        w = {}
        for i, b in enumerate(names):
            hard = (lab == i).astype(np.uint8)
            w[b] = cv2.GaussianBlur(cv2.dilate(hard, np.ones((2 * seam + 1, 2 * seam + 1), np.uint8)).astype(np.float32), (0, 0), seam / 2)
            w[b] = np.minimum(w[b], 1.0)
        # torso layer with the arms painted out, so a swinging arm never reveals a hole in the body
        armw = sum(w[b] for b in w if self.bones[b][2].endswith("arm"))
        arm_px = ((armw > 0.5) & (al > 0.3) & (tq > 0)).astype(np.uint8)
        rgb_t = rgb.copy()
        if arm_px.any():
            u8 = (rgb * 255).astype(np.uint8)
            rgb_t = cv2.inpaint(u8, cv2.dilate(arm_px, np.ones((5, 5), np.uint8)), 7, cv2.INPAINT_TELEA).astype(np.float32) / 255
        self.sprites = {}
        for b in self.bones:
            if b == "torso":
                wt = np.clip(w[b] + armw * tq, 0, 1)
                src = rgb_t
            else:
                wt = w[b]
                src = rgb
            a = (al * wt)[..., None]
            self.sprites[b] = np.concatenate([src * a, a], axis=2).astype(np.float32)

    # -------------------------------------------------------------- gait
    def pose_at(self, t):
        """Animated joint positions (2x canvas), plus per-joint perspective scale."""
        j = self.j
        h = self.h
        phi = self.freq * t
        bob = 0.014 * h * math.sin(2 * math.pi * (phi + self.phase0["L"])) ** 2
        out = {}
        if self.kind == "side":
            fwd = np.array([self.dir, 0.0])
            hip_shift = fwd * self.speed * t + np.array([0, -bob])
            for k in ("Ls", "Rs", "Le", "Re", "Lw", "Rw", "Lh", "Rh", "hip", "neck", "head", "Lhand", "Rhand"):
                out[k] = self.rest_pts[k] + hip_shift
            for s in "LR":
                ps = phi + self.phase0[s]
                n = math.floor(ps)
                psi = ps - n
                a_rest = self.rest_pts[s + "a"]
                # the foot plants where it stands in the still, then one stride further each cycle
                strike_n = a_rest[0] + self.dir * self.stride * n
                if psi < self.STANCE:  # stance: foot fixed on the ground; heel rises before push-off
                    ax = strike_n
                    lift = 0.0
                    heel = 0.035 * h * ease((psi - 0.4) / 0.2)
                    toe_rot = math.radians(28) * ease((psi - 0.42) / 0.18) * self.dir
                else:  # swing: foot lifts, travels one stride forward, lands heel first
                    u = (psi - self.STANCE) / (1 - self.STANCE)
                    ax = strike_n + self.dir * self.stride * ease(u)
                    lift = 0.07 * h * math.sin(math.pi * u)
                    heel = 0.035 * h * (1 - ease(u * 2))
                    toe_rot = (math.radians(28) * (1 - ease(u * 1.6)) - math.radians(12) * ease((u - 0.7) / 0.3)) * self.dir
                ankle = np.array([ax, a_rest[1] - lift - heel])
                hip = self.rest_pts[s + "h"] + hip_shift
                l1, l2 = self.len[s]
                knee = ik_knee(hip, ankle, l1, l2, self.dir)
                out[s + "h"], out[s + "k"], out[s + "a"] = hip, knee, ankle
                # foot: rotate heel->toe about the ankle
                c, si = math.cos(toe_rot), math.sin(toe_rot)
                R = np.array([[c, -si], [si, c]])
                for f in ("he", "toe"):
                    rel = self.rest_pts[s + f] - a_rest
                    out[s + f] = ankle + R @ rel
            scale = {k: 1.0 for k in out}
            scale["Lk"] = scale["Rk"] = 1.0
        else:  # walking away: plan on the ground in "forward" units, then project
            Z0 = self.cfg.get("z0", 7.0) * h
            hip_w = self.speed * t
            sway = 0.012 * h * math.sin(2 * math.pi * (phi + self.phase0["L"]))
            local = {}
            fw = {}
            for k in ("Ls", "Rs", "Le", "Re", "Lw", "Rw", "Lh", "Rh", "hip", "neck", "head", "Lhand", "Rhand"):
                local[k] = self.rest_pts[k] + np.array([sway, -bob])
                fw[k] = hip_w
            for s in "LR":
                ps = phi + self.phase0[s]
                n = math.floor(ps)
                psi = ps - n
                strike_w = self.stride * n  # foot plant on the ground (forward units)
                if psi < self.STANCE:
                    aw = strike_w
                    lift = 0.012 * h * ease((psi - 0.4) / 0.2)
                else:
                    u = (psi - self.STANCE) / (1 - self.STANCE)
                    aw = strike_w + self.stride * ease(u)
                    lift = 0.06 * h * math.sin(math.pi * u)
                a_rest = self.rest_pts[s + "a"]
                local[s + "a"] = a_rest + np.array([0, -lift])
                fw[s + "a"] = aw
                for f in ("he", "toe"):
                    local[s + f] = self.rest_pts[s + f] + np.array([0, -lift])
                    fw[s + f] = fw[s + "a"]
            # project ground offsets (forward = away from camera) with perspective about the vanishing point
            ground_y = max(self.rest_pts["La"][1], self.rest_pts["Ra"][1])
            out, scale = {}, {}
            for k, p in local.items():
                s_k = Z0 / (Z0 + fw[k])
                # anchor each point to the ground below it, then shrink toward the vanishing point
                g = np.array([p[0], ground_y])
                g_proj = self.vp + (g - self.vp) * s_k
                out[k] = g_proj + (p - g) * s_k
                scale[k] = s_k
            for s in "LR":
                hip, ankle = out[s + "h"], out[s + "a"]
                l1, l2 = self.len[s]
                out[s + "k"] = hip + (ankle - hip) * (l1 / (l1 + l2))
                scale[s + "k"] = (scale[s + "h"] + scale[s + "a"]) / 2
        out["knees"] = (out["Lk"] + out["Rk"]) / 2
        scale["knees"] = (scale["Lk"] + scale["Rk"]) / 2
        # arms swing against the legs (held hands stay still)
        for s in "LR":
            if s in self.hold:
                continue
            opp = "R" if s == "L" else "L"
            sw = math.cos(2 * math.pi * (phi + self.phase0[opp]))  # forward when the opposite foot lands
            sh, el, ha = out[s + "s"], out[s + "e"], out[s + "hand"]
            if self.kind == "side":
                th = math.radians(16) * sw * -self.dir
                c, si = math.cos(th), math.sin(th)
                R = np.array([[c, -si], [si, c]])
                out[s + "e"] = sh + R @ (el - sh)
                th2 = th * 1.15
                c2, s2 = math.cos(th2), math.sin(th2)
                R2 = np.array([[c2, -s2], [s2, c2]])
                out[s + "hand"] = out[s + "e"] + R2 @ (ha - el)
                out[s + "w"] = out[s + "e"] + R2 @ (out[s + "w"] - el)
            else:  # seen from behind: forward/back swing shows as a small rise and fall of the hand
                out[s + "e"] = el + np.array([0, -0.01 * self.h * sw])
                out[s + "hand"] = ha + np.array([0.004 * self.h * sw, -0.035 * self.h * max(0, sw) + 0.01 * self.h * max(0, -sw)])
        return out, scale

    def bone_matrices(self, t):
        pts, scale = self.pose_at(t)
        off = self.cfg.get("offset_x", 0.0)  # mirrored actors are planned in flipped coords, then moved back
        if off:
            pts = {k: p + np.array([off, 0.0]) for k, p in pts.items()}
        mats = {}
        for b, (a, c, grp) in self.bones.items():
            p0, p1 = self.rest_pts[a], self.rest_pts[c]
            q0, q1 = pts[a], pts[c]
            ps = scale.get(a, 1.0) if self.kind != "side" else 1.0
            M = bone_affine(p0, p1, q0, q1, ps)
            # sprite local -> canvas rest = translate(O)
            T = np.array([[1, 0, self.O[0]], [0, 1, self.O[1]], [0, 0, 1]], np.float64)
            mats[b] = (np.vstack([M, [0, 0, 1]]) @ T)[:2]
        ground = max(pts["La"][1], pts["Ra"][1], pts["Ltoe"][1], pts["Rtoe"][1])
        return mats, pts, ground

    def render(self, t, canvas_shape):
        """Return (premultiplied RGBA ROI, ROI origin, ground line y)."""
        mats, pts, ground = self.bone_matrices(t)
        xs = [p[0] for p in pts.values()]
        ys = [p[1] for p in pts.values()]
        pad = 0.3 * self.h
        X0 = int(max(0, min(xs) - pad))
        Y0 = int(max(0, min(ys) - pad))
        X1 = int(min(canvas_shape[1], max(xs) + pad))
        Y1 = int(min(canvas_shape[0], max(ys) + pad))
        if X1 <= X0 or Y1 <= Y0:
            return None, (X0, Y0), ground
        size = (X1 - X0, Y1 - Y0)
        acc = {g: np.zeros((size[1], size[0], 4), np.float32) for g in ("far", "fararm", "body", "near", "neararm")}
        for b, (_, _, grp) in self.bones.items():
            M = mats[b].copy()
            M[:, 2] -= [X0, Y0]
            acc[grp] += cv2.warpAffine(self.sprites[b], M, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        # seams are covered by two bones: renormalise any over-coverage inside each layer
        for g, layer in acc.items():
            over = np.maximum(layer[..., 3:4], 1.0)
            acc[g] = layer / over
        # occlusion order: far arm, far leg, body, near leg, near arm. Joint seams (partial alpha) add,
        # solid limbs occlude what is behind them.
        out = acc["fararm"]
        for g in ("far", "body", "near", "neararm"):
            layer = acc[g]
            occ = np.clip((layer[..., 3:4] - 0.6) / 0.35, 0, 1)
            out = layer + out * (1 - occ)
        out[..., 3] = np.clip(out[..., 3], 0, 1)
        return out, (X0, Y0), ground


def reflection_layer(rgba, ground_local, strength=0.2):
    """Mirror the person about the ground line (local ROI coords), blurred and fading with distance."""
    h = rgba.shape[0]
    g = int(round(ground_local))
    if g <= 0 or g >= h:
        return None, 0
    top = rgba[:g][::-1]
    fade = np.linspace(1, 0, top.shape[0], dtype=np.float32)[:, None, None] ** 1.6
    r = cv2.GaussianBlur(top, (0, 0), 3.5) * fade * strength
    return r, g
