"""LaMa inpainting (OpenCV Zoo ONNX export, 512x512) applied tile-by-tile around masked regions."""
import cv2
import numpy as np
import onnxruntime as ort

_SESSION = None


def _session(model_path):
    global _SESSION
    if _SESSION is None:
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        _SESSION = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
    return _SESSION


def _run(model_path, img_bgr, mask):
    s = _session(model_path)
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    x = rgb.transpose(2, 0, 1)[None]
    m = (mask > 127).astype(np.float32)[None, None]
    out = s.run(None, {"image": x, "mask": m})[0][0]
    out = out.transpose(1, 2, 0)
    if out.max() > 2:  # some exports return 0..255
        out = out / 255.0
    return cv2.cvtColor((np.clip(out, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)


def inpaint(model_path, img, mask, context=2.2):
    """Inpaint every connected masked region using a square crop around it, resized to 512."""
    out = img.copy()
    n, lab, stats, _ = cv2.connectedComponentsWithStats((mask > 127).astype(np.uint8))
    h, w = mask.shape
    for i in range(1, n):
        x, y, bw, bh = stats[i, :4]
        side = int(max(bw, bh) * context) + 32
        side = min(side, max(h, w))
        cx, cy = x + bw // 2, y + bh // 2
        X0 = int(np.clip(cx - side // 2, 0, max(0, w - side)))
        Y0 = int(np.clip(cy - side // 2, 0, max(0, h - side)))
        X1, Y1 = min(w, X0 + side), min(h, Y0 + side)
        crop = out[Y0:Y1, X0:X1]
        cm = ((lab[Y0:Y1, X0:X1] == i) * 255).astype(np.uint8)
        ch, cw = crop.shape[:2]
        res = _run(model_path, cv2.resize(crop, (512, 512), interpolation=cv2.INTER_AREA),
                   cv2.resize(cm, (512, 512), interpolation=cv2.INTER_NEAREST))
        res = cv2.resize(res, (cw, ch), interpolation=cv2.INTER_CUBIC)
        a = (cv2.GaussianBlur(cm, (0, 0), 2).astype(np.float32) / 255)[..., None]
        out[Y0:Y1, X0:X1] = (crop * (1 - a) + res * a).astype(np.uint8)
    return out
