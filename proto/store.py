"""Where derived files live. Every key is a path relative to ROOT, so the library moves between machines unchanged.

  LENS_STORE   local root (default proto/store). Point it at a mounted share to work on a server's disk directly.
  LENS_REMOTE  rsync target for push / pull, e.g. ubuntu-8-179:badminton-lens/store (SSH key auth, never a password)
  LENS_VIDEOS  root of the source videos. Sources under it are recorded relative, so another machine can resolve them.

  python3 store.py push | pull
"""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(os.environ.get("LENS_STORE") or Path(__file__).parent / "store")
REMOTE = os.environ.get("LENS_REMOTE")
VIDEOS = os.environ.get("LENS_VIDEOS")

def path(key):
    p = ROOT / key
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def dir(key):
    return path(f"{key}/x").parent

def rel_src(video):
    p = Path(video).resolve()
    return str(p.relative_to(Path(VIDEOS).resolve())) if VIDEOS and p.is_relative_to(Path(VIDEOS).resolve()) else str(p)

def src(recorded):
    return Path(recorded) if Path(recorded).is_absolute() else Path(VIDEOS or ".") / recorded

def sync(direction):
    if not REMOTE:
        sys.exit("set LENS_REMOTE, e.g. ubuntu-8-179:badminton-lens/store")
    a, b = (f"{ROOT}/", f"{REMOTE}/") if direction == "push" else (f"{REMOTE}/", f"{ROOT}/")
    ROOT.mkdir(parents=True, exist_ok=True)
    # shortcut: whole-tree rsync with lens.db inside, newest copy wins; fine for one writer, move the db to a
    # server process when two machines label at once
    host, _, remote_dir = REMOTE.partition(":")
    subprocess.run(["ssh", host, "mkdir", "-p", remote_dir], check=True)
    subprocess.run(["rsync", "-a", "--partial", "--update", "--stats", a, b], check=True)

if __name__ == "__main__":
    sync({"push": "push", "pull": "pull"}[sys.argv[1]])
