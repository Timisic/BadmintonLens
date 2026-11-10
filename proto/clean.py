"""Coach-video cleaning pipeline. Every stage caches into work/<stem>/ and is safe to re-run.

  python3 clean.py prep     <video>   transcript + shots + time-window tiles + sheets (zero model tokens)
  python3 clean.py classify <video>   model labels each tile (type / angle)        -> tile_labels.json
  python3 clean.py swings   <video>   merge tiles into segments, find swings in demo segments, swing sheets
  python3 clean.py phases   <video>   model labels phases on each swing sheet       -> phase_labels.json
  python3 clean.py fine     <video>   every-frame sheets around lowest point / hit   -> fine_labels.json (--model)
  python3 clean.py table    <video>   segments.json + preview clips + review.html
  python3 clean.py review   <video>   local review page; "保存" writes segments_confirmed.json

classify / phases / fine call the configured model (label.py, Qwen by default). table also writes
claude_review_task.md: a reviewer (Claude Code via .claude/skills/clean-coach-video) fixes what the model misjudged in
claude_labels.json and re-runs table. table merges phase < fine < claude; the review page saves human edits to segments_confirmed.json.
"""
import json, os, re, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

STEP = 3.0                      # seconds per tile
TW, TH = 384, 216               # tile size (scan resolution)
CJK = "/System/Library/Fonts/STHeiti Medium.ttc"
TYPES = ["口播讲解", "慢速分解", "全速正确示范", "错误示范", "比赛实战", "广告", "其他"]
ANGLES = ["正面", "背后", "斜后", "侧面", "斜前", "不适用"]
DEMO = {"全速正确示范", "错误示范"}

CLASSIFY = f"""你在整理羽毛球教练李宇轩的杀球教学视频。图中是按时间排列的编号缩略图（左上：#编号 镜头号S 时间），
每格代表约{STEP:g}秒，取该时段画面动作最剧烈的一帧。下方文字是每格对应时段的字幕（可能为空）。
对每一格判断：
- type 取值 {"/".join(TYPES)}
  全速正确示范：教练以正常速度做出完整杀球挥拍，字幕没有否定意味；
  错误示范：字幕有"不可以/不要/错误/最多人做的/很奇怪"等否定，或在模仿学员常见错误；
  慢速分解：放慢或停顿着讲解某一段动作；口播讲解：主要在说话，没有完整挥拍；
  比赛实战：比赛或对打画面；广告：产品推广；其他：片头片尾、字幕卡等。
- angle：拍摄者相对教练的位置，取值 {"/".join(ANGLES)}
- swing：这一帧是否正处在挥拍过程中（true/false）
判断示范对错时以字幕为准，画面相似时不要猜。
只输出 JSON：{{"tiles":[{{"k":编号,"type":"","angle":"","swing":false,"note":"≤15字，可省略"}}]}}"""

# asked in its own call: folded into PHASES, Qwen got these wrong on 9 of 19 swings; alone, 0 of 19 on 拍位
SIDE = """这是一次羽毛球挥拍的连续帧网格（每格左上角为帧号）。只看第一行。回答两个看图就能确定的事实：
脸：能看到这个人的眼睛和鼻子吗？"看得到" 或 "看不到"（只看到后脑勺、头发算看不到）。
拍位：球拍（拍框）在这张图片里位于他身体的左边还是右边？以看图的人的左右为准，不是他本人的左右。"画面左" 或 "画面右"。
只输出 JSON：{"脸":"","拍位":""}"""

FINE = """这是一次杀球挥拍的逐帧网格（每格左上角为帧号，相邻格相差1帧）。没球时击球点指拍面挥到最高、最前、速度最快的那一帧；
拍头最低点指引拍后拍头在背后下沉到最低的那一帧（不在本网格内则为 null）。
只输出 JSON：{"拍头最低点": 帧号或null, "击球点": 帧号, "置信度": "高/中/低"}"""

PHASES = """这是羽毛球教练一次杀球挥拍的连续帧网格（每格左上角为帧号，按时间顺序，相邻格间隔数帧，以帧号为准）。
如果没球，击球点指拍面挥到最高、最前、速度最快的那一帧；拍头最低点指引拍后拍头在背后下沉到最低的那一帧。
angle 为拍摄者相对教练的位置（以引拍侧身时的站位为准）：正面/背后/斜后/侧面/斜前。
先逐行看持拍手的拍头位置：网格每行 4 格，每一行拍头大多在 "头顶以上" / "肩到头之间" / "腰以下"，填进"拍头高度"（4 项，按行顺序）。
若这组帧里根本没有完整的杀球挥拍（只是举拍到准备姿势、走动、比划、半截动作），usable 填 false。
各阶段帧号必须按时间顺序：引拍侧身 < 拍头最低点 < 击球点 < 随挥收拍。
只输出 JSON：{"拍头高度":["","","",""],"usable":true,"angle":"","引拍侧身":帧号或null,"拍头最低点":帧号或null,"击球点":帧号或null,"随挥收拍":帧号或null,"置信度":"高/中/低","备注":"一句话"}"""


def font(size):
    return ImageFont.truetype(CJK, size)

def work(video):
    d = Path(__file__).parent / "work" / Path(video).stem
    d.mkdir(parents=True, exist_ok=True)
    return d

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
    else:
        import asr  # Fun-ASR, needs DASHSCOPE_API_KEY
        from concurrent.futures import ThreadPoolExecutor
        _, dur = probe(video)
        with ThreadPoolExecutor(4) as ex:
            tr = [s for part in ex.map(lambda st: asr.chunk(video, st), range(0, int(dur) + 1, asr.CHUNK)) for s in part]
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

def prep(video):
    d = work(video)
    fps, dur = probe(video)
    tr = transcript(video, d)
    ct = cuts(video)
    wins = windows(ct, dur)
    energy, picks = scan(video, fps, wins, ct)
    np.save(d / "energy.npy", energy)
    tiles = [{"k": k, "shot": s, "t0": round(a, 2), "t1": round(b, 2), "frame": f, "t": round(f / fps, 2),
              "text": text_in(tr, a, b)} for k, ((s, a, b), (f, _)) in enumerate(zip(wins, picks))]
    dump(d, "tiles.json", {"video": str(Path(video).resolve()), "fps": fps, "duration": dur, "cuts": ct, "tiles": tiles})
    sd = d / "sheets"; sd.mkdir(exist_ok=True)
    F = font(20)
    for si in range(0, len(tiles), 16):
        group = tiles[si:si + 16]
        canvas = Image.new("RGB", (4 * TW, -(-len(group) // 4) * TH), "white")
        dr = ImageDraw.Draw(canvas)
        for j, (tl, (_, im)) in enumerate(zip(group, picks[si:si + 16])):
            x, y = (j % 4) * TW, (j // 4) * TH
            canvas.paste(Image.fromarray(im), (x, y))
            lab = f"#{tl['k']} S{tl['shot']} {tl['t']:.0f}s"
            dr.rectangle([x, y, x + 8 + dr.textlength(lab, font=F), y + 28], fill="black")
            dr.text((x + 4, y + 2), lab, fill="yellow", font=F)
        name = f"sheet_{si // 16:02d}"
        canvas.save(sd / f"{name}.jpg", quality=82)
        (sd / f"{name}.txt").write_text("\n".join(f"#{t['k']} [{t['t0']:.1f}-{t['t1']:.1f}s] S{t['shot']} | {t['text']}"
                                                  for t in group))
    (d / "classify_task.md").write_text(
        f"# 镜头分类任务\n\n对 sheets/ 下每个 sheet_XX.jpg（配同名 .txt 字幕）按下列提示作答，"
        f"把所有 tiles 合并写入 tile_labels.json：{{\"tiles\":[...]}}。\n\n{CLASSIFY}\n")
    print(f"{len(ct) + 1} shots, {len(tiles)} tiles, {-(-len(tiles) // 16)} sheets -> {d}")


# ---------- model stages ----------

def pmap(f, xs, workers=int(os.environ.get("COACH_WORKERS", 8))):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(f, xs))

def classify(video):
    import label
    d = work(video)
    jpgs = sorted((d / "sheets").glob("sheet_*.jpg"))
    res = pmap(lambda j: label.ask(Image.open(j), CLASSIFY + "\n\n字幕：\n" + j.with_suffix(".txt").read_text(), 3000), jpgs)
    for j, (js, usage, _) in zip(jpgs, res):
        print(j.name, usage.input_tokens, usage.output_tokens)
    dump(d, "tile_labels.json", {"tiles": [t for js, _, _ in res for t in js["tiles"]]})

def phases(video):
    import label
    d = work(video)
    sws = load(d, "swings.json")
    ask = lambda sw: {**label.ask(Image.open(d / sw["sheet"]), PHASES, 600)[0], **label.ask(Image.open(d / sw["sheet"]), SIDE, 100)[0]}
    res = {sw["id"]: r for sw, r in zip(sws, pmap(ask, sws))}
    H = {"腰以下": 0, "肩到头之间": 1, "头顶以上": 2}
    for v in res.values():
        # models call a racket raise a swing; a smash ends lower than it starts, a raise the opposite
        h = [H.get(x) for x in v.get("拍头高度") or []]
        if len(h) == 4 and None not in h and h[-1] >= h[0]:
            v.update(usable=False, 备注="拍头没有从高处挥下（" + "→".join(v["拍头高度"]) + "）；" + v.get("备注", ""))
    for v in res.values():  # out-of-order phases mean the model misread the swing: keep it but send it to review
        seq = [v.get(k) for k in ("引拍侧身", "拍头最低点", "击球点")]
        if v.get("usable") and (None in seq or seq != sorted(seq)):
            v.update(置信度="低", 备注=f"阶段顺序不对 {seq}，需人工复核；" + v.get("备注", ""))
    for k, v in res.items():
        print(k, v)
    dump(d, "phase_labels.json", res)


# ---------- segments + swings ----------

def segments(d):
    meta = load(d, "tiles.json")
    lab = {int(str(t["k"]).lstrip("#")): t for t in load(d, "tile_labels.json")["tiles"]}  # models echo the sheet's "#k"
    if missing := [t["k"] for t in meta["tiles"] if t["k"] not in lab]:
        print(f"warning: {len(missing)} tiles have no label, treated as 其他: {missing[:10]}")
    segs = []
    for t in meta["tiles"]:
        l = lab.get(t["k"], {"type": "其他", "angle": "不适用"})
        # merge by type only: the per-tile angle flips whenever the coach turns; swings get their own angle later
        if segs and segs[-1]["type"] == l["type"]:
            s = segs[-1]
            s["t1"], s["tiles"] = t["t1"], s["tiles"] + [t["k"]]
            s["shots"] = sorted(set(s["shots"]) | {t["shot"]})
            s["angles"].append(l["angle"])
        else:
            segs.append({"id": f"seg{len(segs):03d}", "type": l["type"], "angles": [l["angle"]], "t0": t["t0"], "t1": t["t1"],
                         "tiles": [t["k"]], "shots": [t["shot"]], "notes": []})
        if l.get("note"):
            segs[-1]["notes"].append(l["note"])
    tr = load(d, "transcript.json")
    for s in segs:
        s["text"] = text_in(tr, s["t0"], s["t1"])
        s["angle"] = max(set(s["angles"]), key=s["angles"].count)
    return segs

def dsize(video):
    """Display size after rotation (decode one frame)."""
    png = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"],
                         capture_output=True, check=True).stdout
    import io
    return Image.open(io.BytesIO(png)).size

_PTS = {}
def frame_pts(video):
    """Presentation time of every frame in decode order. Phone/edited videos are often VFR, so index/fps drifts."""
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
    d = work(video)
    meta = load(d, "tiles.json")
    fps = meta["fps"]
    cut_frames = [c * fps for c in meta["cuts"]]
    energy = np.load(d / "energy.npy")
    segs = segments(d)
    sd = d / "swings"; sd.mkdir(exist_ok=True)
    out, dropped = [], 0
    r = max(1, round(fps / 30))  # keep ~1s of motion at any fps: 32r frames, every 2r-th shown
    W, H = TW * 2, TH * 2
    for s in segs:
        if s["type"] not in DEMO:
            continue
        a, b = max(0, int((s["t0"] - 1) * fps)), min(len(energy), int((s["t1"] + 1) * fps))
        le, region = local_energy(video, fps, a, b)
        for p in swing_peaks(le, fps, 0, b - a):
            p += a
            if any(abs(p - o["peak_frame"]) < fps * 0.5 for o in out):  # windows overlap by 1s
                continue
            first = max(0, p - 18 * r)
            if any(first <= c <= first + 32 * r for c in cut_frames):  # a scene cut splits the swing
                dropped += 1
                continue
            fr = clip(video, first, 32 * r, (W, H), fps)
            # the segment's active region, widened: a small far-away player still fills the tiles, racket included,
            # and every swing in the segment gets the same framing
            ex, ey = 0.4 * (region[2] - region[0]), 0.4 * (region[3] - region[1])
            box = (int(max(0, region[0] - ex) * W), int(max(0, region[1] - ey) * H),
                   int(min(1, region[2] + ex) * W), int(min(1, region[3] + ey) * H))
            if motion_box(fr) is None:
                continue
            idx = list(range(0, len(fr), 2 * r))[:16]
            sid = f"{s['id']}_sw{len([o for o in out if o['seg'] == s['id']])}"
            grid_sheet([Image.fromarray(fr[i]).crop(box) for i in idx], [f"#{first + i}" for i in idx], sd / f"{sid}.jpg")
            out.append({"id": sid, "seg": s["id"], "type": s["type"], "peak_frame": p, "t": round(p / fps, 2),
                        "box": [v / W if k % 2 == 0 else v / H for k, v in enumerate(box)], "sheet": f"swings/{sid}.jpg"})
    dump(d, "segments_draft.json", segs)
    dump(d, "swings.json", out)
    (d / "phase_task.md").write_text(f"# 挥拍阶段标注任务\n\n对 swings.json 中每一项的 sheet 图作答，"
                                     f"写入 phase_labels.json：{{\"<swing id>\": {{...}}}}。\n\n{PHASES}\n")
    print(f"{len(segs)} segments, {sum(s['type'] in DEMO for s in segs)} demo segments, "
          f"{len(out)} swing candidates, {dropped} dropped for crossing a cut")
    for s in segs:
        print(f"  {s['id']} {s['t0']:6.1f}-{s['t1']:6.1f} {s['type']:<6} {s['angle']} | {s['text'][:24]}")

def fine(video):
    """Every-frame sheets around each usable swing's coarse lowest point / hit, for 1-frame precision."""
    d = work(video)
    fps = load(d, "tiles.json")["fps"]
    ph = load(d, "phase_labels.json")
    sd = d / "fine"; sd.mkdir(exist_ok=True)
    jobs = []
    for sw in load(d, "swings.json"):
        p = ph.get(sw["id"]) or {}
        if not p.get("usable") or not p.get("击球点"):
            continue
        hit, low = p["击球点"], p.get("拍头最低点") or p["击球点"] - round(0.12 * fps)
        first = min(low - 2, hit - 11)
        n = max(16, hit + 4 - first + 1)
        fr = clip(video, first, n, (TW * 2, TH * 2), fps)
        bx = sw["box"]; W, H = TW * 2, TH * 2
        box = (int(bx[0] * W), int(bx[1] * H), int(bx[2] * W), int(bx[3] * H))
        grid_sheet([Image.fromarray(f).crop(box) for f in fr], [f"#{first + i}" for i in range(len(fr))],
                   sd / f"{sw['id']}.jpg", cols=4 if n <= 16 else 5, tw=300 if n <= 16 else 240)
        jobs.append(sw["id"])
    (d / "fine_task.md").write_text(f"# 逐帧精标任务\n\n对 fine/<swing id>.jpg（{', '.join(jobs)}）作答，"
                                    f"写入 fine_labels.json：{{\"<swing id>\": {{...}}}}。\n\n{FINE}\n")
    print(f"{len(jobs)} fine sheets")
    if "--model" in sys.argv:
        import label
        res = pmap(lambda j: label.ask(Image.open(sd / f"{j}.jpg"), FINE, 400)[0], jobs)
        dump(d, "fine_labels.json", dict(zip(jobs, res)))


# ---------- table + review ----------

REVIEW_FIELDS = ("angle", "脸", "拍位", "引拍侧身", "拍头最低点", "击球点")

def table(video):
    d = work(video)
    meta = load(d, "tiles.json")
    segs = load(d, "segments_draft.json")
    sw = load(d, "swings.json")
    ph = load(d, "phase_labels.json") if (d / "phase_labels.json").exists() else {}
    fl = load(d, "fine_labels.json") if (d / "fine_labels.json").exists() else {}
    cl = load(d, "claude_labels.json") if (d / "claude_labels.json").exists() else {}
    for k, v in fl.items():  # per-frame labels refine the coarse ones
        ph[k].update({f: v[f] for f in ("拍头最低点", "击球点") if v.get(f)}, 精标=True)
    if unknown := set(cl) - set(ph) - {s["id"] for s in segs}:
        print(f"warning: claude_labels.json ids match no segment or swing: {sorted(unknown)}")
    for k in cl.keys() & ph.keys():  # reviewer corrections win over model labels
        ph[k].update({f: cl[k][f] for f in ("usable", *REVIEW_FIELDS) if f in cl[k]}, 复核="claude")
    for s in segs:  # segment ids (segNNN) and swing ids (segNNN_swK) share claude_labels.json
        if s["id"] in cl:
            s.update(type=cl[s["id"]].get("type", s["type"]), 复核="claude")
    seg_todo = {s["id"]: {"type": s["type"], "t": f"{s['t0']:.0f}-{s['t1']:.0f}s", "text": s["text"][:80],
                          "sheets": [x["sheet"] for x in sw if x["seg"] == s["id"]]}
                for s in segs if s["type"] in DEMO and s["id"] not in cl}
    todo = {k: {f: v.get(f) for f in ("usable", *REVIEW_FIELDS, "置信度", "备注")} for k, v in ph.items()
            if k not in cl and (v.get("usable") or v.get("置信度") == "低")}
    (d / "claude_review_task.md").write_text(
        f"# Claude 复核任务\n\n## 片段类型（{len(seg_todo)} 个）\n\n看 sheets 里的挥拍图和字幕，判断是不是正常速度的完整杀球："
        f"慢速/停顿讲解改为 慢速分解，字幕有否定或模仿学员错误改为 错误示范，对打改为 比赛实战。"
        f"写入 claude_labels.json：{{\"<seg id>\": {{\"type\": 值}}}}，type 必填（不改也写上当前值）。\n\n"
        f"```json\n{json.dumps(seg_todo, ensure_ascii=False, indent=1)}\n```\n\n"
        f"## 挥拍（{len(todo)} 个）\n\n先看 review_sides.jpg 核对每个挥拍的 脸 / 拍位（引拍时的前两格）；"
        f"再逐个看 swings/<id>.jpg 核对 usable、angle、帧号。只改看错的字段，"
        f"写入 claude_labels.json：{{\"<swing id>\": {{字段: 值}}}}，usable 必填（模型重跑后结论可能变），其余字段只写改动的。"
        f"可改字段：usable, {', '.join(REVIEW_FIELDS)}。\n\n```json\n{json.dumps(todo, ensure_ascii=False, indent=1)}\n```\n")
    side_sheet([(d / next(x["sheet"] for x in sw if x["id"] == k), f"{k} {v['脸']} {v['拍位']}") for k, v in todo.items()],
               d / "review_sides.jpg")
    cd = d / "clips"; cd.mkdir(exist_ok=True)
    for s in segs:
        s["swings"] = [dict(x, phases=ph.get(x["id"])) for x in sw if x["seg"] == s["id"]]
        s["swings"] = [x for x in s["swings"] if not x["phases"] or x["phases"].get("usable", True)]
        c = cd / f"{s['id']}_{s['t0']:.1f}.mp4"  # start time in the name: segment ids shift when swings is re-run
        if not c.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['t0']:.2f}", "-i", video, "-t", f"{min(s['t1'] - s['t0'], 30):.2f}",
                            "-vf", "scale=-2:360", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-an",
                            "-movflags", "+faststart", str(c)], check=True)
        s["clip"] = f"clips/{c.name}"
    dump(d, "segments.json", {"video": meta["video"], "fps": meta["fps"], "segments": segs})
    (d / "review.html").write_text(REVIEW_HTML)
    print(f"segments.json: {len(segs)} segments, "
          f"{sum(len(s['swings']) for s in segs)} labeled swings -> {d / 'review.html'}")

def side_sheet(items, path, cols=5, w=300, h=200):
    """One image with the first two tiles (the backswing) of each swing sheet, labeled, for a one-look side check."""
    c = Image.new("RGB", (cols * w, max(1, -(-len(items) // cols)) * (h + 20)), "white"); dr = ImageDraw.Draw(c)
    for i, (sheet, text) in enumerate(items):
        im = Image.open(sheet); t = im.crop((0, 0, im.width // 2, im.height // 4)); t.thumbnail((w, h))
        x, y = i % cols * w, i // cols * (h + 20)
        c.paste(t, (x, y + 20)); dr.text((x + 3, y + 2), text, fill="black", font=font(15))
    c.save(path, quality=85)

REVIEW_HTML = """<!doctype html><meta charset=utf-8><title>片段审核</title>
<style>body{font:14px -apple-system,sans-serif;margin:16px;background:#fafafa}
.seg{display:grid;grid-template-columns:320px 1fr;gap:12px;background:#fff;border:1px solid #ddd;border-radius:8px;padding:10px;margin:10px 0}
.seg.demo{border-color:#2a7}.seg.wrong{border-color:#c33}video{width:320px}select{font-size:14px}
.sw img{max-width:100%;margin-top:6px}.meta{color:#666}.txt{margin:6px 0;line-height:1.5}
#bar{position:sticky;top:0;background:#fafafa;padding:8px 0;z-index:1}
label.f{margin-right:10px}</style>
<div id=bar><button onclick=save()>保存为 segments_confirmed.json</button> <span id=st></span>
 <label class=f><input type=checkbox id=only onchange=draw()> 只看示范片段</label></div><div id=list></div>
<script>
const TYPES=%TYPES%, ANGLES=%ANGLES%; let data;
fetch('segments.json').then(r=>r.json()).then(j=>{data=j;draw()});
function opt(list,v){return list.map(x=>`<option ${x==v?'selected':''}>${x}</option>`).join('')}
function draw(){const only=document.getElementById('only').checked;
 document.getElementById('list').innerHTML=data.segments.map((s,i)=>(only&&!s.type.includes('示范'))?'':`
 <div class="seg ${s.type=='全速正确示范'?'demo':s.type=='错误示范'?'wrong':''}">
  <div><video src="${s.clip}" controls preload=none></video>
   <div class=meta>${s.id} · ${s.t0.toFixed(1)}–${s.t1.toFixed(1)}s · 镜头 ${s.shots.join(',')}</div></div>
  <div><select onchange="data.segments[${i}].type=this.value">${opt(TYPES,s.type)}</select>
   <select onchange="data.segments[${i}].angle=this.value">${opt(ANGLES,s.angle)}</select>
   <label><input type=checkbox ${s.confirmed?'checked':''} onchange="data.segments[${i}].confirmed=this.checked"> 已确认</label>
   <div class=meta>${s.notes.join('；')}</div><div class=txt>${s.text||'<i>无字幕</i>'}</div>
   ${s.swings.map((w,j)=>`<details class=sw><summary>挥拍 ${w.id} @${w.t}s ${w.phases?(w.phases.angle||'')+' · 击球点 #'+w.phases['击球点']+' · '+w.phases['置信度']:'未标注'}
     <label><input type=checkbox ${w.reject?'checked':''} onchange="data.segments[${i}].swings[${j}].reject=this.checked"> 剔除</label></summary>
     <img src="${w.sheet}"></details>`).join('')}</div></div>`).join('')}
function save(){fetch('save',{method:'POST',body:JSON.stringify(data)}).then(r=>r.text()).then(t=>document.getElementById('st').textContent=t)}
</script>""".replace("%TYPES%", json.dumps(TYPES, ensure_ascii=False)).replace("%ANGLES%", json.dumps(ANGLES, ensure_ascii=False))

def review(video, port=8765):
    import http.server, functools
    d = work(video)
    class H(http.server.SimpleHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            dump(d, "segments_confirmed.json", body)
            self.send_response(200); self.end_headers(); self.wfile.write("已保存".encode())
    print(f"http://127.0.0.1:{port}/review.html")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=str(d))).serve_forever()


if __name__ == "__main__":
    {"prep": prep, "classify": classify, "swings": swings, "phases": phases, "fine": fine, "table": table,
     "review": review}[sys.argv[1]](sys.argv[2])
