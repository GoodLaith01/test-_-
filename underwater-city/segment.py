"""Cut the swimmer out of each keyframe (GrabCut) and build a clean background plate.

Outputs per image in assets/: <name>_mask.png (soft alpha of the man) and
<name>_plate.png (background with the man inpainted away).
"""
import sys
import cv2
import numpy as np

ASSETS = sys.argv[1] if len(sys.argv) > 1 else "assets"


# Hints in half-res (1376x768) coordinates: generous outline (probable FG) and
# body skeleton strokes (definite FG) for GrabCut.
HINTS = {
    "city": {
        "outline": [(410,222),(565,222),(605,400),(608,745),(500,765),(470,768),(0,768),(0,675),(140,630),(150,570),(330,365),(400,335)],
        "strokes": [((490,300),(490,300),90), ((480,365),(425,555),70), ((545,410),(562,560),26), ((562,560),(548,690),22),
                    ((385,400),(270,520),26), ((270,520),(200,640),22), ((420,560),(330,700),70), ((330,700),(300,768),60),
                    ((380,600),(220,740),45)],
        "bg": [[(465,560),(518,558),(508,655),(472,672)], [(60,548),(160,548),(165,605),(60,640)]],
    },
    "dive": {
        "outline": [(435,190),(620,175),(900,115),(915,0),(1112,0),(1102,135),(965,305),(765,455),(645,565),(485,745),(405,768),(318,768),(328,675),(418,555),(438,430)],
        "strokes": [((530,300),(530,300),120), ((640,330),(800,240),110), ((800,240),(930,150),90), ((930,150),(985,40),55),
                    ((985,40),(990,0),45), ((1040,80),(1075,0),45), ((620,400),(500,560),35), ((500,560),(400,690),28),
                    ((690,420),(560,600),35), ((560,600),(430,700),28)],
        "bg": [[(615,200),(655,262),(700,268),(790,212),(856,166),(904,145),(915,110),(945,0),(620,0)]],
    },
}


def segment(name):
    img = cv2.imread(f"{ASSETS}/{name}.png", cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    s = 0.5
    small = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    mask = np.full(small.shape[:2], cv2.GC_BGD, np.uint8)
    hint = HINTS[name]
    cv2.fillPoly(mask, [np.array(hint["outline"], np.int32)], cv2.GC_PR_FGD)
    for a, b, t in hint["strokes"]:
        if a == b:
            cv2.circle(mask, a, t // 2, cv2.GC_FGD, -1)
        else:
            cv2.line(mask, a, b, cv2.GC_FGD, t)
    for poly in hint.get("bg", []):
        cv2.fillPoly(mask, [np.array(poly, np.int32)], cv2.GC_BGD)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(small, mask, None, bgd, fgd, 10, cv2.GC_INIT_WITH_MASK)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    # keep the largest component (the man)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n > 1:
        big = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        fg = np.where(lab == big, 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    fg = cv2.resize(fg, (w, h), interpolation=cv2.INTER_LINEAR)
    soft = cv2.GaussianBlur(fg, (0, 0), 2.0)
    cv2.imwrite(f"{ASSETS}/{name}_mask.png", soft)

    # background plate: inpaint a dilated version of the man
    hole = cv2.dilate((fg > 40).astype(np.uint8) * 255, np.ones((41, 41), np.uint8))
    q = 0.25
    sm = cv2.resize(img, (int(w * q), int(h * q)), interpolation=cv2.INTER_AREA)
    hm = cv2.resize(hole, (int(w * q), int(h * q)), interpolation=cv2.INTER_NEAREST)
    filled = cv2.inpaint(sm, hm, 12, cv2.INPAINT_TELEA)
    filled = cv2.GaussianBlur(filled, (0, 0), 3)
    filled = cv2.resize(filled, (w, h), interpolation=cv2.INTER_CUBIC)
    a = (cv2.GaussianBlur(hole, (0, 0), 12).astype(np.float32) / 255.0)[..., None]
    plate = (img * (1 - a) + filled * a).astype(np.uint8)
    cv2.imwrite(f"{ASSETS}/{name}_plate.png", plate)

    # preview for checking
    prev = img.copy()
    prev[fg > 128] = (prev[fg > 128] * 0.4 + np.array([0, 0, 255]) * 0.6).astype(np.uint8)
    cv2.imwrite(f"{ASSETS}/../preview_{name}_mask.jpg", cv2.resize(prev, (1376, 768)))
    cv2.imwrite(f"{ASSETS}/../preview_{name}_plate.jpg", cv2.resize(plate, (1376, 768)))


for n in HINTS:
    segment(n)
    print("done", n)
