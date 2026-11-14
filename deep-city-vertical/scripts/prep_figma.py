"""Prepare the Figma-generated keyframes for Remotion.

- Upscales each 864x1536 keyframe 2x (Lanczos + light unsharp mask).
- Cuts the swimmer out of `dive` and `city` (GrabCut guided by hand-placed
  outline/skeleton hints) and inpaints a clean background plate.

Writes to public/: <name>.jpg (full frame), <name>_plate.jpg, <name>_man.png (RGBA).
Usage: python3 scripts/prep_figma.py figma-src public
"""
import sys

import cv2
import numpy as np

SRC, OUT = sys.argv[1], sys.argv[2]
UP = 2

# Hints in original 864x1536 coordinates.
HINTS = {
    "dive": {
        "outline": [(270, 0), (595, 0), (590, 130), (565, 260), (610, 380), (705, 610), (718, 760),
                    (712, 1045), (585, 1045), (545, 920), (600, 780), (565, 650), (300, 650), (262, 760),
                    (335, 885), (250, 955), (135, 945), (135, 640), (195, 450), (285, 345), (265, 200)],
        "strokes": [((430, 455), (430, 455), 150), ((250, 560), (600, 560), 80), ((300, 420), (560, 420), 60),
                    ((190, 640), (220, 780), 50), ((220, 770), (230, 880), 38), ((655, 650), (662, 800), 50),
                    ((655, 800), (640, 960), 38), ((235, 875), (298, 828), 22), ((330, 260), (330, 60), 50), ((520, 250), (540, 60), 40)],
        "bg": [[(310, 665), (550, 665), (548, 1000), (312, 1000)], [(398, 0), (478, 0), (468, 225), (402, 255)]],
    },
    "city": {
        "outline": [(55, 878), (315, 878), (325, 1100), (372, 1300), (365, 1536), (0, 1536), (0, 1075), (55, 1000)],
        "strokes": [((190, 1000), (190, 1000), 160), ((110, 1200), (200, 1500), 240)],
        "bg": [],
    },
}


def upscale(img):
    big = cv2.resize(img, None, fx=UP, fy=UP, interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(big, (0, 0), 1.2)
    return cv2.addWeighted(big, 1.35, blur, -0.35, 0)


def cutout(name, img):
    hint = HINTS[name]
    mask = np.full(img.shape[:2], cv2.GC_BGD, np.uint8)
    cv2.fillPoly(mask, [np.array(hint["outline"], np.int32)], cv2.GC_PR_FGD)
    for a, b, t in hint["strokes"]:
        if a == b:
            cv2.circle(mask, a, t // 2, cv2.GC_FGD, -1)
        else:
            cv2.line(mask, a, b, cv2.GC_FGD, t)
    for poly in hint["bg"]:
        cv2.fillPoly(mask, [np.array(poly, np.int32)], cv2.GC_BGD)
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(img, mask, None, bgd, fgd, 10, cv2.GC_INIT_WITH_MASK)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n > 1:
        fg = np.where(lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]), 255, 0).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    return fg


for name in ["dive", "city", "street"]:
    img = cv2.imread(f"{SRC}/{name}.png", cv2.IMREAD_COLOR)
    big = upscale(img)
    cv2.imwrite(f"{OUT}/{name}.jpg", big, [cv2.IMWRITE_JPEG_QUALITY, 94])
    if name not in HINTS:
        continue
    fg = cutout(name, img)
    fg_big = cv2.resize(fg, None, fx=UP, fy=UP, interpolation=cv2.INTER_LINEAR)
    alpha = cv2.GaussianBlur(fg_big, (0, 0), 1.6)
    # plate: inpaint a dilated hole at quarter res, blend back in
    hole = cv2.dilate(fg_big, np.ones((45, 45), np.uint8))
    q = 0.25
    sm = cv2.resize(big, None, fx=q, fy=q, interpolation=cv2.INTER_AREA)
    hm = cv2.resize(hole, (sm.shape[1], sm.shape[0]), interpolation=cv2.INTER_NEAREST)
    filled = cv2.inpaint(sm, hm, 15, cv2.INPAINT_TELEA)
    filled = cv2.resize(cv2.GaussianBlur(filled, (0, 0), 3), (big.shape[1], big.shape[0]), interpolation=cv2.INTER_CUBIC)
    a = (cv2.GaussianBlur(hole, (0, 0), 14).astype(np.float32) / 255)[..., None]
    plate = (big * (1 - a) + filled * a).astype(np.uint8)
    cv2.imwrite(f"{OUT}/{name}_plate.jpg", plate, [cv2.IMWRITE_JPEG_QUALITY, 94])
    ys, xs = np.where(alpha > 4)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    cv2.imwrite(f"{OUT}/{name}_man.png", np.dstack([big, alpha])[y0:y1, x0:x1])
    print(name, "man bbox (src 864 units):", x0 / UP, y0 / UP, x1 / UP, y1 / UP)
    prev = img.copy()
    prev[fg > 128] = (prev[fg > 128] * 0.4 + np.array([0, 0, 255]) * 0.6).astype(np.uint8)
    cv2.imwrite(f"{SRC}/check_{name}.jpg", cv2.resize(prev, (432, 768)))
