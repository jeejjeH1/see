"""Trace the raster logos in assets/logos/src into crisp SVGs (assets/logos/*.svg).

Mono logos are traced as a single shape (fill=currentColor so the video can recolor them).
Seismic is split into its facets (connected components) and each keeps its own colour.
Vend keeps its two tones.
"""
import json
import sys
from pathlib import Path

import numpy as np
import potrace
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "logos" / "src"
OUT = ROOT / "assets" / "logos"
SCALE = 8


def upscale_mask(mask, scale=SCALE):
    im = Image.fromarray((mask * 255).astype(np.uint8))
    im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    im = im.filter(ImageFilter.GaussianBlur(scale * 0.45))
    return np.array(im) > 127


def trace(mask, scale=SCALE):
    bm = potrace.Bitmap(~mask)  # potracer treats dark (False) pixels as ink
    plist = bm.trace(turdsize=20, alphamax=1.0, opticurve=True, opttolerance=0.2)
    s = 1.0 / scale
    parts = []
    for curve in plist:
        x, y = curve.start_point.x, curve.start_point.y
        d = [f"M{x*s:.2f},{y*s:.2f}"]
        for seg in curve.segments:
            if seg.is_corner:
                (cx, cy), (ex, ey) = (seg.c.x, seg.c.y), (seg.end_point.x, seg.end_point.y)
                d.append(f"L{cx*s:.2f},{cy*s:.2f}L{ex*s:.2f},{ey*s:.2f}")
            else:
                (ax, ay), (bx, by), (ex, ey) = (seg.c1.x, seg.c1.y), (seg.c2.x, seg.c2.y), (seg.end_point.x, seg.end_point.y)
                d.append(f"C{ax*s:.2f},{ay*s:.2f} {bx*s:.2f},{by*s:.2f} {ex*s:.2f},{ey*s:.2f}")
        d.append("Z")
        parts.append("".join(d))
    return "".join(parts)


def bbox(mask):
    ys, xs = np.nonzero(mask)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def svg(viewbox, body, extra=""):
    x0, y0, x1, y1 = viewbox
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {x1-x0} {y1-y0}">'
            f"{extra}{body}</svg>")


def components(mask):
    """4-connected components of a boolean mask (small images only)."""
    h, w = mask.shape
    labels = np.zeros((h, w), int)
    n = 0
    for sy in range(h):
        for sx in range(w):
            if mask[sy, sx] and not labels[sy, sx]:
                n += 1
                stack = [(sy, sx)]
                labels[sy, sx] = n
                while stack:
                    y, x = stack.pop()
                    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not labels[ny, nx]:
                            labels[ny, nx] = n
                            stack.append((ny, nx))
    return labels, n


def main():
    meta = {}
    for png in sorted(SRC.glob("*.png")):
        name = png.stem
        rgba = np.array(Image.open(png).convert("RGBA")).astype(float)
        alpha = rgba[..., 3] / 255
        lum = rgba[..., :3].mean(axis=2)
        solid = alpha > 0.5
        x0, y0, x1, y1 = bbox(solid)
        pad = 1
        vb = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)

        if name == "seismic":
            labels, n = components(alpha > 0.85)
            body = []
            for i in range(1, n + 1):
                m = labels == i
                if m.sum() < 200:
                    continue
                col = np.median(rgba[m][:, :3], axis=0).astype(int)
                # dilate slightly so the anti-aliased rim is kept
                d = trace(upscale_mask(m | ((labels == 0) & (alpha > 0.5) & near(m))))
                body.append(f'<path fill="#{col[0]:02x}{col[1]:02x}{col[2]:02x}" d="{d}"/>')
            out = svg(vb, "".join(body))
        elif name == "vend":
            dark = solid & (lum < 20)
            grey = solid & (lum >= 20)
            out = svg(vb, f'<path fill="currentColor" fill-rule="evenodd" opacity="0.72" d="{trace(upscale_mask(grey))}"/>'
                          f'<path fill="currentColor" fill-rule="evenodd" d="{trace(upscale_mask(dark))}"/>')
        elif name == "brookwell":
            # embossed white "B": keep only the letter, drop the soft floor shadow
            m = alpha > 0.9
            labels, n = components(m)
            sizes = [(labels == i).sum() for i in range(1, n + 1)]
            m = labels == (int(np.argmax(sizes)) + 1)
            x0, y0, x1, y1 = bbox(m)
            vb = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
            out = svg(vb, f'<path fill="currentColor" fill-rule="evenodd" d="{trace(upscale_mask(m))}"/>')
        else:
            out = svg(vb, f'<path fill="currentColor" fill-rule="evenodd" d="{trace(upscale_mask(solid))}"/>')

        (OUT / f"{name}.svg").write_text(out)
        meta[name] = {"w": int(vb[2] - vb[0]), "h": int(vb[3] - vb[1])}
        print(name, meta[name], file=sys.stderr)
    (OUT / "logos.json").write_text(json.dumps(meta, indent=2))


def near(m):
    """1px dilation."""
    d = m.copy()
    d[1:] |= m[:-1]
    d[:-1] |= m[1:]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


if __name__ == "__main__":
    main()
