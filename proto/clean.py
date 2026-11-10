"""Video cleaning pipeline: a coach video or your own clip -> swings with labeled phases in the library (db.py).

The code spends no model tokens. The vision work is done by Claude subagents that read the *_task.md files and write
the *_labels.json files (see .claude/skills/clean-coach-video). Every stage caches in store/<video_id>/ and is safe
to re-run.

  python3 clean.py prep   <video> [--user]   transcript + shots + tiles + sheets       -> classify_task.md
  python3 clean.py swings <video>            segments, swing candidates, swing sheets   -> phase_task.md
  python3 clean.py fine   <video>            every-frame sheets around the hit          -> fine_task.md
  python3 clean.py ingest <video>            validate the labels, write the library and preview clips

Sheets number their tiles with small frame offsets (#0, #2, ...). Labels answer with those numbers and ingest turns
them into seconds, so frame numbers stay inside the cache.
"""
import json, os, re, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import db, store

STEP = 3.0                      # seconds per tile
TW, TH = 384, 216               # tile size (scan resolution)
RACKET_HEIGHT = {"below_waist": 0, "shoulder_to_head": 1, "above_head": 2}

def opts(table):
    return " / ".join(f"{k}（{v}）" for k, v in table.items())

CLASSIFY = f"""你在整理羽毛球教练的杀球教学视频。图中是按时间排列的编号缩略图（左上：#编号 时间），
每格代表约{STEP:g}秒，取该时段画面动作最剧烈的一帧。同名 .txt 是每格对应时段的字幕（可能为空）。
对每一格判断 kind，填英文值：{opts(db.KIND)}
- demo：教练以正常速度做出完整杀球挥拍，字幕没有否定意味；
- wrong_demo：字幕有"不可以/不要/错误/最多人做的/很奇怪"等否定，或在模仿学员常见错误；
- slow_demo：放慢或停顿着讲解某一段动作；talk：主要在说话，没有完整挥拍；
- match：比赛或对打画面；ad：产品推广；other：片头片尾、字幕卡等。
判断示范对错时以字幕为准，画面相似时不要猜。
只输出 JSON：{{"tiles":[{{"k":编号,"kind":"","note":"≤15字，可省略"}}]}}"""

PHASES = f"""这是一次杀球挥拍的连续帧网格（每格左上角 #编号 是帧序号，按时间顺序，相邻格间隔数帧）。帧号一律填格子上的编号。
- backswing（引拍侧身）：侧身架拍完成的那一帧。
- racket_low（拍头最低点）：引拍后拍头在背后下沉到最低的那一帧。
- hit（击球点）：没球时指拍面挥到最高、最前、速度最快的那一帧。
- follow（随挥收拍）：挥拍结束、拍子收到身前的那一帧。
  顺序必须是 backswing < racket_low < hit < follow，不在图里的填 null。
- racket_height：网格每行 4 格，逐行填拍头大多在 above_head（头顶以上）/ shoulder_to_head（肩到头之间）/ below_waist（腰以下），共 4 项。
- usable：这组帧里没有完整的杀球挥拍（只是举拍到准备姿势、走动、比划、半截动作）填 false。
- camera：拍摄者相对球员的位置，以引拍侧身时为准。{opts(db.CAMERA)}
- face_visible：只看第一行。看得到眼睛和鼻子填 true，只看到后脑勺或头发填 false。
- racket_side：只看第一行。球拍（拍框）在画面里位于身体的 left 还是 right，以看图的人的左右为准，不是球员本人的。
- confidence：high / medium / low。
只输出 JSON：{{"racket_height":["","","",""],"usable":true,"camera":"","face_visible":true,"racket_side":"","backswing":null,"racket_low":null,"hit":null,"follow":null,"confidence":"","note":"一句话"}}"""

FINE = """这是同一次杀球在击球前后的逐帧网格（每格左上角 #编号 是帧序号，相邻格相差 1 帧，编号和挥拍图是同一套）。
没球时 hit（击球点）指拍面挥到最高、最前、速度最快的那一帧；racket_low（拍头最低点）指引拍后拍头在背后下沉到最低的那一帧（不在本网格内填 null）。
只输出 JSON：{"racket_low": 编号或null, "hit": 编号}"""


def font(size):
    return ImageFont.load_default(size)  # sheets carry ASCII only, so they render the same on the Linux server

def probe(video):
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=r_frame_rate:format=duration", "-of", "json", video],
                                  capture_output=True, text=True, check=True).stdout)
    n, d = s["streams"][0]["r_frame_rate"].split("/")
    return float(n) / float(d), float(s["format"]["duration"])

def load(d, name):
    return json.loads((d / name).read_text())

def dump(d, name, obj):
    (d / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1))

def cache(video):
    d = store.dir(db.video_id(video))
    if not (d / "tiles.json").exists():
        sys.exit(f"run `clean.py prep` on {video} first")
    return d, load(d, "tiles.json")

def clock(t):
    return f"{int(t) // 60}:{int(t) % 60:02d}"


# ---------- prep ----------

def parse_srt(path):
    out = []
    for block in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8-sig").strip()):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)\s*\n(.*)", block, re.S)
        if m:
            g = [int(x) for x in m.groups()[:8]]
            out.append({"t0": g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000,
                        "t1": g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000,
                        "text": " ".join(m.group(9).split())})
    return out

def transcript(video, d):
    if (d / "transcript.json").exists():
        return load(d, "transcript.json")
    srt = Path(video).with_suffix(".srt")
    if srt.exists():
        tr = parse_srt(srt)
    elif os.environ.get("DASHSCOPE_API_KEY"):  # the one cloud call left, and only when you opt in with a key
        import asr
        from concurrent.futures import ThreadPoolExecutor
        _, dur = probe(video)
        with ThreadPoolExecutor(4) as ex:
            tr = [s for part in ex.map(lambda st: asr.chunk(video, st), range(0, int(dur) + 1, asr.CHUNK)) for s in part]
    else:
        print(f"no {srt.name} next to the video: classifying without a transcript")
        tr = []
    dump(d, "transcript.json", tr)
    return tr

def text_in(tr, t0, t1):
    """Transcript text spoken in [t0, t1): words when we have word timings, else overlapping sentences."""
    out = []
    for s in tr:
        if s.get("words"):
            out += [w["w"] for w in s["words"] if t0 <= (w["t0"] + w["t1"]) / 2 < t1]
        elif s["t0"] < t1 and s["t1"] > t0:
            out.append(s["text"])
    return "".join(out)

def cuts(video):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", "select='gt(scene,0.3)',metadata=print:file=-",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, check=True).stdout
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r)]

def windows(cut_times, dur):
    """Shots split at scene cuts, each shot split into ~STEP windows. Returns [(shot, t0, t1)]."""
    bounds = [0.0] + cut_times + [dur]
    out = []
    for s, (a, b) in enumerate(zip(bounds, bounds[1:])):
        n = max(1, round((b - a) / STEP))
        out += [(s, a + (b - a) * i / n, a + (b - a) * (i + 1) / n) for i in range(n)]
    return out

def scan(video, fps, wins, cut_times):
    """One decode pass: per-frame motion energy, plus the most active frame of each window."""
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-fps_mode", "passthrough", "-vf", f"scale={TW}:{TH}", "-pix_fmt", "rgb24",
                          "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    cut_frames = {round(c * fps) for c in cut_times}
    energy, best, prev, w, n = [], [(-1.0, None, None)] * len(wins), None, 0, 0
    while (buf := p.stdout.read(TW * TH * 3)) and len(buf) == TW * TH * 3:
        rgb = np.frombuffer(buf, np.uint8).reshape(TH, TW, 3)
        g = rgb[::4, ::4].mean(axis=2)
        e = 0.0 if prev is None else float(np.abs(g - prev).mean())
        prev = g
        energy.append(e)
        t = n / fps
        while w + 1 < len(wins) and t >= wins[w][2]:
            w += 1
        near_cut = any(abs(n - c) <= 2 for c in cut_frames)
        if best[w][1] is None or (not near_cut and e > best[w][0]):
            best[w] = (e, n, rgb.copy())
        n += 1
    p.wait()
    return np.array(energy, np.float32), [(f, im) for _, f, im in best]

def prep(video, role="coach"):
    d = store.dir(db.video_id(video))
    fps, dur = probe(video)
    tr = transcript(video, d) if role == "coach" else []
    ct = cuts(video)
    wins = windows(ct, dur)
    energy, picks = scan(video, fps, wins, ct)
    np.save(d / "energy.npy", energy)
    tiles = [{"k": k, "shot": s, "t0": round(a, 2), "t1": round(b, 2), "t": round(f / fps, 2),
              "text": text_in(tr, a, b)} for k, ((s, a, b), (f, _)) in enumerate(zip(wins, picks))]
    dump(d, "tiles.json", {"id": d.name, "role": role, "name": Path(video).stem, "fps": fps, "duration": dur,
                           "cuts": ct, "tiles": tiles})
    if role == "user":  # your own clip is one demo segment: nothing to classify
        print(f"{d.name}: user clip, {dur:.0f}s -> {d}")
        return
    sd = d / "sheets"; sd.mkdir(exist_ok=True)
    for si in range(0, len(tiles), 16):
        group = tiles[si:si + 16]
        name = f"sheet_{si // 16:02d}"
        grid_sheet([Image.fromarray(im) for _, im in picks[si:si + 16]], [f"#{t['k']} {clock(t['t'])}" for t in group],
                   sd / f"{name}.jpg", tw=TW)
        (sd / f"{name}.txt").write_text("\n".join(f"#{t['k']} [{clock(t['t0'])}-{clock(t['t1'])}] {t['text']}" for t in group))
    (d / "classify_task.md").write_text(
        f"# 镜头分类任务\n\n对 sheets/ 下每个 sheet_XX.jpg（配同名 .txt 字幕）按下列提示作答，"
        f"把所有 tiles 合并写入 tile_labels.json：{{\"tiles\":[...]}}。\n\n{CLASSIFY}\n")
    print(f"{d.name}: {len(ct) + 1} shots, {len(tiles)} tiles, {-(-len(tiles) // 16)} sheets -> {d}")


# ---------- segments + swings ----------

def segments(d, meta):
    vid = meta["id"]
    if meta["role"] == "user":
        return [{"id": f"{vid}_s0000000", "kind": "demo", "t0": 0.0, "t1": meta["duration"], "text": "", "notes": []}]
    lab = {int(str(t["k"]).lstrip("#")): t for t in load(d, "tile_labels.json")["tiles"]}  # agents echo the sheet's "#k"
    if bad := {t["kind"] for t in lab.values()} - set(db.KIND):
        sys.exit(f"tile_labels.json: unknown kind {sorted(bad)}, expected {list(db.KIND)}")
    if missing := [t["k"] for t in meta["tiles"] if t["k"] not in lab]:
        print(f"warning: {len(missing)} tiles have no label, treated as other: {missing[:10]}")
    tr = load(d, "transcript.json")
    segs = []
    for t in meta["tiles"]:
        l = lab.get(t["k"], {"kind": "other"})
        if segs and segs[-1]["kind"] == l["kind"]:
            segs[-1]["t1"] = t["t1"]
        else:  # the start time is the id: it survives a re-run, a running counter does not
            segs.append({"id": f"{vid}_s{round(t['t0'] * 1000):07d}", "kind": l["kind"], "t0": t["t0"], "t1": t["t1"], "notes": []})
        if l.get("note"):
            segs[-1]["notes"].append(l["note"])
    for s in segs:
        s["text"] = text_in(tr, s["t0"], s["t1"])
    return segs

def dsize(video):
    """Display size after rotation (decode one frame)."""
    png = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"],
                         capture_output=True, check=True).stdout
    import io
    return Image.open(io.BytesIO(png)).size

def sheet_size(video):
    w, h = dsize(video)
    return (TW * 2, TH * 2) if w >= h else (TH * 2, TW * 2)  # phone clips are portrait

_PTS = {}
def frame_pts(video):
    """Presentation time of every frame in decode order. Phone/edited videos are often VFR, so index/fps drifts."""
    video = str(video)
    if video not in _PTS:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
                              "-of", "csv=p=0", video], capture_output=True, text=True, check=True).stdout
        _PTS[video] = sorted(float(x.strip(",")) for x in out.split() if x.strip(",") not in ("", "N/A"))
    return _PTS[video]

def clip(video, first, n, size, fps):
    """n consecutive frames starting at frame index `first` (input seek: fast on long files)."""
    w, h = size
    pts = frame_pts(video)
    t0 = max(0.0, pts[first] - 0.5 / fps)  # half a frame early so the seek lands on `first`
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.4f}", "-i", video, "-fps_mode", "passthrough",
                          "-frames:v", str(n),
                          "-vf", f"scale={w}:{h}", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)

def frames_at(video, idx, fps, height=960):
    """PIL frames for indices idx, decoding only the span they cover."""
    W, H = dsize(video)
    size = (round(W * height / H / 2) * 2, height)
    a = min(idx)
    fr = clip(video, a, max(idx) - a + 1, size, fps)
    return [Image.fromarray(fr[i - a]) for i in idx]

def motion_box(frames, thr=25, pad=0.15):
    """Box around pixels that change across frames (N,H,W,3), padded."""
    g = frames.mean(axis=3)
    ys, xs = np.nonzero(np.abs(np.diff(g, axis=0)).max(axis=0) > thr)
    if len(xs) < 50:
        return None
    H, W = g.shape[1:]
    x0, x1 = np.percentile(xs, [2, 98]); y0, y1 = np.percentile(ys, [2, 98])
    p = pad * max(x1 - x0, y1 - y0)
    return (int(max(0, x0 - p)), int(max(0, y0 - p)), int(min(W, x1 + p)), int(min(H, y1 + p)))

def swing_peaks(energy, fps, a, b):
    """Swing candidates in [a, b) frames: smoothed-energy local maxima that stand out from the segment floor."""
    k = max(1, int(fps * 0.25))
    s = np.convolve(energy, np.ones(k) / k, mode="same")
    gap = int(fps * 0.8)
    floor = np.percentile(s[a:b], 20) if b > a else 0
    return [i for i in range(a, b) if s[i] == s[max(0, i - gap):i + gap + 1].max() and s[i] > 2.5 * floor + 0.05]

def local_energy(video, fps, a, b):
    """Motion energy of frames a..b inside the region that moves most (a small player is drowned out in the full
    frame). Returns (energy, region box as fractions of the frame)."""
    w, h = TW // 2, TH // 2
    g = clip(video, a, b - a, (w, h), fps).mean(axis=3)
    d = np.abs(np.diff(g, axis=0))
    act = d.mean(axis=0)
    ys, xs = np.nonzero(act > np.percentile(act, 97))
    x0, x1 = np.percentile(xs, [5, 95]).astype(int); y0, y1 = np.percentile(ys, [5, 95]).astype(int)
    pw, ph = max(4, (x1 - x0) // 2), max(4, (y1 - y0) // 2)
    X0, Y0, X1, Y1 = max(0, x0 - pw), max(0, y0 - ph), min(w, x1 + pw), min(h, y1 + ph)
    return np.concatenate([[0], d[:, Y0:Y1, X0:X1].mean(axis=(1, 2))]), (X0 / w, Y0 / h, X1 / w, Y1 / h)

def grid_sheet(ims, labels, path, cols=4, tw=300):
    th = int(tw * ims[0].height / ims[0].width)
    canvas = Image.new("RGB", (cols * tw, -(-len(ims) // cols) * th), "white")
    dr, F = ImageDraw.Draw(canvas), font(22)
    for j, (im, lab) in enumerate(zip(ims, labels)):
        x, y = (j % cols) * tw, (j // cols) * th
        canvas.paste(im.resize((tw, th)), (x, y))
        dr.rectangle([x, y, x + 8 + dr.textlength(lab, font=F), y + 30], fill="black")
        dr.text((x + 4, y + 2), lab, fill="yellow", font=F)
    canvas.save(path, quality=85)

def swings(video):
    d, meta = cache(video)
    fps, pts = meta["fps"], frame_pts(video)
    cut_frames = [c * fps for c in meta["cuts"]]
    energy = np.load(d / "energy.npy")
    segs = segments(d, meta)
    sd = d / "swings"; sd.mkdir(exist_ok=True)
    for old in sd.glob("*.jpg"):
        old.unlink()
    out, dropped = [], 0
    r = max(1, round(fps / 30))  # same span of motion at any fps
    # frames before the peak, frames in all, tile step. Coach edits cut tight around a swing, so a wide window would
    # cross a cut and drop it. Your own clips are unedited and slower: 1s of lead keeps the backswing in view.
    lead, span, step = (18 * r, 32 * r, 2 * r) if meta["role"] == "coach" else (30 * r, 48 * r, 3 * r)
    W, H = sheet_size(video)
    for s in segs:
        if s["kind"] not in db.DEMO:
            continue
        a, b = max(0, int((s["t0"] - 1) * fps)), min(len(energy), int((s["t1"] + 1) * fps))
        le, region = local_energy(video, fps, a, b)
        for p in swing_peaks(le, fps, 0, b - a):
            p += a
            if any(abs(p - o["peak"]) < fps * 0.5 for o in out):  # windows overlap by 1s
                continue
            first = max(0, p - lead)
            if any(first <= c <= first + span for c in cut_frames):  # a scene cut splits the swing
                dropped += 1
                continue
            fr = clip(video, first, span, (W, H), fps)
            # the segment's active region, widened: a small far-away player still fills the tiles, racket included,
            # and every swing in the segment gets the same framing
            ex, ey = 0.4 * (region[2] - region[0]), 0.4 * (region[3] - region[1])
            box = (int(max(0, region[0] - ex) * W), int(max(0, region[1] - ey) * H),
                   int(min(1, region[2] + ex) * W), int(min(1, region[3] + ey) * H))
            if meta["role"] == "user":  # you film yourself full-body: the whole frame is the player
                box = (0, 0, W, H)
            if motion_box(fr) is None:
                continue
            idx = list(range(0, len(fr), step))[:16]
            sid = f"{meta['id']}_{round(pts[p] * 1000):07d}"
            grid_sheet([Image.fromarray(fr[i]).crop(box) for i in idx], [f"#{i}" for i in idx], sd / f"{sid}.jpg")
            out.append({"id": sid, "segment": s["id"], "first": first, "peak": p, "frames": len(fr),
                        "box": [v / W if k % 2 == 0 else v / H for k, v in enumerate(box)], "sheet": f"swings/{sid}.jpg"})
    dump(d, "segments_draft.json", segs)
    dump(d, "swings.json", out)
    (d / "phase_task.md").write_text(f"# 挥拍阶段标注任务\n\n对 swings.json 中每一项的 sheet 图作答，"
                                     f"写入 phase_labels.json：{{\"<swing id>\": {{...}}}}。\n\n{PHASES}\n")
    print(f"{len(segs)} segments, {sum(s['kind'] in db.DEMO for s in segs)} demo segments, "
          f"{len(out)} swing candidates, {dropped} dropped for crossing a cut")
    for s in segs:
        print(f"  {s['id']} {clock(s['t0']):>6}-{clock(s['t1']):<6} {s['kind']:<10} | {s['text'][:24]}")

def fine(video):
    """Every-frame sheets around each usable swing's coarse lowest point / hit, for 1-frame precision."""
    d, meta = cache(video)
    fps = meta["fps"]
    ph = load(d, "phase_labels.json")
    sd = d / "fine"; sd.mkdir(exist_ok=True)
    jobs = []
    for sw in load(d, "swings.json"):
        p = ph.get(sw["id"]) or {}
        if not p.get("usable") or p.get("hit") is None:
            continue
        hit = sw["first"] + p["hit"]
        low = sw["first"] + p["racket_low"] if p.get("racket_low") is not None else hit - round(0.12 * fps)
        first = max(0, min(low - 2, hit - 11))
        n = max(16, hit + 4 - first + 1)
        W, H = sheet_size(video)
        fr = clip(video, first, n, (W, H), fps)
        bx = sw["box"]
        box = (int(bx[0] * W), int(bx[1] * H), int(bx[2] * W), int(bx[3] * H))
        grid_sheet([Image.fromarray(f).crop(box) for f in fr], [f"#{first - sw['first'] + i}" for i in range(len(fr))],
                   sd / f"{sw['id']}.jpg", cols=4 if n <= 16 else 5, tw=300 if n <= 16 else 240)
        jobs.append(sw["id"])
    (d / "fine_task.md").write_text(f"# 逐帧精标任务\n\n对 fine/<swing id>.jpg（{', '.join(jobs)}）作答，"
                                    f"写入 fine_labels.json：{{\"<swing id>\": {{...}}}}。\n\n{FINE}\n")
    print(f"{len(jobs)} fine sheets -> {d / 'fine_task.md'}")


# ---------- ingest ----------

def to_label(sw, p, pts):
    """A sheet answer (frame offsets) -> a library label (seconds)."""
    p = dict(p)
    h = [RACKET_HEIGHT.get(x) for x in p.pop("racket_height", None) or []]
    # agents call a racket raise a swing; a smash ends lower than it starts, a raise the opposite
    if len(h) == 4 and None not in h and h[-1] >= h[0]:
        p.update(usable=False, note="拍头没有从高处挥下；" + (p.get("note") or ""))
    for k in db.PHASE:
        if p.get(k) is not None:
            p[k] = round(pts[max(0, min(len(pts) - 1, sw["first"] + p[k]))], 3)
    return p

def ingest(video, source="claude"):
    d, meta = cache(video)
    vid, pts = meta["id"], frame_pts(video)
    segs, sws = load(d, "segments_draft.json"), load(d, "swings.json")
    ph = load(d, "phase_labels.json")
    fl = load(d, "fine_labels.json") if (d / "fine_labels.json").exists() else {}
    kinds = load(d, "segment_kinds.json") if (d / "segment_kinds.json").exists() else {}
    if unknown := (set(ph) | set(fl)) - {s["id"] for s in sws} | set(kinds) - {s["id"] for s in segs}:
        sys.exit(f"labels for ids that do not exist (did swings re-run?): {sorted(unknown)}")
    labels, errors = {}, []
    for sw in sws:
        if sw["id"] in ph:
            p = {**ph[sw["id"]], **{k: v for k, v in fl.get(sw["id"], {}).items() if k in ("racket_low", "hit") and v is not None}}
            try:
                labels[sw["id"]] = db.check_label(to_label(sw, p, pts))
            except ValueError as e:
                errors.append(f"{sw['id']}: {e}")
    if errors:
        sys.exit("fix these labels, then run ingest again:\n  " + "\n  ".join(errors))
    cd = d / "clips"; cd.mkdir(exist_ok=True)
    for s in segs:
        s["kind"] = kinds.get(s["id"], s["kind"])
        c = cd / f"{s['id']}.mp4"
        if not c.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['t0']:.2f}", "-i", video, "-t", f"{min(s['t1'] - s['t0'], 30):.2f}",
                            "-vf", "scale=-2:360", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-an",
                            "-movflags", "+faststart", str(c)], check=True)
    import time
    with db.connect() as c:
        c.execute("INSERT INTO video VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET role=excluded.role, name=excluded.name, "
                  "src=excluded.src, fps=excluded.fps, duration=excluded.duration",
                  (vid, meta["role"], meta["name"], store.rel_src(video), meta["fps"], meta["duration"], time.time()))
        keep = json.dumps([s["id"] for s in sws])
        # a swing the detector no longer finds goes, with its labels; ids are peak times, so the rest keep theirs
        c.execute("DELETE FROM label WHERE swing_id IN (SELECT id FROM swing WHERE video_id=? AND id NOT IN (SELECT value FROM json_each(?)))", (vid, keep))
        c.execute("DELETE FROM swing WHERE video_id=? AND id NOT IN (SELECT value FROM json_each(?))", (vid, keep))
        c.execute("DELETE FROM segment WHERE video_id=?", (vid,))
        for s in segs:
            c.execute("INSERT INTO segment VALUES(?,?,?,?,?,?,?)",
                      (s["id"], vid, s["t0"], s["t1"], s["kind"], s["text"], f"{vid}/clips/{s['id']}.mp4"))
        for sw in sws:
            last = min(len(pts) - 1, sw["first"] + sw["frames"] - 1)
            c.execute("INSERT OR REPLACE INTO swing VALUES(?,?,?,?,?,?,?)",
                      (sw["id"], vid, sw["segment"], pts[sw["first"]], pts[last], json.dumps(sw["box"]), f"{vid}/{sw['sheet']}"))
            if sw["id"] in labels:
                db.set_label(c, sw["id"], source, labels[sw["id"]])
    print(f"{meta['name']} ({vid}): {len(segs)} segments, {len(sws)} swings, "
          f"{sum(bool(l.get('usable')) for l in labels.values())} usable, {len(sws) - len(labels)} unlabeled -> {store.path('lens.db')}")


if __name__ == "__main__":
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    if sys.argv[1] == "prep":
        prep(args[0], "user" if "--user" in sys.argv else "coach")
    else:
        {"swings": swings, "fine": fine, "ingest": ingest}[sys.argv[1]](args[0])
