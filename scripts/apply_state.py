#!/usr/bin/env python3
"""Regenerate every game-state-dependent part of the site from games.json (the ONE flag per game is games[].live).

  python scripts/apply_state.py            write changes
  python scripts/apply_state.py --check    exit 1 if any file differs from what games.json says (drift)
  python scripts/apply_state.py --touch wordlodge,arrowaway   also bump that game's sitemap <lastmod> to today

Generated, per game:  hero Play button / "Coming soon" button, get-card with QR image, JSON-LD installUrl,
badges on every game card, hub status sentence, hub from-app Play redirect (LIVE map), offers.json "available",
Wall of Honor Play links, sitemap, <slug>/assets/qr.svg, and (from <slug>/assets/captions.json) the screenshot
gallery + JSON-LD screenshot list, plus the "What's new" block from games.json.
Idempotent. Needs: pip install qrcode (only to (re)draw the QR SVGs)."""
import argparse, datetime, html, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _site import REPO, HOST, load_games, play_url

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
ap.add_argument("--touch", default="")
args = ap.parse_args()
TODAY = datetime.date.today().isoformat()

D = load_games()
G = D["games"]
BY = {g["slug"]: g for g in G}
ORDER = [g["slug"] for g in G]
NUM = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
esc = lambda s: html.escape(s, quote=True)

changed = []


def put(rel, text):
    p = REPO / rel
    old = p.read_text(encoding="utf-8") if p.exists() else None
    if old != text:
        changed.append(rel)
        if not args.check:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")


def region(t, name, new, rel):
    pat = re.compile(r"<!--gl:%s-->.*?<!--/gl:%s-->" % (name, name), re.S)
    if not pat.search(t):
        sys.exit("%s: marker gl:%s missing" % (rel, name))
    return pat.sub(lambda m: "<!--gl:%s-->%s<!--/gl:%s-->" % (name, new, name), t, count=1)


# ------------------------------------------------------------------ QR (real, scannable, drawn ahead of time)
def qr_svg(url, label):
    import qrcode
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0, box_size=1)
    q.add_data(url)
    q.make(fit=True)
    m = q.get_matrix()
    n = len(m)
    b = 3  # quiet zone (the .qr box adds white padding on top)
    d = []
    for y, row in enumerate(m):
        x = 0
        while x < n:
            if row[x]:
                s = x
                while x < n and row[x]:
                    x += 1
                d.append("M%d,%dh%dv1h-%dz" % (s + b, y + b, x - s, x - s))
            else:
                x += 1
    size = n + 2 * b
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" shape-rendering="crispEdges" role="img" aria-label="%s">'
            '<rect width="%d" height="%d" fill="#fff"/><path fill="#1b1410" d="%s"/></svg>\n') % (size, size, esc(label), size, size, "".join(d))


for g in G:
    rel = "%s/assets/qr.svg" % g["slug"]
    try:
        put(rel, qr_svg(play_url(D, g), "QR code: open %s on Google Play" % g["name"]))
    except ImportError:
        if not (REPO / rel).exists():
            sys.exit("pip install qrcode  (needed to draw %s)" % rel)


# ------------------------------------------------------------------ per-game blocks
def hero(g):
    if g["live"]:
        return '<a class="btn primary" href="%s" rel="noopener">Get it on Google Play</a>' % esc(play_url(D, g, True))
    return '<span class="btn soon" role="status">Coming soon to Google Play</span>'


def getcard(g):
    s, n = g["slug"], g["name"]
    if g["live"]:
        return ('<aside class="getcard" id="get"><h3>Get %s</h3><div class="qr"><img src="/%s/assets/qr.svg" alt="QR code: open %s on Google Play" width="174" height="174"></div>'
                '<p class="qrnote">Scan with your phone to open %s on Google Play.</p><div class="cta col"><a class="btn primary" href="%s" rel="noopener">Get it on Google Play</a></div></aside>'
                % (esc(n), s, esc(n), esc(n), esc(play_url(D, g, True))))
    return ('<aside class="getcard" id="get"><h3>%s is coming soon</h3><p class="qrnote">Not on Google Play yet. The store link and a scan-to-install code appear here the day it launches.</p>'
            '<div class="cta col"><span class="btn soon" role="status">Coming soon to Google Play</span><a class="btn ghost" href="/">See all Zamverse games</a></div></aside>' % esc(n))


def shots(g, caps):
    out = []
    for c in caps["shots"]:
        out.append('<figure><div class="phone"><img src="/%s/assets/%s" alt="%s" width="%d" height="%d" loading="lazy" style="aspect-ratio:%d/%d;height:auto"></div><figcaption>%s</figcaption></figure>'
                   % (g["slug"], c["file"], esc(c["alt"]), c.get("width", 540), c.get("height", 960), c.get("width", 540), c.get("height", 960), esc(c["caption"])))
    return "".join(out)


def notes(g):
    w = g.get("whatsNew") or {}
    if not w.get("items"):
        return ""
    return ('<section class="whatsnew" id="whatsnew"><div class="wrap"><h2>%s</h2><p class="notesub">%s</p><ul class="notes">%s</ul></div></section>\n'
            % (esc(w.get("title", "What's new")), esc(w.get("sub", "")), "".join("<li>%s</li>" % esc(i) for i in w["items"])))


def jsonld(t, g, caps):
    pat = re.compile(r'(<script type="application/ld\+json">)(\{"@context":"https://schema.org","@type":"VideoGame".*?)(</script>)', re.S)
    m = pat.search(t)
    if not m:
        return t
    j = json.loads(m.group(2))
    j.pop("downloadUrl", None)
    j.pop("installUrl", None)
    if g["live"]:
        j["installUrl"] = play_url(D, g, True)
    j["screenshot"] = ["%s/%s/assets/%s" % (HOST, g["slug"], c["file"]) for c in caps["shots"]]
    return t[:m.start(2)] + json.dumps(j, ensure_ascii=False, separators=(",", ":")) + t[m.end(2):]


# ------------------------------------------------------------------ cards (hub + "More from Zamverse")
def cards(t):
    m = re.search(r'(<div class="ggrid">)((?:<a class="gcard".*?</a>)+)(</div>)', t, re.S)
    if not m:
        return t
    items = re.findall(r'<a class="gcard".*?</a>', m.group(2), re.S)

    def slug_of(a):
        return re.search(r'href="/([a-z]+)/', a).group(1)

    def fix(a):
        s = slug_of(a)
        g = BY[s]
        a = re.sub(r'<span class="gbadge[^"]*">[^<]*</span>', "", a)
        b = '<span class="gbadge%s">%s</span>' % ("" if g["live"] else " soon", "On Google Play" if g["live"] else "Coming soon")
        a = a.replace('<div class="gshade"></div>', '<div class="gshade"></div>' + b, 1)
        a = re.sub(r'<h3>[^<]*</h3><p>[^<]*</p>', lambda mm: "<h3>%s</h3><p>%s</p>" % (esc(g["name"]), esc(g["tagline"])), a, count=1)
        return a
    items = [fix(a) for a in sorted(items, key=lambda a: ORDER.index(slug_of(a)))]
    return t[:m.start(2)] + "".join(items) + t[m.end(2):]


def status_line():
    live = [g for g in G if g["live"]]
    k = len(G) - len(live)
    if not live:
        return "Our games are coming soon to Google Play."
    if k == 0:
        return "All %s games are on Google Play." % NUM.get(len(G), len(G))
    names = live[0]["name"] if len(live) == 1 else ", ".join(x["name"] for x in live[:-1]) + " and " + live[-1]["name"]
    return "%s %s on Google Play now. The other %s coming soon." % (
        names, "is" if len(live) == 1 else "are", "game is" if k == 1 else NUM.get(k, k) + " games are")


# ------------------------------------------------------------------ pages
for g in G:
    rel = "%s/index.html" % g["slug"]
    t = (REPO / rel).read_text(encoding="utf-8")
    caps = json.loads((REPO / g["slug"] / "assets" / "captions.json").read_text(encoding="utf-8"))
    t = region(t, "hero", hero(g), rel)
    t = region(t, "get", getcard(g), rel)
    t = region(t, "shots", shots(g, caps), rel)
    t = region(t, "notes", notes(g), rel)
    t = jsonld(t, g, caps)
    t = cards(t)
    put(rel, t)

rel = "index.html"
t = (REPO / rel).read_text(encoding="utf-8")
t = cards(t)
t = re.sub(r'(<p class="gstatus" id="games-status">)[^<]*(</p>)', lambda m: m.group(1) + esc(status_line()) + m.group(2), t, count=1)
live_js = "var LIVE = {%s};" % ",".join("'%s':1" % g["slug"] for g in G if g["live"])
t, n = re.subn(r"var LIVE = \{[^}]*\};", live_js, t, count=1)
if n != 1:
    sys.exit("index.html: var LIVE missing")
put(rel, t)

rel = "honor/index.html"
t = (REPO / rel).read_text(encoding="utf-8")
how = ("Get any Zamverse game on Google Play. Every game is free to play." if all(g["live"] for g in G)
       else "Pick a Zamverse game. Every game is free to play, and more are coming to Google Play soon.")
put(rel, region(t, "honorhow", how, rel))

rel = "assets/honor-wall.js"
t = (REPO / rel).read_text(encoding="utf-8")
t, n = re.subn(r"var LIVE_SLUGS = \{[^}]*\};", "var LIVE_SLUGS = {%s};" % ", ".join("%s: 1" % g["slug"] for g in G if g["live"]), t, count=1)
if n != 1:
    sys.exit("honor-wall.js: LIVE_SLUGS missing")
put(rel, t)

# offers.json (same "available" key the apps read)
od = json.loads((REPO / "offers.json").read_text(encoding="utf-8"))
for o in od["offers"]:
    g = BY.get(o.get("id"))
    if g:
        o["body"] = g["tagline"]
        o["url"] = play_url(D, g)
        if g["live"]:
            o.pop("available", None)
        else:
            o["available"] = False
od["offers"].sort(key=lambda o: ORDER.index(o["id"]) if o.get("id") in BY else 99)
put("offers.json", json.dumps(od, indent=2, ensure_ascii=False) + "\n")

# sitemap (keeps each URL's lastmod; --touch bumps the named games' main page)
old = {}
sp = REPO / "sitemap.xml"
if sp.exists():
    for loc, lm in re.findall(r"<loc>([^<]+)</loc><lastmod>([^<]+)</lastmod>", sp.read_text(encoding="utf-8")):
        old[loc] = lm
touch = {HOST + "/%s/" % s for s in args.touch.split(",") if s}
urls = [("/", "1.0"), ("/about/", "0.4"), ("/honor/", "0.6")] + [("/%s/" % s, "0.9") for s in ORDER]
for sub in ("support", "privacy", "terms", "delete-account"):
    urls += [("/%s/%s/" % (s, sub), "0.3") for s in ORDER if (REPO / s / sub / "index.html").exists()]
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, pr in urls:
    full = HOST + u
    lm = TODAY if full in touch else old.get(full, TODAY)
    sm.append("  <url><loc>%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>" % (full, lm, pr))
sm.append("</urlset>")
put("sitemap.xml", "\n".join(sm) + "\n")

if args.check:
    if changed:
        print("DRIFT: these files do not match games.json:\n  " + "\n  ".join(sorted(set(changed))))
        print("Run: python scripts/apply_state.py")
        sys.exit(1)
    print("state ok: pages match games.json")
else:
    print("updated %d file(s)" % len(set(changed)) if changed else "already up to date")
    for c in sorted(set(changed)):
        print("  " + c)
