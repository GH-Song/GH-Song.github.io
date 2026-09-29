#!/usr/bin/env python3
"""Renders the link-preview card static/img/og.jpg (1200 x 630) with headless Chrome.

    python3 tools/make_og.py

Numbers are read from content/*.json, so re-run it after they change.
Requires: pillow, Google Chrome.
"""
import json
import pathlib
import shutil
import subprocess
import tempfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "static" / "img"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def main():
    load = lambda n: json.loads((ROOT / "content" / f"{n}.json").read_text("utf-8"))
    site, pubs, honors = load("site"), load("publications"), load("honors")
    journals = [p for p in pubs["papers"] if p.get("type", "journal") == "journal"]
    filed = sum(len(p["filings"]) for p in honors["patents"])
    stats = [(len(journals), "Journal articles"), (site["scholar"]["citations"], "Citations"),
             (filed, "Patent applications"), (len(honors["awards"]), "Awards")]
    tmp = pathlib.Path(tempfile.mkdtemp())
    shutil.copy(IMG / "portrait.jpg", tmp / "portrait.jpg")
    cells = "".join(f"<div><b>{v}</b><span>{l}</span></div>" for v, l in stats)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<style>
*{{margin:0;box-sizing:border-box}}
html,body{{width:1200px;height:630px;overflow:hidden;background:#fff;color:#111418;font-family:"Pretendard Variable",Pretendard,sans-serif}}
.wrap{{position:absolute;inset:0;padding:88px 96px;display:grid;grid-template-columns:1fr 220px;gap:64px}}
h1{{font-size:64px;font-weight:700;letter-spacing:-.02em;line-height:1.1}}
h1 span{{font-size:34px;font-weight:400;color:#7b818a;margin-left:18px;letter-spacing:0}}
.role{{font-size:28px;color:#464c55;margin-top:22px;line-height:1.4}}
.stats{{display:flex;gap:0;margin-top:64px;border-top:2px solid #111418}}
.stats div{{padding:22px 26px 0 0;margin-right:26px;border-right:1px solid #eaecef;white-space:nowrap}}
.stats div:last-child{{border-right:0}}
.stats b{{display:block;font-size:46px;font-weight:600;letter-spacing:-.02em}}
.stats span{{font-size:17px;color:#7b818a}}
img{{width:220px;height:275px;object-fit:cover;border-radius:6px}}
.url{{position:absolute;left:96px;bottom:56px;font-size:20px;color:#7b818a}}
</style></head><body>
<div class="wrap"><div>
<h1>Gookho Song<span>송국호</span></h1>
<p class="role">Ph.D. Candidate, Bio and Brain Engineering<br>KAIST</p>
<div class="stats">{cells}</div></div>
<div><img src="portrait.jpg"></div></div>
<p class="url">gh-song.github.io</p>
</body></html>"""
    (tmp / "og.html").write_text(html, "utf-8")
    shot = tmp / "og.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1200,630",
                    "--virtual-time-budget=6000", f"--screenshot={shot}", (tmp / "og.html").as_uri()],
                   check=True, capture_output=True)
    Image.open(shot).convert("RGB").save(IMG / "og.jpg", quality=90, optimize=True, progressive=True)
    print("wrote", (IMG / "og.jpg").relative_to(ROOT))


if __name__ == "__main__":
    main()
