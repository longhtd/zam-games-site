#!/usr/bin/env python3
"""Flip games to LIVE once their Google Play page answers HTTP 200.

  python scripts/go_live.py <slug> [<slug> ...] [--push] [--dry-run] [--force] [--no-commit]

What it does, in order:
  1. refuses unless the working tree is clean (so the commit holds only the flip)
  2. for each slug: refuses unless https://play.google.com/store/apps/details?id=com.zamverse.<slug> answers 200
     (--force skips this probe: ONLY when the owner explicitly says so)
  3. sets games[].live=true and liveSince in games.json, runs scripts/apply_state.py (button, QR, JSON-LD, badges,
     hub sentence, from-app redirect, offers.json, Wall of Honor links, sitemap lastmod)
  4. runs scripts/check_site.py; on any error it restores every file and exits 1
  5. commits "web: <names> now live on Google Play" (explicit paths) and, with --push, pushes the current branch.
Nothing else is manual."""
import argparse, datetime, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _site import REPO, load_games, save_games, play_url, probe_play, run, py


def flip(slugs, force=False, push=False, dry=False, commit=True, strict=False):
    d = load_games()
    by = {g["slug"]: g for g in d["games"]}
    todo, refused = [], 0
    for s in slugs:
        if s not in by:
            sys.exit("unknown slug %r (known: %s)" % (s, ", ".join(by)))
        g = by[s]
        if g["live"]:
            print("%s: already live, nothing to do" % s)
            continue
        ok, why = probe_play(play_url(d, g))
        print("%s: Google Play says %s" % (s, why))
        if not ok and not force:
            print("  -> refused: the store page is not live yet (use --force only if the owner says so)")
            refused += 1
            continue
        todo.append(g)
    if not todo:
        return 2 if (strict and refused) else 0
    names = [g["name"] for g in todo]
    if dry:
        print("dry run: would flip " + ", ".join(names))
        return 0
    if commit and run("git", "status", "--porcelain").stdout.strip():
        sys.exit("working tree is not clean; commit or stash first (the flip commit must contain only the flip)")
    today = datetime.date.today().isoformat()
    for g in todo:
        g["live"] = True
        g["liveSince"] = today
    save_games(d)
    p = py("apply_state.py", "--touch", ",".join(g["slug"] for g in todo))
    print(p.stdout.strip() or p.stderr.strip())
    c = py("check_site.py")
    print(c.stdout.strip() or c.stderr.strip())
    if p.returncode != 0 or c.returncode != 0:
        run("git", "checkout", "--", ".", check=False)
        sys.exit("checks failed, everything restored; nothing was committed")
    if not commit:
        print("flipped (not committed): " + ", ".join(names))
        return 0
    paths = [l[3:].strip().strip('"') for l in run("git", "status", "--porcelain").stdout.splitlines()]
    run("git", "add", "--", *paths)
    msg = "web: %s now live on Google Play (store button, QR, install URL, badges and hub copy switched on from games.json)" % ", ".join(names)
    run("git", "commit", "-q", "-m", msg + "\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>")
    print("committed: " + msg)
    if push:
        r = run("git", "push", "origin", "HEAD", check=False)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            sys.exit("push failed; the commit is local")
        print("pushed")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="skip the Google Play probe (owner's explicit say-so only)")
    ap.add_argument("--no-commit", action="store_true")
    a = ap.parse_args()
    sys.exit(flip(a.slugs, a.force, a.push, a.dry_run, not a.no_commit, strict=True))
