"""Where my swing falls short of the coach's, and what the coach says about it.

Every check is a height difference between two joints, in torso lengths, so it holds whatever side the camera is on
and however large the player is in the picture. A check is a finding when the coach is ahead by more than its margin.
A swing is judged whole, phase by phase, and so is the video it came from: every swing of it against the same coach.
The coach's own words come from the transcript segments that mention the check's keywords.
"""
import numpy as np
import compare, db

SHOULDER, WRIST, HIP, ANKLE = 5, 9, 11, 15  # the left one of each COCO pair; +1 is the right
PHASE = {"prep": "引拍", "hit": "击球", "after": "击球后"}
# In the order a swing happens. name: what is measured. fault: what it means to fall short. {r} is the racket side,
# {o} the other. margin: how far two good swings differ anyway, read off the coach demos in the library.
# look: the joint to watch (0 racket side, 1 the other) and the seconds from the hit that show it, the same for both players.
CHECKS = {
    "off_up": {"phase": "prep", "name": "{o}手上举", "fault": "引拍时{o}手抬得不够高", "margin": 0.25,
               "look": (WRIST, 1, [-0.6, -0.45, -0.3]), "words": ["抬左手", "左手再抬", "展肩", "舒展"]},
    # only from behind or in front: there a lean back shows as a lean to the side, away from the racket hand
    "lean": {"phase": "prep", "name": "上身后仰", "fault": "引拍时上身是直的，没有向{o}后方仰", "margin": 0.08,
             "look": (SHOULDER, 1, [-0.6, -0.45, -0.35]), "words": ["侧身", "往后倒", "后仰"]},
    "off_pull": {"phase": "hit", "name": "{o}手下拉", "fault": "挥拍时{o}手没有往下拉", "margin": 0.3,
                 "look": (WRIST, 1, [-0.4, -0.2, 0]), "words": ["拉左手", "左手往后", "往下拉", "拉左肩", "左肘"]},
    "tilt": {"phase": "hit", "name": "{r}肩顶起", "fault": "击球时两肩是平的，{r}肩没有顶上去", "margin": 0.15,
             "look": (SHOULDER, 0, [-0.12, 0, 0.12]), "words": ["一高一低", "右肩", "压左肩", "平的", "左肩"]},
    "reach": {"phase": "hit", "name": "击球高度", "fault": "击球点偏低，手臂没有向上伸展开", "margin": 0.15,
              "look": (WRIST, 0, [-0.12, 0, 0.12]), "words": ["舒展", "伸展", "往上", "抬手", "右肩上"]},
    "leg": {"phase": "after", "name": "{r}腿上抬", "fault": "{r}腿抬得不够，重心没有完全换到{o}腿", "margin": 0.25,
            "look": (ANKLE, 0, [0.1, 0.25, 0.4]), "words": ["右腿", "抬腿", "抬起来", "离开地", "去左腿", "去了左腿"]},
}
SPOKEN = {"talk", "slow_demo", "demo", "wrong_demo"}  # segments where the coach is teaching

def pose(s):
    """Seconds from the hit, and the keypoints, around a swing. None without pose."""
    hit = s["label"]["hit"]
    p = compare.player(s, hit + compare.SPAN[0], hit + compare.SPAN[1])
    return None if p is None or len(p[0]) < 5 else (p[0] - hit, p[1])

def measure(s, racket):
    """{check: value} for a player whose racket hand is `racket` (0 left, 1 right). None without pose."""
    p = pose(s)
    if p is None or racket is None:
        return None
    d, k = p
    unit, off = compare.torso(k), 1 - racket
    y = lambda joint: k[:, joint, 1]
    above = lambda low, high: (y(low) - y(high)) / unit  # how far `high` is above `low`
    def peak(v, a, b):
        v = v[(d >= a) & (d <= b)]
        return None if np.isnan(v).all() else float(np.nanmax(v))
    now = 1 / s["fps"]  # the hit frame itself
    mid = lambda joint: k[:, [joint, joint + 1], 0].mean(1)
    # the off side is on the left of the picture for a right-hander seen from behind, or a left-hander from the front
    left = {"back": racket == 1, "front": racket == 0}.get(s["label"].get("camera"))
    early = (mid(SHOULDER) - mid(HIP))[(d >= -0.6) & (d <= -0.35)] / unit
    floor = np.nanpercentile(k[:, [ANKLE, ANKLE + 1], 1], 95)
    up, at_hit = peak(above(SHOULDER + off, WRIST + off), -0.9, -0.15), peak(above(SHOULDER + off, WRIST + off), -now, now)
    out = {
        "off_up": up,
        "lean": None if left is None or np.isnan(early).all() else float(np.nanmedian(early)) * (-1 if left else 1),
        "off_pull": None if up is None or at_hit is None else up - at_hit,
        "tilt": peak(above(SHOULDER + off, SHOULDER + racket), -now, now),
        "reach": peak(above(SHOULDER + racket, WRIST + racket), -now, now),
        "leg": peak((floor - y(ANKLE + racket)) / unit, -0.15, 0.45),
    }
    return {key: v for key, v in out.items() if v is not None}

def spot(s, racket, joint, side, at):
    """Where that joint is in the picture, `at` seconds from the hit. None when the pose lost it."""
    d, k = pose(s)
    xy = k[int(np.abs(d - at).argmin()), joint + (racket if side == 0 else 1 - racket), :2]
    return None if np.isnan(xy).any() else xy.tolist()

def lessons(c, words, limit=3):
    """Transcript passages where a coach talks about these words, most relevant first. Neighbouring segments that
    also mention them are read as one passage: the transcript is cut by picture, not by sentence."""
    segs = [dict(r) for r in c.execute(
        "SELECT g.*, v.name FROM segment g JOIN video v ON v.id = g.video_id WHERE v.role='coach' ORDER BY v.name, g.t0")]
    for g in segs:
        g["score"] = sum((g["text"] or "").count(w) for w in words) if g["kind"] in SPOKEN else 0
    out, run = [], []
    for g in segs + [{"score": 0}]:
        if g["score"] and (not run or (run[-1]["video_id"] == g["video_id"] and g["t0"] - run[-1]["t1"] < 0.5 and g["t1"] - run[0]["t0"] < 45)):
            run.append(g)
            continue
        if run:
            out.append({"video_id": run[0]["video_id"], "name": run[0]["name"], "t0": run[0]["t0"], "t1": run[-1]["t1"],
                        "text": "".join(x["text"] for x in run), "score": sum(x["score"] for x in run)})
        run = [g] if g["score"] else []
    return [{k: v for k, v in o.items() if k != "score"} for o in sorted(out, key=lambda o: -o["score"])[:limit]]

def diagnose(c, me, coach, lib=()):
    """My swing against the coach's, check by check in the order a swing happens. None without pose.
    short    this swing falls short
    video    the same check over every swing of the video mine came from: how many fall short, of how many,
             and their median. `habit` when most do: then the lessons come along even if this swing is fine.
    frames   moments to look at, the same seconds from the hit for both, with the joint to watch in each picture"""
    of = lambda one: [s for s in lib if s["video_id"] == one["video_id"]] or [one]
    hand, theirs = compare.racket_hand(of(me)), compare.racket_hand(of(coach))
    a, b = measure(me, hand), measure(coach, theirs)
    if not a or not b:
        return None
    side = {"r": "左右"[hand], "o": "右左"[hand]}
    same = [m for s in of(me) if (m := measure(s, hand))]
    out = []
    for key, check in CHECKS.items():
        if key not in a or key not in b:
            continue
        short = lambda v: b[key] - v > check["margin"]
        seen = [m[key] for m in same if key in m]
        habit = sum(map(short, seen)) * 2 > len(seen)
        joint, which, ats = check["look"]
        out.append({"key": key, "phase": PHASE[check["phase"]], "name": check["name"].format(**side),
                    "fault": check["fault"].format(**side), "short": short(a[key]), "me": a[key], "coach": b[key],
                    "video": {"short": sum(map(short, seen)), "total": len(seen), "value": float(np.median(seen)), "habit": habit},
                    "frames": [{"at": at, "me": spot(me, hand, joint, which, at), "coach": spot(coach, theirs, joint, which, at)}
                               for at in ats],
                    "lessons": lessons(c, check["words"]) if short(a[key]) or habit else []})
    return out
