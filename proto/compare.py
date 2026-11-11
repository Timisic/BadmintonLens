"""Coach against you, filmed from the same side, both on one clock: seconds from the hit. The hit is the one moment
that can be found objectively (the racket wrist at its highest), so it is the only anchor; the columns are the same
offsets from it for both rows, and whatever differs between the rows is a real difference in timing or posture.

  python3 compare.py refine     hit time of every swing from the racket wrist in pose.npz -> the pose label layer
  python3 compare.py standard   keep the best coach demo of each camera view, drop the coach's other swings
"""
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np
import clean, db, store

OFFSETS = [-0.6, -0.4, -0.27, -0.17, -0.07, 0, 0.1, 0.23, 0.47]  # stills, denser where the arm is fastest
SPAN = [-0.9, 0.7]  # what synced playback loops over
RANK = list(db.CONFIDENCE)
L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST, L_HIP, R_HIP = 5, 6, 9, 10, 11, 12  # COCO keypoints

def ready(s):
    return bool(s["label"].get("usable")) and "hit" in s["label"]

def demos(lib):
    """Coach swings a user swing may be compared against."""
    return [s for s in lib if s["role"] == "coach" and s["kind"] == "demo" and ready(s)]

def view_key(s):
    return s["label"].get("camera"), s["label"].get("face_visible"), s["label"].get("racket_side")

def pairs(lib):
    """For each of your swings, the coach demos filmed from the same side (face_visible + racket_side), best first:
    same camera, then confident, then high frame rate."""
    coach = demos(lib)
    return {u["id"]: [c["id"] for c in sorted((c for c in coach if view_key(c)[1:] == view_key(u)[1:]),
                                             key=lambda c: (view_key(c) != view_key(u), RANK.index(c["label"].get("confidence", "low")), -c["fps"]))]
            for u in lib if u["role"] == "user" and ready(u)}

@lru_cache(maxsize=None)
def pose(folder):
    z = np.load(folder / "pose.npz")
    video = folder / "play.mp4"
    return z["kpts"], z["boxes"], np.array(clean.frame_pts(video))

def player(s, a, b):
    """Frame times, keypoints [n, 17, 3] and boxes [n, 4] of the swing's player from a to b seconds. A frame where
    nobody stands in the swing's column is nan. None without pose data."""
    folder = store.ROOT / Path(s["sheet"] or "").parent.parent
    if not (folder / "pose.npz").is_file() or not (folder / "play.mp4").is_file():
        return None
    kpts, boxes, pts = pose(folder)
    i, j = np.searchsorted(pts, [a, b])
    j = min(j + 1, len(boxes))
    k, bx = kpts[i:j].astype(float), boxes[i:j].astype(float)
    cx = (bx[..., 0] + bx[..., 2]) / 2
    ok = (bx[..., 2] > bx[..., 0]) & (cx > s["box"][0]) & (cx < s["box"][2])  # people come largest first
    who = ok.argmax(axis=1)
    n = np.arange(len(who))
    k, bx = k[n, who], bx[n, who]
    k[~ok.any(axis=1)] = bx[~ok.any(axis=1)] = np.nan
    return pts[i:j], k, bx

def view(s):
    """Tight box around the player over the compared span, x0 y0 x1 y1 as fractions of the picture. Falls back to the swing's box."""
    p = player(s, s["label"]["hit"] + SPAN[0], s["label"]["hit"] + SPAN[1])
    if p is None or np.isnan(p[2]).all():
        return s["box"]
    b = p[2]
    x0, y0, x1, y1 = np.nanmin(b[:, 0]), np.nanmin(b[:, 1]), np.nanmax(b[:, 2]), np.nanmax(b[:, 3])
    w, h = x1 - x0, y1 - y0
    # the pose box stops at the hand: leave room for the racket, mostly above
    return [max(0, x0 - w * .1), max(0, y0 - h * .3), min(1, x1 + w * .1), min(1, y1 + h * .05)]

def wrist(s):
    """(hit time, peak wrist speed in torso lengths per second) read off the racket wrist near the labeled hit: the
    faster wrist is the racket's, and it is highest at contact. None when the pose is missing or shows no swing there."""
    hit = s["label"]["hit"]
    p = player(s, hit - 0.25, hit + 0.2)
    if p is None or len(p[0]) < 5 or np.isnan(p[1][:, L_WRIST, 0]).mean() > 0.3:
        return None
    t, k, _ = p
    torso = np.nanmedian(np.linalg.norm(k[:, [L_SHOULDER, R_SHOULDER], :2].mean(1) - k[:, [L_HIP, R_HIP], :2].mean(1), axis=1))
    w = k[:, [L_WRIST, R_WRIST], :2]
    speed = np.nanmax(np.linalg.norm(np.gradient(w, t, axis=0), axis=2), axis=0) / torso
    top = int(np.nanargmin(w[:, speed.argmax(), 1]))
    if speed.max() < 5 or top in (0, len(t) - 1):  # a slow hand, or one still rising at the edge: not a hit
        return None
    return float(t[top]), float(speed.max())

def refine():
    with db.connect() as c:
        for s in db.swings(c):
            l = s["label"]
            if "hit" not in l or l["source"] == "human" or not (w := wrist(s)):
                continue
            t = round(w[0], 3)
            # the other phases stay in order around the new hit
            d = {"hit": t, **{k: t for k in ("backswing", "racket_low") if l.get(k, t) > t}, **({"follow": t} if l.get("follow", t) < t else {})}
            db.set_label(c, s["id"], "pose", d)
            if abs(t - l["hit"]) > 0.02:
                print(f"{s['name']} {clean.clock(l['hit'])}: hit {t - l['hit']:+.3f}s")

def standard():
    """A coach video is cut into dozens of swings; comparing needs the best one of each camera view. The rest go,
    except swings a person labeled. Segments and their transcript stay."""
    with db.connect() as c:
        lib = db.swings(c)
        best = {}
        for s in demos(lib):
            score = (s["fps"], -RANK.index(s["label"].get("confidence", "low")), (wrist(s) or (0, 0))[1])
            if view_key(s) not in best or score > best[view_key(s)][0]:
                best[view_key(s)] = score, s
        keep = {s["id"] for _, s in best.values()}
        for _, s in best.values():
            print("keep", s["name"], clean.clock(s["label"]["hit"]), *view_key(s))
        drop = [s["id"] for s in lib if s["role"] == "coach" and s["id"] not in keep and s["label"].get("source") != "human"]
        c.executemany("DELETE FROM label WHERE swing_id=?", [(i,) for i in drop])
        c.executemany("DELETE FROM swing WHERE id=?", [(i,) for i in drop])
        print(f"dropped {len(drop)} coach swings")

if __name__ == "__main__":
    {"refine": refine, "standard": standard}[sys.argv[1]]()
