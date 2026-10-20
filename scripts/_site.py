"""Shared helpers for the games.zamverse.com maintenance scripts (stdlib only)."""
import json, subprocess, sys, urllib.request, urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOST = "https://games.zamverse.com"


def load_games():
    d = json.loads((REPO / "games.json").read_text(encoding="utf-8"))
    return d


def save_games(d):
    (REPO / "games.json").write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def play_url(d, g, referrer=False):
    u = d["playBase"] + g["package"]
    return u + "&referrer=" + d["referrer"] if referrer else u


def probe_play(url, timeout=25):
    """Return (ok, detail). ok only when Google Play answers HTTP 200 and we stay on play.google.com."""
    req = urllib.request.Request(url + "&hl=en", headers={"User-Agent": "Mozilla/5.0 (go_live check)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            final = r.geturl()
            if r.status == 200 and "play.google.com/store/apps/details" in final:
                return True, "HTTP 200"
            return False, "HTTP %s at %s" % (r.status, final)
    except urllib.error.HTTPError as e:
        return False, "HTTP %s" % e.code
    except Exception as e:  # network trouble must never flip a game live
        return False, "request failed: %s" % e


def run(*args, check=True, capture=True):
    p = subprocess.run(list(args), cwd=REPO, text=True, capture_output=capture)
    if check and p.returncode != 0:
        sys.exit("command failed: %s\n%s%s" % (" ".join(args), p.stdout or "", p.stderr or ""))
    return p


def py(script, *args):
    return run(sys.executable, str(REPO / "scripts" / script), *args, check=False)
