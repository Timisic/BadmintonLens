"""Same-angle comparison: for each of your labeled swings, pick the best matching coach demo from the library and lay
coach over you: 5 phase columns plus N in-between frames per interval, placed at the same fraction of each interval
for both rows, so different tempos still line up by phase. Every frame is captioned with its time from the hit.

  python3 compare.py [name ...]     your video names (substring); default all -> store/compare/<name>_<time>.jpg
"""
import bisect, os, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import clean, db, store

CJK = os.environ.get("LENS_FONT", "/System/Library/Fonts/STHeiti Medium.ttc")  # column heads are Chinese
N = 2  # in-between frames per interval
AFTER = (0.27, 0.6)  # the follow-through columns sit at fixed times after the hit, the same for both rows
COLS = [db.PHASE["backswing"], db.PHASE["racket_low"], db.PHASE["hit"], "随挥", "收拍"]
RANK = list(db.CONFIDENCE)

def ready(s):
    return s["label"].get("usable") and all(k in s["label"] for k in ("backswing", "racket_low", "hit"))

def demos(lib):
    """Coach swings a user swing may be compared against."""
    return [s for s in lib if s["role"] == "coach" and s["kind"] == "demo" and ready(s)]

def pick(user, coach):
    """Same camera side (face_visible + racket_side) is required; same camera preferred; then confident, high fps."""
    key = lambda s: (s["label"].get("face_visible"), s["label"].get("racket_side"))
    side = [s for s in coach if key(s) == key(user)]
    if not side:
        return None, "库里没有同侧机位的教练示范"
    same = [s for s in side if s["label"].get("camera") == user["label"].get("camera")]
    best = min(same or side, key=lambda s: (RANK.index(s["label"].get("confidence", "low")), -s["fps"]))
    cam = lambda s: db.CAMERA.get(s["label"].get("camera"), "未标")  # camera is optional in a label
    return best, "" if same else f"没有{cam(user)}机位的示范，用同侧的{cam(best)}"

def times(label):
    key = [label["backswing"], label["racket_low"], label["hit"], label["hit"] + AFTER[0], label["hit"] + AFTER[1]]
    out = []
    for a, b in zip(key, key[1:]):
        out += [a + (b - a) * j / (N + 1) for j in range(N + 1)]
    return out + [key[-1]]

def view(s):
    """Tight box around the player over the compared frames, x0 y0 x1 y1 as fractions of the picture. Falls back to the swing's box."""
    f = store.ROOT / Path(s["sheet"] or "").parent.parent / "pose.npz"
    if not f.is_file():
        return s["box"]
    ts = times(s["label"])
    # shortcut: frame index from t * fps, which drifts on variable frame rate video; fine for a crop, use clean.frame_pts if it ever cuts a limb
    b = np.load(f)["boxes"][round(ts[0] * s["fps"]):round(ts[-1] * s["fps"]) + 1].astype(float)
    cx = (b[..., 0] + b[..., 2]) / 2
    ok = (b[..., 2] > b[..., 0]) & (cx > s["box"][0]) & (cx < s["box"][2])  # people sorted largest first; keep those in the swing's column
    b = np.array([p[m][0] for p, m in zip(b, ok) if m.any()])
    if not len(b):
        return s["box"]
    x0, y0, x1, y1 = b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()
    w, h = x1 - x0, y1 - y0
    # the pose box stops at the hand: leave room for the racket, mostly above
    return [max(0, x0 - w * .1), max(0, y0 - h * .3), min(1, x1 + w * .1), min(1, y1 + h * .05)]

def row(s):
    video = str(store.src(s["src"]))
    pts = clean.frame_pts(video)
    near = lambda t: min((j for j in (bisect.bisect_left(pts, t) - 1, bisect.bisect_left(pts, t)) if 0 <= j < len(pts)),
                         key=lambda j: abs(pts[j] - t))
    idx = [near(t) for t in times(s["label"])]
    ims = clean.frames_at(video, idx, s["fps"], height=720)
    shown = [pts[i] - s["label"]["hit"] for i in idx]
    g = np.asarray(ims).mean(axis=3)
    H, W = g.shape[1:]
    ys, xs = np.nonzero(np.abs(np.diff(g, axis=0)).max(axis=0) > 25)
    if len(xs) < 50:
        return ims, shown
    # portrait box: full vertical motion extent, centred on the player's column (median x ignores stray pans/subtitles)
    y0, y1 = np.percentile(ys, [2, 98]); h = min((y1 - y0) * 1.25, H); cy = (y0 + y1) / 2; cx = np.median(xs)
    w = min(h * 0.6, W)
    x0 = min(max(0, cx - w / 2), W - w); y0 = min(max(0, cy - h / 2), H - h)
    return [im.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))) for im in ims], shown

def build(user, coach):
    best, note = pick(user, coach)
    if not best:
        print(user["name"], note); return
    rows = [(f"{db.ROLE[s['role']]} · {s['name']} {clean.clock(s['label']['hit'])}", *row(s)) for s in (best, user)]
    n, tw, th = 4 * (N + 1) + 1, 170, 280
    head = 34 + (24 if note else 0)
    c = Image.new("RGB", (n * tw, head + 2 * (th + 22)), "white"); d = ImageDraw.Draw(c)
    f, fs = ImageFont.truetype(CJK, 18), ImageFont.truetype(CJK, 14)
    for k in range(0, n, N + 1):
        d.rectangle([k * tw, 0, (k + 1) * tw - 2, 32], fill="#222")
        d.text((k * tw + 6, 7), COLS[k // (N + 1)], fill="white", font=f)
    if note:
        d.text((6, 36), "注意：" + note, fill="#c00", font=fs)
    for r, (label, ims, shown) in enumerate(rows):
        y = head + r * (th + 22)
        for k, im in enumerate(ims):
            t = im.copy(); t.thumbnail((tw - 4, th))
            c.paste(t, (k * tw + (tw - t.width) // 2, y))
            if k % (N + 1) == 0:
                d.rectangle([k * tw, y, (k + 1) * tw - 2, y + th - 1], outline="#e33", width=2)
            d.text((k * tw + 4, y + th + 2), f"{shown[k]:+.2f}s", fill="black", font=fs)
        d.rectangle([0, y, 8 + d.textlength(label, font=fs), y + 20], fill="black")
        d.text((4, y + 2), label, fill="yellow", font=fs)
    out = store.path(f"compare/{user['name']}_{clean.stamp(user['id'])}.jpg")
    c.save(out, quality=85)
    print(f"{user['name']} <- {best['name']} {clean.clock(best['label']['hit'])} {note} -> {out}")

if __name__ == "__main__":
    lib = db.swings(db.connect())
    coach = demos(lib)
    for u in lib:
        if u["role"] == "user" and ready(u) and (not sys.argv[1:] or any(a in u["name"] for a in sys.argv[1:])):
            build(u, coach)
