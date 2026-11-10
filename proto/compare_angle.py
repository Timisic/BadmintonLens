"""Same-angle comparison: picks the best matching coach swing from every cleaned video (work/*/segments.json) and
lays coach vs user side by side: 5 phase columns plus N in-between frames per interval, placed at the same fraction
of each interval for both rows (different tempos still line up by phase).

user_clips.json: {"IMG_5515": {"path": ..., "angle": "斜后", "脸": "看不到", "拍位": "画面右", "phases": [引拍侧身, 拍头最低点, 击球点]}}
Usage: python3 compare_angle.py [IMG_5515 ...]"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import clean

HERE = Path(__file__).parent
PH = ["引拍侧身", "拍头最低点", "击球点", "随挥+0.27s", "收拍+0.6s"]
N = 2  # in-between frames per interval
RANK = {"高": 0, "中": 1, "低": 2}

def coach_swings():
    for f in sorted(HERE.glob("work/*/segments.json")):
        meta = json.loads(f.read_text())
        for s in meta["segments"]:
            if s["type"] != "全速正确示范":
                continue
            for w in s["swings"]:
                p = w.get("phases") or {}
                if p.get("usable") and not w.get("reject") and all(p.get(k) for k in PH[:3]):
                    yield {"video": meta["video"], "fps": meta["fps"], "id": f"{f.parent.name}/{w['id']}",
                           "angle": p.get("angle"), "脸": p.get("脸"), "拍位": p.get("拍位"), "conf": p.get("置信度", "低"),
                           "fine": bool(p.get("精标")), "phases": [p[k] for k in PH[:3]]}

def pick(user):
    """Same camera side (脸 + 拍位) is required; same coarse angle preferred; then fine-labeled, confident, high fps."""
    side = [w for w in coach_swings() if (w["脸"], w["拍位"]) == (user["脸"], user["拍位"])]
    if not side:
        return None, f"没有 脸={user['脸']} 拍位={user['拍位']} 的教练示范"
    same = [w for w in side if w["angle"] == user["angle"]]
    note = "" if same else f"没有 {user['angle']} 的示范，用同侧机位 {side[0]['angle']}"
    best = min(same or side, key=lambda w: (not w["fine"], RANK.get(w["conf"], 3), -w["fps"]))
    return best, note

def columns(fps, back, low, hit):
    key = [back, low, hit, hit + round(0.27 * fps), hit + round(0.6 * fps)]
    cols, names = [], []
    for k in range(4):
        a, b = key[k], key[k + 1]
        cols.append(a); names.append(PH[k])
        cols += [round(a + (b - a) * j / (N + 1)) for j in range(1, N + 1)]
        names += [f"{j}/{N + 1}" for j in range(1, N + 1)]
    return cols + [key[4]], names + [PH[4]]

def row(video, fps, phases):
    cols, names = columns(fps, *phases)
    ims = clean.frames_at(video, cols, fps, height=720)
    g = np.asarray(ims).mean(axis=3)
    H, W = g.shape[1:]
    ys, xs = np.nonzero(np.abs(np.diff(g, axis=0)).max(axis=0) > 25)
    if len(xs) < 50:
        return ims, cols, names
    # portrait box: full vertical motion extent, centred on the player's column (median x ignores stray pans/subtitles)
    y0, y1 = np.percentile(ys, [2, 98]); h = (y1 - y0) * 1.25; cy = (y0 + y1) / 2; cx = np.median(xs)
    h = min(h, H); w = min(h * 0.6, W)
    x0 = min(max(0, cx - w / 2), W - w); y0 = min(max(0, cy - h / 2), H - h)
    return [im.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))) for im in ims], cols, names

def build(name, user, out):
    coach, note = pick(user)
    if not coach:
        print(name, note); return
    fps_u = clean.probe(user["path"])[0]
    rows = [(f"教练 {coach['id']}", *row(coach["video"], coach["fps"], coach["phases"]), coach["fps"], coach["phases"][2]),
            (name, *row(user["path"], fps_u, user["phases"]), fps_u, user["phases"][2])]
    names = rows[0][3]
    tw, th = 170, 280
    head = 34 + (24 if note else 0)
    c = Image.new("RGB", (len(names) * tw, head + 2 * (th + 22)), "white"); d = ImageDraw.Draw(c)
    f, fs = ImageFont.truetype(clean.CJK, 18), ImageFont.truetype(clean.CJK, 14)
    for k, n in enumerate(names):
        key = "/" not in n
        if key:
            d.rectangle([k * tw, 0, (k + 1) * tw - 2, 32], fill="#222")
        d.text((k * tw + 6, 7), n, fill="white" if key else "#666", font=f)
    if note:
        d.text((6, 36), "注意：" + note, fill="#c00", font=fs)
    for r, (label, ims, cols, _, fps, hit) in enumerate(rows):
        y = head + r * (th + 22)
        for k, im in enumerate(ims):
            t = im.copy(); t.thumbnail((tw - 4, th))
            c.paste(t, (k * tw + (tw - t.width) // 2, y))
            if "/" not in names[k]:
                d.rectangle([k * tw, y, (k + 1) * tw - 2, y + th - 1], outline="#e33", width=2)
            d.text((k * tw + 4, y + th + 2), f"#{cols[k]} {(cols[k] - hit) / fps:+.2f}s", fill="black", font=fs)
        d.rectangle([0, y, 8 + d.textlength(label, font=fs), y + 20], fill="black")
        d.text((4, y + 2), label, fill="yellow", font=fs)
    c.save(out, quality=85)
    print(name, "<-", coach["id"], coach["angle"], coach["脸"], coach["拍位"], coach["conf"], note)

if __name__ == "__main__":
    clips = json.loads((HERE / "user_clips.json").read_text())
    for u in sys.argv[1:] or clips:
        build(u, clips[u], f"cmp4a_{u}.jpg")
