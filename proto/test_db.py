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
r = compare.reading({"label": {"hit": 1.0}})
assert abs(r["hit"] - 1.1) < 0.02 and r["hand"] == 1 and r["overhead"] and r["camera"] == "left", r
assert abs(compare.reading({"label": {}, "t0": 0.5, "t1": 2})["hit"] - 1.1) < 0.02  # found without a label too
flat = k.copy()
flat[:, 10, 1] = 0.5
k, coach = flat, k
assert compare.reading({"label": {"hit": 1.0}}) is None  # a still hand is not a hit

# the coach lifts the racket-side foot, I do not: that is the finding, and the coach's words on it come along
k = coach.copy()
me = {"label": {"hit": 1.1}, "fps": 30, "video_id": "u"}
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
assert [(f["key"], f["short"], f["habit"]) for f in found][0] == ("leg", True, [1, 1]) and not any(f["short"] for f in found[1:]), found
assert [(l["t0"], l["t1"], l["text"]) for l in found[0]["lessons"]] == [(0, 9, "右腿会抬起来右腿离开地")]  # neighbours read as one
print("ok")
