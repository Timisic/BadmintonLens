"""python3 test_db.py"""
import clean, db

ok = {"usable": True, "camera": "back", "hit": 1.5}
assert db.check_label(ok) == ok
for bad in ({**ok, "camera": "背后"}, {**ok, "hit": "1.5"}, {**ok, "usable": 1}, {**ok, "击球点": 1.5}):
    try:
        db.check_label(bad)
    except ValueError:
        continue
    raise AssertionError(f"accepted {bad}")

# offsets on a sheet become seconds; a racket that ends no lower than it starts is a raise, not a smash
sw, pts = {"first": 10}, [i / 30 for i in range(100)]
assert clean.to_label(sw, {"usable": True, "hit": 5}, pts) == {"usable": True, "hit": 0.5}
assert clean.to_label(sw, {"usable": True, "racket_height": ["below_waist", "shoulder_to_head", "above_head", "above_head"]}, pts)["usable"] is False

# the pose reads a swing: the hit is where the faster wrist is highest, whatever the label said
import numpy as np, compare, diagnose
t = np.arange(0, 3, 1 / 30)
k = np.full((len(t), 17, 3), 0.5)
k[:, 0, 1], k[:, [5, 6], 1], k[:, [11, 12], 1], k[:, [15, 16], 1] = 0.3, 0.4, 0.6, 0.9
k[:, 5, 0], k[:, 6, 0] = np.where(t < 1.1, 0.4, 0.6), np.where(t < 1.1, 0.6, 0.4)  # back to the camera, then chest
k[:, 10, 1] = 0.5 - 0.4 * np.exp(-((t - 1.1) / 0.08) ** 2)
compare.player = lambda s, a, b: (t[(t >= a) & (t <= b)], k[(t >= a) & (t <= b)], None)
cand = {"label": {}, "t0": 0.5, "t1": 2}
r = compare.reading(cand)
assert abs(r["hit"] - 1.1) < 0.02 and r["hand"] == 1 and r["overhead"] and r["camera"] == "left", r
# reading again from its own answer gives the same answer: a wrong hit must not pull the next reading after it
assert compare.reading({**cand, "label": {"hit": 0.6, "source": "pose"}})["hit"] == r["hit"]
assert abs(compare.reading({"label": {"hit": 1.0, "source": "human"}})["hit"] - 1.1) < 0.02  # a person's hit narrows the search
clean_k = k.copy()
k[60, 10, :2] = 0.05, 0.0  # the pose jumps for one frame, far faster and higher than the swing
assert abs(compare.reading(cand)["hit"] - 1.1) < 0.02
k[:, 9, 1] = 0.6 - 0.6 * np.exp(-((t - 0.7) / 0.08) ** 2)  # the other hand flicks up faster: told the hand, the hit stays
assert compare.reading(cand)["hand"] == 0 and abs(compare.reading(cand, 1)["hit"] - 1.1) < 0.02
k = clean_k
flat = k.copy()
flat[:, 10, 1] = 0.5
k, coach = flat, k
assert compare.reading(cand) is None  # a still hand is not a hit

# the coach lifts the racket-side foot, I do not: that is the finding, and the coach's words on it come along
k = coach.copy()
me = {"label": {"hit": 1.1}, "t0": 0.5, "t1": 2, "fps": 30, "video_id": "u"}
lifted = coach.copy()
lifted[:, 16, 1] = 0.9 - 0.15 * np.exp(-((t - 1.3) / 0.1) ** 2)
compare.player = lambda s, a, b: (t[(t >= a) & (t <= b)], (lifted if s.get("coach") else k)[(t >= a) & (t <= b)], None)
c = db.sqlite3.connect(":memory:")
c.row_factory = db.sqlite3.Row
c.executescript(db.SCHEMA)
c.execute("INSERT INTO video VALUES('v','coach','教练','',30,10,0)")
c.executemany("INSERT INTO segment VALUES(?, 'v', ?, ?, ?, ?, NULL)",
              [("a", 0, 5, "talk", "右腿会抬起来"), ("b", 5, 9, "slow_demo", "右腿离开地"), ("x", 9, 12, "ad", "右腿"), ("y", 20, 25, "talk", "别的")])
found = diagnose.diagnose(c, me, {**me, "coach": True}, [me])
assert [f["phase"] for f in found] == ["引拍", "击球", "击球", "击球", "击球后"]  # the whole swing, in order
assert [f["key"] for f in found if f["short"]] == ["leg"], found
leg = found[-1]
assert leg["video"] == {"short": 1, "total": 1, "value": leg["me"], "habit": True} and leg["coach"] > leg["me"]
# both players are shown at the same moments, the joint to watch marked in each
assert [f["at"] for f in leg["frames"]] == [0.1, 0.25, 0.4] and all(len(f["me"]) == len(f["coach"]) == 2 for f in leg["frames"])
# from behind, the coach leans away from the racket hand before the hit and I stand straight
back = {**me, "label": {"hit": 1.1, "camera": "back"}}
lifted[:, 5:7, 0] -= 0.3 * compare.torso(lifted)
assert [f["key"] for f in diagnose.diagnose(c, back, {**back, "coach": True}, [back]) if f["short"]] == ["lean", "leg"]
found = [leg]
assert [(l["t0"], l["t1"], l["text"]) for l in found[0]["lessons"]] == [(0, 9, "右腿会抬起来右腿离开地")]  # neighbours read as one
print("ok")
