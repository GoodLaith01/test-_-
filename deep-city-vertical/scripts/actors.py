"""Actors: the people, swimmers and sharks that get animated, with their cut-out masks.

Coordinates are in 864x1536 source units (the Figma keyframes). Each actor has
a rough box and optional GrabCut hints; `segment()` returns a full-frame mask.
"""
import os

import cv2
import numpy as np

_HUMAN = None


def _human_session():
    """PP-HumanSeg (OpenCV Zoo ONNX). Path from $PPHUMANSEG."""
    global _HUMAN
    if _HUMAN is None:
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        _HUMAN = ort.InferenceSession(os.environ["PPHUMANSEG"], opts, providers=["CPUExecutionProvider"])
    return _HUMAN


def _human_prob(crop):
    x = cv2.resize(crop, (192, 192), interpolation=cv2.INTER_AREA)[:, :, ::-1].astype(np.float32) / 255
    x = ((x - 0.5) / 0.5).transpose(2, 0, 1)[None]
    out = _human_session().run(None, {"x": x})[0][0]
    e = np.exp(out - out.max(0))
    p = (e / e.sum(0))[1]
    return cv2.resize(p, (crop.shape[1], crop.shape[0]), interpolation=cv2.INTER_CUBIC)


def segment_person(img, actor, margin=6):
    """Person matte from PP-HumanSeg on a square crop, limited to this actor's box and blob."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = actor["box"]
    cx, hh = (x0 + x1) // 2, y1 - y0
    side = int(hh * 1.15)
    X0 = int(np.clip(cx - side // 2, 0, w - side))
    Y0 = int(np.clip(y0 - int(hh * 0.08), 0, h - side))
    p = _human_prob(img[Y0:Y0 + side, X0:X0 + side])
    full = np.zeros((h, w), np.float32)
    full[Y0:Y0 + side, X0:X0 + side] = p
    lim = np.zeros((h, w), np.float32)
    lim[max(0, y0 - margin):y1 + margin, max(0, x0 - margin):x1 + margin] = 1
    full *= lim
    hard = (full > 0.5).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(hard)
    if n > 1:
        keep = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        blob = cv2.dilate((lab == keep).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(np.float32)
        full *= blob
    alpha = np.clip((full - 0.3) / 0.4, 0, 1)
    return (alpha * 255).astype(np.uint8)

# kind: "side" = walks sideways (stride opens/closes), "back" = walks away/toward camera,
#       "swim" = swimmer, "glide" = shark/fish (rigid glide with a tail wave)
STREET_ACTORS = [
    dict(name="man_left", kind="side", box=(62, 1150, 212, 1442), dir=+1,
         fg=[((150, 1180), (150, 1180), 34), ((140, 1210), (120, 1330), 40), ((120, 1330), (90, 1420), 18), ((130, 1330), (180, 1415), 18), ((168, 1240), (176, 1298), 9)],
         bg=[[(62, 1200), (98, 1200), (98, 1318), (62, 1318)], [(118, 1360), (140, 1360), (130, 1425), (120, 1425)],
             [(186, 1228), (212, 1228), (212, 1400), (190, 1400)], [(160, 1302), (185, 1302), (185, 1340), (168, 1340)]]),
    dict(name="woman_dress", kind="side", box=(392, 1168, 478, 1342), dir=-1, skirt=True, mirror=True,
         fg=[((428, 1185), (428, 1185), 20), ((430, 1205), (430, 1290), 26), ((425, 1290), (410, 1332), 8), ((440, 1290), (465, 1325), 8), ((420, 1205), (402, 1232), 5), ((403, 1230), (396, 1256), 4)],
         bg=[[(452, 1168), (478, 1168), (478, 1238), (452, 1238)]]),
    dict(name="man_red", kind="back", box=(582, 1176, 642, 1378), dir=0, hold=["R"],
         fg=[((617, 1190), (617, 1190), 20), ((615, 1210), (612, 1290), 30), ((605, 1290), (598, 1350), 10), ((622, 1290), (622, 1360), 10), ((630, 1245), (641, 1282), 6), ((600, 1350), (597, 1373), 8)]),
    dict(name="woman_pack", kind="back", box=(642, 1178, 708, 1388), dir=0, skirt=True, hold=["L"],
         fg=[((672, 1195), (672, 1195), 20), ((672, 1215), (672, 1300), 30), ((664, 1300), (660, 1370), 10), ((682, 1300), (685, 1375), 10), ((652, 1240), (645, 1282), 6)]),
    dict(name="man_bag", kind="back", box=(766, 1152, 842, 1398), dir=0,
         fg=[((805, 1170), (805, 1170), 26), ((805, 1195), (805, 1300), 40), ((790, 1300), (782, 1385), 12), ((818, 1300), (822, 1390), 12), ((785, 1225), (779, 1280), 7), ((830, 1225), (836, 1278), 7)]),
]

SKY_ACTORS = [
    dict(name="swimmer_hi", kind="swim", box=(538, 172, 615, 246), heading=(1.0, -0.55),
         fg=[((600, 190), (560, 220), 12), ((560, 220), (548, 236), 6)]),
    dict(name="swimmer_lo", kind="swim", box=(515, 402, 565, 447), heading=(-1.0, -0.35),
         fg=[((527, 410), (550, 432), 9)]),
    dict(name="shark_hi", kind="glide", box=(350, 115, 425, 152), heading=(1.0, 0.05), fg=[((365, 133), (410, 140), 8)]),
    dict(name="shark_lo", kind="glide", box=(465, 322, 530, 348), heading=(1.0, 0.03), fg=[((478, 333), (518, 340), 6)]),
]


def segment(img, actor, pad=6, iters=8):
    """Pedestrians: PP-HumanSeg matte. Swimmers/sharks: GrabCut inside the box, seeded with strokes."""
    if actor["kind"] in ("side", "back") and os.environ.get("PPHUMANSEG"):
        return segment_person(img, actor)
    h, w = img.shape[:2]
    x0, y0, x1, y1 = actor["box"]
    X0, Y0, X1, Y1 = max(0, x0 - 30), max(0, y0 - 30), min(w, x1 + 30), min(h, y1 + 30)
    crop = img[Y0:Y1, X0:X1]
    m = np.full(crop.shape[:2], cv2.GC_BGD, np.uint8)
    m[y0 - Y0 + 0: y1 - Y0, x0 - X0: x1 - X0] = cv2.GC_PR_FGD
    for a, b, t in actor.get("fg", []):
        a = (a[0] - X0, a[1] - Y0)
        b = (b[0] - X0, b[1] - Y0)
        if a == b:
            cv2.circle(m, a, max(1, t // 2), cv2.GC_FGD, -1)
        else:
            cv2.line(m, a, b, cv2.GC_FGD, max(1, t))
    for poly in actor.get("bg", []):
        cv2.fillPoly(m, [np.array([(p[0] - X0, p[1] - Y0) for p in poly], np.int32)], cv2.GC_BGD)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(crop, m, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    fg = np.where((m == cv2.GC_FGD) | (m == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n > 1:
        fg = np.where(lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]), 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    out = np.zeros((h, w), np.uint8)
    out[Y0:Y1, X0:X1] = fg
    return out
