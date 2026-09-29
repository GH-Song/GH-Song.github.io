#!/usr/bin/env python3
"""Builds every web image in static/img/ from the original sources.

Run only when a source changes — the outputs are committed, so the site build
itself never needs these files.

    python3 tools/prep_images.py

Sources live outside this repository on purpose (publisher PDFs must not be
redistributed; the lab thumbnails are large originals). Edit the paths below.
Requires: pymupdf, pillow.

Processing is limited to crop, trimming white margins, erasing a panel letter
and resizing.
"""
import pathlib

import fitz
from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "img"
PUB = OUT / "pub"
PUB.mkdir(parents=True, exist_ok=True)

HOME = pathlib.Path.home()
SRC_PAPERS = HOME / "Projects" / "mypr" / "published"
SRC_LAB = HOME / "Projects" / "mypr" / "sources" / "lab-thumbs"      # from mooolab.kaist.ac.kr/Publication.html
SRC_PR = HOME / "Projects" / "optica-cardnews" / "260806_KAIST, 산란층에 가려진 투명 물체, 사진 한 장으로 복원한다 rev.3.pdf"
SRC_PHOTO = HOME / "Downloads" / "바이오및뇌공학과_송국호_개인사진.jpg"


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


# ── portrait (shown small) ─────────────────────────────────────────────────
print("portrait")
p = ImageOps.exif_transpose(Image.open(SRC_PHOTO)).convert("RGB")
p = p.crop((342, 260, 1842, 2135)).resize((400, 500), Image.LANCZOS)      # 4:5 head and shoulders
save(p, OUT / "portrait.webp", q=86)
p.save(OUT / "portrait.jpg", quality=88, optimize=True, progressive=True)

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
