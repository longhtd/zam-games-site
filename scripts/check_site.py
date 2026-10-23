#!/usr/bin/env python3
"""Static check of the games.zamverse.com repo: local links/assets resolve, anchors exist, JSON-LD parses,
meta/OG/canonical present and consistent, sitemap matches pages, Play links/QR/offers exactly match games.json,
generated pages are not out of date (apply_state --check), no stale numbers.
Usage: python scripts/check_site.py  -> exit 1 on any error."""
import re, sys, json
from pathlib import Path
from urllib.parse import urlparse, unquote

import subprocess
repo = Path(__file__).resolve().parent.parent
_gj = json.loads((repo / "games.json").read_text(encoding="utf-8"))
LIVE = {g["slug"] for g in _gj["games"] if g["live"]}
SLUGS = [g["slug"] for g in _gj["games"]]
HOST = "https://games.zamverse.com"
errs, warns = [], []
E = lambda m: errs.append(m)
W = lambda m: warns.append(m)

pages = sorted(p for p in repo.rglob("*.html") if ".git" not in p.parts and not p.name.startswith("google"))
ids_by_page = {}
for p in pages:
    ids_by_page[p] = set(re.findall(r'\bid="([^"]+)"', p.read_text(encoding="utf-8")))


def resolve(base, ref):
    path = unquote(ref.split("#")[0].split("?")[0])
    if path.startswith("/"):
        t = repo / path.lstrip("/")
    else:
        t = base.parent / path
    if t.is_dir() or path.endswith("/") or path == "":
        t = t / "index.html"
    if not t.exists() and not t.suffix:
        t2 = Path(str(t) + "/index.html") if False else t.parent / t.name / "index.html"
        if t2.exists():
            return t2
    return t


nlinks = 0
for p in pages:
    h = p.read_text(encoding="utf-8")
    rel = p.relative_to(repo).as_posix()
    # links / assets
    hs = re.sub(r"<script.*?</script>", "", h, flags=re.S)
    for attr, ref in re.findall(r'\b(href|src|content)="([^"]*)"', hs):
        if attr == "content" and not ref.startswith(HOST):
            continue
        if ref.startswith(("mailto:", "tel:", "javascript:", "data:", "http://", "#")) or ref == "":
            if ref.startswith("#") and len(ref) > 1 and ref[1:] not in ids_by_page[p]:
                E("%s: anchor %s missing" % (rel, ref))
            continue
        if ref.startswith("https://"):
            if ref.startswith(HOST):
                ref = ref[len(HOST):] or "/"
            else:
                continue
        nlinks += 1
        t = resolve(p, ref)
        if not t.exists():
            E("%s: broken %s=%s" % (rel, attr, ref))
        elif "#" in ref and t.suffix == ".html":
            frag = ref.split("#")[1]
            if frag and frag not in ids_by_page.get(t, set()):
                E("%s: anchor #%s missing in %s" % (rel, frag, t.relative_to(repo).as_posix()))
    # JSON-LD
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try:
            json.loads(m.group(1))
        except Exception as e:
            E("%s: JSON-LD invalid: %s" % (rel, e))
    # head basics (not for 404)
    if rel not in ("404.html",):
        for need, pat in (("title", r"<title>[^<]{5,}</title>"), ("description", r'name="description" content="[^"]{12,}"'),
                          ("canonical", r'rel="canonical" href="[^"]+"'), ("og:title", r'property="og:title"'),
                          ("og:image", r'property="og:image"'), ("viewport", r'name="viewport"')):
            if not re.search(pat, h):
                E("%s: missing %s" % (rel, need))
        c = re.search(r'rel="canonical" href="([^"]+)"', h)
        if c:
            want = HOST + "/" + ("" if rel == "index.html" else rel[:-len("index.html")])
            if c.group(1) != want:
                E("%s: canonical %s != %s" % (rel, c.group(1), want))
        og = re.search(r'property="og:url" content="([^"]+)"', h)
        if og and c and og.group(1) != c.group(1):
            E("%s: og:url differs from canonical" % rel)
        d = re.search(r'name="description" content="([^"]*)"', h)
        if d and len(d.group(1)) > 200:
            W("%s: description %d chars (>200)" % (rel, len(d.group(1))))
    # Play links only for live games
    for slug in SLUGS:
        if slug not in LIVE and re.search(r"play\.google\.com/store/apps/details\?id=com\.zamverse\.%s" % slug, h) and rel != "offers.json":
            E("%s: Play link for non-live %s" % (rel, slug))
    # leftover words
    for bad in ("200 levels", "200 handmade", "Coming soon to Google Play Get", "lorem", "TODO", "undefined"):
        if bad in h and not (bad == "200 levels" and False):
            W("%s: contains '%s'" % (rel, bad))

# sitemap
sm = (repo / "sitemap.xml").read_text(encoding="utf-8")
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
for l in locs:
    t = resolve(repo / "x", l[len(HOST):])
    if not t.exists():
        E("sitemap: %s has no page" % l)
if len(set(locs)) != len(locs):
    E("sitemap: duplicate loc")
for p in pages:
    rel = p.relative_to(repo).as_posix()
    if rel == "404.html" or "delete-account" in rel or "/support/" in rel or "/privacy/" in rel:
        continue
    u = HOST + "/" + ("" if rel == "index.html" else rel[:-len("index.html")])
    if u not in locs:
        W("sitemap: missing %s" % u)

# offers.json
od = json.loads((repo / "offers.json").read_text(encoding="utf-8"))
for o in od["offers"]:
    slug = o.get("id")
    if slug in SLUGS:
        if (slug in LIVE) == (o.get("available") is False):
            E("offers.json: %s available flag does not match live status" % slug)
        t = resolve(repo / "x", urlparse(o["iconUrl"]).path)
        if not t.exists():
            E("offers.json: %s iconUrl missing" % slug)

# images referenced in game pages exist and are non-empty
for p in repo.rglob("*"):
    if p.suffix in (".png", ".webp", ".jpg") and p.stat().st_size < 200:
        E("tiny/empty image %s" % p.relative_to(repo))

_p = subprocess.run([sys.executable, str(repo / "scripts" / "apply_state.py"), "--check"], capture_output=True, text=True)
if _p.returncode != 0:
    E("generated state is out of date: " + " | ".join(_p.stdout.strip().splitlines()))
for s in SLUGS:
    page = (repo / s / "index.html").read_text(encoding="utf-8")
    has_btn = "Get it on Google Play" in page
    if (s in LIVE) != has_btn:
        E("%s/index.html: Play button does not match live flag" % s)
    if (s in LIVE) != ((repo / s / "assets" / "qr.svg").exists() and "/assets/qr.svg" in page):
        E("%s: QR image does not match live flag" % s)
    if not (repo / s / "assets" / "captions.json").exists():
        E("%s: captions.json missing" % s)
    else:
        for c in json.loads((repo / s / "assets" / "captions.json").read_text(encoding="utf-8"))["shots"]:
            if not (repo / s / "assets" / c["file"]).exists():
                E("%s: captions.json lists missing file %s" % (s, c["file"]))
print("pages=%d local-refs=%d errors=%d warnings=%d" % (len(pages), nlinks, len(errs), len(warns)))
for m in errs:
    print("ERROR", m)
for m in warns:
    print("warn ", m)
sys.exit(1 if errs else 0)
