# games.zamverse.com

Static site (GitHub Pages, branch `main`, no build server). Everything that depends on whether a game is on Google Play
is generated from **one flag per game** in [`games.json`](games.json): `games[].live`.

## Go live (nothing else to do on the site)

When a game's Play page is up, from a clean checkout of `main`:

```
python scripts/go_live.py <slug> --push        # wordlodge | arrowaway | snugcats | pixelpicnic | styledrop | glimmergrove | burrowbuddy
python scripts/go_live_all.py --push           # flips every game whose Play page answers 200 (safe to run on a schedule; no-op otherwise)
```

`go_live.py` refuses unless `https://play.google.com/store/apps/details?id=com.zamverse.<slug>` answers HTTP 200
(`--force` skips that probe: only when the owner explicitly says so), requires a clean working tree, flips the flag,
regenerates the site, runs `scripts/check_site.py` (restores everything if it fails), commits and, with `--push`, pushes.
`--dry-run` only reports.

One flag changes, consistently: the hero "Get it on Google Play" button (instead of the "Coming soon" button), the get-card
with the pre-drawn QR image (`<slug>/assets/qr.svg`), the JSON-LD `installUrl`, the "On Google Play" / "Coming soon" badge on every
game card, the hub sentence ("... coming soon" turns into "All seven games are on Google Play."), the hub's in-app
(`?from=`) Play redirect, `offers.json` (`available`), the Wall of Honor Play links, the Wall of Honor "how it works" line and
the sitemap `lastmod`. "Coming soon" appears nowhere else.

## Files

| File | Purpose |
|---|---|
| `games.json` | The flag (`live`, `liveSince`), name, package, hub tagline and the "What's new" block of each game |
| `<slug>/assets/captions.json` | Gallery: for each screenshot `file`, `alt`, `caption`, `width`, `height` |
| `<slug>/assets/qr.svg` | Real QR code for the plain Play URL (generated, verified to decode) |
| `scripts/apply_state.py` | Regenerates every generated block from the files above (`--check` reports drift). Needs `pip install qrcode` only to redraw QR codes |
| `scripts/check_site.py` | Links, anchors, JSON-LD, meta/OG/canonical, sitemap, Play links/QR/offers vs `games.json`, generated-state drift |
| `scripts/go_live.py`, `scripts/go_live_all.py` | See above |

Never hand-edit the regions between `<!--gl:...-->` markers or `offers.json`, `sitemap.xml`, the hub card blurbs: edit `games.json` /
`captions.json` and run `python scripts/apply_state.py`.

## New screenshots (drop-in)

1. Put the new `shotN.webp` files into `<slug>/assets/` (delete the old ones that are no longer listed).
2. Edit `<slug>/assets/captions.json` (one entry per screenshot, 3 words or fewer for the caption is the store rule; `alt` describes the picture).
3. `python scripts/apply_state.py && python scripts/check_site.py`, commit, push. The gallery, lightbox and JSON-LD screenshot list all follow.

## New release notes

Edit `games[].whatsNew` in `games.json`, then `python scripts/apply_state.py`.

## Checks

`python scripts/check_site.py` must print `errors=0`. It also fails when the generated pages no longer match `games.json`.
