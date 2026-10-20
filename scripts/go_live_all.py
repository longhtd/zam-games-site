#!/usr/bin/env python3
"""Flip EVERY game whose Google Play page answers HTTP 200 (safe to run on a schedule; does nothing when none changed).

  python scripts/go_live_all.py [--push] [--dry-run]

One commit for all games that went live in this run. Same safeguards as go_live.py (clean tree, checker, restore on failure)."""
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _site import load_games
from go_live import flip

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--push", action="store_true")
ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()
slugs = [g["slug"] for g in load_games()["games"] if not g["live"]]
if not slugs:
    print("every game is already live")
    sys.exit(0)
sys.exit(flip(slugs, force=False, push=a.push, dry=a.dry_run))
