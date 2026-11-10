"""python3 test_db.py"""
import clean, db

ok = {"usable": True, "camera": "back", "face_visible": False, "racket_side": "right", "backswing": 1.0, "racket_low": 1.4, "hit": 1.5}
assert db.check_label(ok) == ok
for bad in ({**ok, "camera": "背后"}, {**ok, "hit": 1.2}, {**ok, "racket_low": None}, {**ok, "击球点": 1.5}):
    try:
        db.check_label(bad)
    except ValueError:
        continue
    raise AssertionError(f"accepted {bad}")

# offsets on a sheet become seconds; a racket that ends no lower than it starts is a raise, not a smash
sw, pts = {"first": 10}, [i / 30 for i in range(100)]
assert clean.to_label(sw, {"usable": True, "hit": 5}, pts) == {"usable": True, "hit": 0.5}
assert clean.to_label(sw, {"usable": True, "racket_height": ["below_waist", "shoulder_to_head", "above_head", "above_head"]}, pts)["usable"] is False
print("ok")
