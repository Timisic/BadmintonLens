"""Coach against you, filmed from the same side, both on one clock: seconds from the hit. The hit is the one moment
that can be found objectively (the racket wrist at its highest), so it is the only anchor; the columns are the same
offsets from it for both rows, and whatever differs between the rows is a real difference in timing or posture.

  python3 compare.py refine     read every swing off pose.npz -> the pose label layer: is it a swing, the hit, the camera
  python3 compare.py standard   keep the best coach demo of each video and camera, drop the coach's other swings
"""
import warnings
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np
import clean, db, store

OFFSETS = [-0.6, -0.4, -0.25, -0.12, 0, 0.12, 0.3]  # stills, denser where the arm is fastest
SPAN = [-0.9, 0.7]  # what synced playback loops over
NOSE, L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST, L_HIP, R_HIP = 0, 5, 6, 9, 10, 11, 12  # COCO keypoints

def ready(s):
    return bool(s["label"].get("usable")) and "hit" in s["label"]

def demos(lib):
    """Coach swings a user swing may be compared against."""
    return [s for s in lib if s["role"] == "coach" and s["kind"] == "demo" and ready(s)]

def pairs(lib):
    """For each of my swings, the coach demos filmed from the same place, sharpest video first."""
    coach = sorted(demos(lib), key=lambda c: -c["fps"])
    return {u["id"]: [c["id"] for c in coach if c["label"].get("camera") == u["label"].get("camera")]
            for u in lib if u["role"] == "user" and ready(u)}

def pose(folder):
    # keyed on the files' mtimes: the API outlives a `store.py pull` that brings a new pose.npz or play.mp4
    return _pose(folder, *((folder / f).stat().st_mtime_ns for f in ("pose.npz", "play.mp4")))

@lru_cache(maxsize=256)
def _pose(folder, *_):
    z = np.load(folder / "pose.npz")
    return z["kpts"], z["boxes"], np.array(clean.frame_pts(folder / "play.mp4"))

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

def torso(k):
    """Shoulders to hips, the yardstick that makes two people filmed at different sizes comparable."""
    return np.nanmedian(np.linalg.norm(k[:, [L_SHOULDER, R_SHOULDER], :2].mean(1) - k[:, [L_HIP, R_HIP], :2].mean(1), axis=1))

def reading(s, hand=None):
    """What the pose shows of a swing, None when it shows no fast hand:
    hit       when the racket wrist is highest. The faster wrist is the racket's, unless `hand` says which it is.
    speed     its peak, in torso lengths per second
    overhead  a real overhead swing: fast, and the hand passes above the head
    hand      0 left, 1 right
    camera    where the camera stands. Seen from the left, a right-hander shows their back while preparing and
              their chest after the hit; from the right it is the reverse; front and back show one side throughout."""
    l = s["label"]
    # Always the same window, so reading twice gives the same answer. Only a hit a person set narrows it.
    a, b = (l["hit"] - 0.25, l["hit"] + 0.2) if l.get("source") == "human" and "hit" in l else (s["t0"] - 0.3, s["t1"] + 0.3)
    p = player(s, a - 0.7, b + 0.5)
    if p is None or len(p[0]) < 5:
        return None
    t, k, _ = p
    raw, unit = k[:, [L_WRIST, R_WRIST], :2], torso(k)
    # The pose jumps for a frame now and then. A median over a few frames drops the jump and keeps the swing.
    def calm(n):
        pad = np.pad(raw, ((n // 2, n // 2), (0, 0), (0, 0)), mode="edge")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # a joint unseen for that long stays unseen
            return np.nanmedian(np.stack([pad[i:i + len(raw)] for i in range(n)]), axis=0)
    speed = np.linalg.norm(np.gradient(calm(5), t, axis=0), axis=2) / unit
    # the top is read from the frames as they are, so it is not blunted, minus the ones that jumped
    w = np.where(np.abs(raw - calm(3)) > 0.5 * unit, np.nan, raw)
    speed[(t < a) | (t > b)] = np.nan
    if np.isnan(speed).mean() > 0.9 or not np.nanmax(speed) >= 5:
        return None
    if hand is None:
        hand = int(np.nanmax(speed, axis=0).argmax())
    if np.isnan(speed[:, hand]).all():
        return None
    fast = t[np.nanargmax(speed[:, hand])]
    y = np.where((t >= fast - 0.2) & (t <= fast + 0.15), w[:, hand, 1], np.nan)
    top = int(np.nanargmin(y))
    def chest(a, b):  # 1 facing the camera, -1 facing away: the left shoulder is on the right of the picture when facing it
        x = (k[:, L_SHOULDER, 0] - k[:, R_SHOULDER, 0])[(t >= t[top] + a) & (t <= t[top] + b)]
        return 0 if np.isnan(x).all() else np.sign(np.nanmedian(x))
    camera = {(1, 1): "front", (-1, -1): "back", (-1, 1): "left", (1, -1): "right"}.get((chest(-0.6, -0.3), chest(0.15, 0.4)))
    if hand == 0:  # a left-hander is a right-hander in a mirror
        camera = {"left": "right", "right": "left"}.get(camera, camera)
    peak = float(np.nanmax(speed[:, hand]))
    return {"hit": float(t[top]), "speed": peak, "hand": hand, "camera": camera,
            "overhead": bool(peak >= 15 and (k[top, NOSE, 1] - w[top, hand, 1]) / unit > 0.3)}

def racket_hand(swings):
    """The hand most of one video's swings are read with. A single swing can be misread: the other hand is raised
    high too, and from behind the pose swaps the two sides."""
    hands = [r["hand"] for s in swings if (r := reading(s)) and r["overhead"]]
    return max(set(hands), key=hands.count) if hands else None

def refine():
    with db.connect() as c:
        last, new = {}, []
        every = db.swings(c)
        hands = {v: racket_hand([s for s in every if s["video_id"] == v]) for v in {s["video_id"] for s in every}}
        for s in every:
            l, r = s["label"], reading(s, hands[s["video_id"]])
            d = {}
            if r and ("hit" in l or r["overhead"]):
                d = {"hit": round(r["hit"], 3), "camera": r["camera"]}
            if l.get("source") in (None, "pose"):  # nobody judged it: an overhead swing is one, once
                d["usable"] = "hit" in d and abs(d["hit"] - last.get(s["video_id"], -9)) > 0.3
            if d.get("usable", l.get("usable")) and "hit" in d:
                last[s["video_id"]] = d["hit"]
            new.append((s, d))
        # my own videos are one phone on one tripod: a swing read differently from the rest was misread
        for video in {s["video_id"] for s, _ in new if s["role"] == "user"}:
            seen = [d["camera"] for s, d in new if s["video_id"] == video and d.get("camera")]
            for s, d in new:
                if s["video_id"] == video and "camera" in d:
                    d["camera"] = max(set(seen), key=seen.count)
        for s, d in new:
            if d:
                db.set_label(c, s["id"], "pose", d)
            print(s["name"], clean.clock(s["t0"]), d or "no pose")

def standard():
    """A coach video is cut into dozens of swings; comparing needs the best one from each camera. The rest go,
    except swings a person labeled. Segments and their transcript stay."""
    with db.connect() as c:
        lib = db.swings(c)
        best = {}
        for s in demos(lib):
            key, score = (s["name"], s["label"].get("camera")), (reading(s) or {}).get("speed", 0)
            if key not in best or score > best[key][0]:
                best[key] = score, s
        keep = {s["id"] for _, s in best.values()}
        for key, (_, s) in best.items():
            print("keep", *key, clean.clock(s["label"]["hit"]))
        drop = [s["id"] for s in lib if s["role"] == "coach" and s["id"] not in keep and s["label"].get("source") != "human"]
        c.executemany("DELETE FROM label WHERE swing_id=?", [(i,) for i in drop])
        c.executemany("DELETE FROM swing WHERE id=?", [(i,) for i in drop])
        print(f"dropped {len(drop)} coach swings")

if __name__ == "__main__":
    {"refine": refine, "standard": standard}[sys.argv[1]]()
