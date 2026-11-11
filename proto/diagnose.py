"""Where my swing falls short of the coach's, and what the coach says about it.

Every check is a height difference between two joints, in torso lengths, so it holds whatever side the camera is on
and however large the player is in the picture. A check is a finding when the coach is ahead by more than its margin.
The coach's own words come from the transcript segments that mention the check's keywords.
"""
import numpy as np
import compare, db

SHOULDER, WRIST, ANKLE = 5, 9, 15  # the left one of each COCO pair; +1 is the right
# name: what is measured. fault: what it means to fall short. {r} is the racket side, {o} the other.
# margin: how far two good swings differ anyway, read off the coach demos in the library.
CHECKS = {
    "leg": {"name": "{r}腿上抬", "fault": "{r}腿抬得不够，重心没有完全换到{o}腿", "margin": 0.25,
            "words": ["右腿", "抬腿", "抬起来", "离开地", "去左腿", "去了左腿"]},
    "reach": {"name": "击球高度", "fault": "击球点偏低，手臂没有向上伸展开", "margin": 0.15,
              "words": ["舒展", "伸展", "往上", "抬手", "右肩上"]},
    "tilt": {"name": "击球时{r}肩顶起", "fault": "击球时两肩是平的，{r}肩没有顶上去", "margin": 0.15,
             "words": ["一高一低", "右肩", "压左肩", "平的", "左肩"]},
    "off_up": {"name": "{o}手上举", "fault": "引拍时{o}手抬得不够高", "margin": 0.25,
               "words": ["抬左手", "左手再抬", "展肩", "舒展"]},
    "off_pull": {"name": "{o}手下拉", "fault": "挥拍时{o}手没有往下拉", "margin": 0.3,
                 "words": ["拉左手", "左手往后", "往下拉", "拉左肩", "左肘"]},
}
SPOKEN = {"talk", "slow_demo", "demo", "wrong_demo"}  # segments where the coach is teaching

def racket_hand(swings):
    """The hand most of one player's swings are read with. From behind the pose now and then swaps the two sides
    of a swing; such a swing is not measured, its joints cannot be trusted."""
    hands = [r["hand"] for s in swings if (r := compare.reading(s))]
    return max(set(hands), key=hands.count) if hands else None

def measure(s, hand):
    """{check: (value, seconds from the hit of the moment that shows it, [x, y] of the joint in the picture)} for
    a player whose racket hand is `hand`. None without pose, or when the pose reads this swing with the other hand."""
    hit = s["label"]["hit"]
    p = compare.player(s, hit + compare.SPAN[0], hit + compare.SPAN[1])
    r = compare.reading(s)
    if p is None or r is None or r["hand"] != hand:
        return None
    t, k, _ = p
    d, unit, racket, off = t - hit, compare.torso(k), r["hand"], 1 - r["hand"]
    y = lambda joint: k[:, joint, 1]
    above = lambda low, high: (y(low) - y(high)) / unit  # how far `high` is above `low`
    def peak(v, a, b, joint):
        v = np.where((d >= a) & (d <= b), v, np.nan)
        if np.isnan(v).all():
            return None
        i = int(np.nanargmax(v))
        return float(v[i]), float(d[i]), k[i, joint, :2].tolist()
    now = 1 / s["fps"]  # the hit frame itself
    floor = np.nanpercentile(k[:, [ANKLE, ANKLE + 1], 1], 95)
    up = peak(above(SHOULDER + off, WRIST + off), -0.9, -0.15, WRIST + off)
    at_hit = peak(above(SHOULDER + off, WRIST + off), -now, now, WRIST + off)
    out = {
        "leg": peak((floor - y(ANKLE + racket)) / unit, -0.15, 0.45, ANKLE + racket),
        "reach": peak(above(SHOULDER + racket, WRIST + racket), -now, now, WRIST + racket),
        "tilt": peak(above(SHOULDER + off, SHOULDER + racket), -now, now, SHOULDER + racket),
        "off_up": up,
        "off_pull": up and at_hit and (up[0] - at_hit[0], at_hit[1], at_hit[2]),
    }
    return {k_: v for k_, v in out.items() if v and not np.isnan(v[0])}

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
    """Every check both swings allow, the widest gap first. `short` marks the findings; those carry the lessons, and
    `habit`: in how many of the swings from the same video of mine the same thing shows. None without pose."""
    of = lambda one: [s for s in lib if s["video_id"] == one["video_id"]] or [one]
    hand = racket_hand(of(me))
    a, b = measure(me, hand), measure(coach, racket_hand(of(coach)))
    if not a or not b:
        return None
    side = {"r": "左右"[hand], "o": "右左"[hand]}
    same = [m for s in of(me) if (m := measure(s, hand))]
    out = []
    for key, check in CHECKS.items():
        if key not in a or key not in b:
            continue
        (mine, my_at, my_spot), (theirs, their_at, their_spot) = a[key], b[key]
        short = theirs - mine > check["margin"]
        out.append({"key": key, "name": check["name"].format(**side), "fault": check["fault"].format(**side), "short": short,
                    "gap": (theirs - mine) / check["margin"],
                    "me": {"value": mine, "at": my_at, "spot": my_spot},
                    "coach": {"value": theirs, "at": their_at, "spot": their_spot},
                    "habit": [sum(key in m and theirs - m[key][0] > check["margin"] for m in same), len(same)],
                    "lessons": lessons(c, check["words"]) if short else []})
    return sorted(out, key=lambda f: -f["gap"])
