#!/usr/bin/env python3
"""Builds every web image in static/img/ from the original sources.

Run only when a source changes — the outputs are committed, so the site build
itself never needs these files.

    python3 tools/prep_images.py

Sources live outside this repository on purpose (publisher PDFs must not be
redistributed; the lab thumbnails are large originals). Edit the paths below.
Requires: pymupdf, pillow.

Processing is limited to crop, trimming white margins, erasing a panel letter
and resizing — except the portrait, where the chandelier above the head is
painted out (requested by Gookho) before the face crop.
Requires numpy as well.
"""
import pathlib

import fitz
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "img"
PUB = OUT / "pub"
PUB.mkdir(parents=True, exist_ok=True)

HOME = pathlib.Path.home()
SRC_PAPERS = HOME / "Projects" / "mypr" / "published"
SRC_LAB = HOME / "Projects" / "mypr" / "sources" / "lab-thumbs"      # from mooolab.kaist.ac.kr/Publication.html
SRC_PR = HOME / "Projects" / "optica-cardnews" / "260806_KAIST, 산란층에 가려진 투명 물체, 사진 한 장으로 복원한다 rev.3.pdf"
SRC_PHOTO = HOME / "Projects" / "mypr" / "IMGL0353.jpg"
SRC_APR = HOME / "Projects" / "mypr" / "sources" / "papers" / "apr2025_fig1.jpg"   # Fig. 1, CC BY 4.0
SRC_PAT = HOME / "Projects" / "mypr" / "sources" / "patents"                     # Google Patents front-page drawings


def pdf_image(pdf, page, xref):
    """Embedded image at native resolution (page is 1-based, xref from the PDF)."""
    d = fitz.open(pdf)
    px = fitz.Pixmap(d, xref)
    if px.alpha:
        px = fitz.Pixmap(px, 0)
    if px.n == 1:
        return Image.frombytes("L", (px.width, px.height), px.samples).convert("RGB")
    if px.n >= 4:
        px = fitz.Pixmap(fitz.csRGB, px)
    return Image.frombytes("RGB", (px.width, px.height), px.samples)


def flatten(im):
    """Composite transparency onto white."""
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return bg.convert("RGB")
    return im.convert("RGB")


def trim(im, pad=6):
    """Cut uniform white margins."""
    im = flatten(im)
    diff = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255)))
    box = ImageOps.grayscale(diff).point(lambda v: 255 if v > 12 else 0).getbbox()
    if not box:
        return im
    l, t, r, b = box
    return im.crop((max(0, l - pad), max(0, t - pad), min(im.width, r + pad), min(im.height, b + pad)))


def blank(im, box):
    im = im.copy()
    ImageDraw.Draw(im).rectangle(box, fill=(255, 255, 255))
    return im


def fit(im, w, h):
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    return im


def save(im, path, q=84):
    im.save(path, "WEBP", quality=q, method=6)
    print(f"  {path.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  {path.stat().st_size // 1024} KB")


def remove_lamps(a, origin):
    """Paint out the two pendant lamps that hang into the top of the face crop.

    The glass (and its glow) is masked by shape and brightness; hair is never
    masked. The hole is filled from the surrounding wall/ceiling with a
    pull-push pyramid, smoothed, and given grain matched to the ceiling.
    """
    H, W = a.shape[:2]
    lum = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    yy, xx = np.mgrid[0:H, 0:W]
    X, Y = xx + origin[0], yy + origin[1]

    def footprint(x0, x1, y1, r):                         # box with rounded bottom corners
        inside = (X >= x0) & (X <= x1) & (Y <= y1)
        for cx in (x0 + r, x1 - r):
            side = (X < cx) if cx == x0 + r else (X > cx)
            corner = side & (Y > y1 - r)
            inside &= ~(corner & ((X - cx) ** 2 + (Y - (y1 - r)) ** 2 > r * r))
        return inside

    def dilate(m, px):
        return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * px + 1))) > 0

    left = dilate(footprint(1095, 1552, 936, 60) & (lum > 110), 3) & (lum > 110) & (Y < 944)
    core = footprint(1698, 2190, 900, 55) & (lum > 55)
    right = core | (dilate(core, 36) & (Y < 922) & (lum > 39))
    mask = left | right
    warm = (a[..., 0] - a[..., 2]) > 8                    # brown hair, as opposed to the neutral ceiling
    valid = ~mask & ~((lum < 110) & (X < 1570) & (Y < 1010)) & ~((lum < 110) & warm & (Y < 1010))

    levels = [(a * valid[..., None], valid.astype(np.float32))]
    while min(levels[-1][1].shape) > 4:
        I, w = levels[-1]
        h, v = (I.shape[0] + 1) // 2 * 2, (I.shape[1] + 1) // 2 * 2
        Ip = np.zeros((h, v, 3), np.float32); Ip[:I.shape[0], :I.shape[1]] = I
        wp = np.zeros((h, v), np.float32); wp[:w.shape[0], :w.shape[1]] = w
        levels.append((Ip.reshape(h // 2, 2, v // 2, 2, 3).sum((1, 3)), wp.reshape(h // 2, 2, v // 2, 2).sum((1, 3))))
    I, w = levels[-1]
    f = I / np.maximum(w, 1e-6)[..., None]
    for I, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(f, 2, 0), 2, 1)[:I.shape[0], :I.shape[1]]
        wt = np.clip(w, 0, 1)[..., None]
        f = wt * (I / np.maximum(w, 1e-6)[..., None]) + (1 - wt) * up
    for _ in range(300):
        avg = (np.roll(f, 1, 0) + np.roll(f, -1, 0) + np.roll(f, 1, 1) + np.roll(f, -1, 1)) / 4
        f = np.where(valid[..., None], a, avg)
    ref = lum[20:60, W - 120:W - 20]
    grain = float((ref - np.asarray(Image.fromarray(ref.astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32)).std())
    f = f + np.random.default_rng(3).normal(0, grain, (H, W, 1)).astype(np.float32)
    alpha = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32)[..., None] / 255
    return np.clip(a * (1 - alpha) + f * alpha, 0, 255).astype(np.uint8)


# ── portrait (shown small) ─────────────────────────────────────────────────
print("portrait")
CROP = (1215, 848, 2335, 2248)                            # 1120 x 1400 (4:5), face-centred
p = ImageOps.exif_transpose(Image.open(SRC_PHOTO)).convert("RGB").crop(CROP)
p = Image.fromarray(remove_lamps(np.asarray(p, dtype=np.float32), CROP[:2])).resize((400, 500), Image.LANCZOS)
save(p, OUT / "portrait.webp", q=88)
p.save(OUT / "portrait.jpg", quality=90, optimize=True, progressive=True)

# ── publication thumbnails ────────────────────────────────────────────────
print("publication thumbnails")
TW, TH = 480, 320
lab = {
    "sciadv2025": "2025-5.jpg", "tpami2025": "2025-6.png", "lsa2024": "2024-3.png",
    "ncomms2024": "2024-2.jpg", "oe2024": "2024-4.png", "nmi2023": "2023-2.jpg",
    "jom2023": "2023-1.png", "jkps2022": "2022-2.jpg",
}
for key, name in lab.items():
    save(fit(trim(Image.open(SRC_LAB / name)), TW, TH), PUB / f"{key}.webp")
pr_fig1 = trim(pdf_image(SRC_PR, 6, 41))          # Optica: plane-wave vs point illumination
pr_fig3 = trim(pdf_image(SRC_PR, 7, 46))          # Optica: setup, measurement, reconstruction
save(fit(pr_fig1, TW, TH), PUB / "optica2026.webp")
sa_fig5 = pdf_image(SRC_PAPERS / "ScienceAdvances_ReconSpec.pdf", 7, 719)
library = blank(blank(sa_fig5.crop((0, 0, 776, 776)), (0, 0, 40, 44)), (0, 400, 44, 450))
save(fit(trim(library), TW, TH), PUB / "pj2026.webp")
save(fit(trim(Image.open(SRC_APR)), TW, TH), PUB / "apr2025.webp")

# ── patent drawings (front page of the US publications) ──────────────────
print("patent drawings")
PAT = OUT / "patent"
PAT.mkdir(exist_ok=True)
for key, name in (("us12571712", "US20240377304A1_D00000.png"),        # pre-grant publication of US 12,571,712 B2
                  ("us20240280406", "US20240280406A1_D00000.png")):
    save(fit(trim(Image.open(SRC_PAT / name), pad=12), 360, 360), PAT / f"{key}.webp")

# ── research-page figures (original colours, white background) ───────────
print("research figures")
SA = SRC_PAPERS / "ScienceAdvances_ReconSpec.pdf"
save(fit(pdf_image(SA, 2, 219), 1400, 1400), OUT / "sa-schematic.webp")
save(fit(blank(pdf_image(SA, 3, 320).crop((0, 0, 1000, 412)), (0, 0, 44, 46)), 1000, 1000), OUT / "sa-device.webp")
save(fit(trim(library), 776, 776), OUT / "sa-library.webp")
TP = SRC_PAPERS / "TPAMI_VDPS.pdf"
save(fit(pdf_image(TP, 1, 24), 1200, 1200), OUT / "tp-config.webp")
save(fit(blank(pdf_image(TP, 11, 512).crop((0, 0, 2664, 1632)), (0, 0, 60, 60)), 1400, 1400), OUT / "tp-real.webp")
save(fit(pr_fig1, 1400, 1400), OUT / "op-fig1.webp")
save(fit(pr_fig3, 1400, 1400), OUT / "op-fig3.webp")
print("done")
