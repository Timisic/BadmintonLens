"""python3 test_api.py"""
import os, tempfile
from pathlib import Path

root = Path(tempfile.mkdtemp())
os.environ["LENS_STORE"] = str(root)  # store.ROOT is read at import

from fastapi.testclient import TestClient
import api, db, store

# run alone: imported after anything that loaded store, this would write into the real library
assert store.ROOT == root, f"store already loaded from {store.ROOT}; run python3 test_api.py on its own"

src = root / "v.mp4"
src.write_bytes(bytes(range(256)) * 4)
(root / "sheet.jpg").write_bytes(b"jpg")
ok = {"usable": True, "camera": "back", "hit": 1.5}
c = db.connect()
c.executemany("INSERT INTO video VALUES(?,?,?,?,30,10,0)",
              [("vc", "coach", "教练", str(src)), ("vu", "user", "我的", str(src)), ("gone", "user", "丢了", str(root / "no.mp4"))])
c.execute("INSERT INTO segment VALUES('g','vc',0,5,'demo','',NULL)")
c.executemany("INSERT INTO swing VALUES(?,?,?,?,?,'[0,0,1,1]','sheet.jpg')",
              [("c1", "vc", "g", 1, 2), ("u1", "vu", None, 1, 2), ("u2", "vu", None, 3, 4)])
db.set_label(c, "c1", "claude", ok)
db.set_label(c, "u1", "claude", ok)
c.commit()
c.close()

http = TestClient(api.app)
label = lambda swing: next(s for v in http.get("/api/library").json()["videos"] for s in v["swings"] if s["id"] == swing)["label"]

lib = http.get("/api/library").json()
assert set(lib["vocab"]) == {"kind", "camera", "role", "source"}
assert [v["id"] for v in lib["videos"]] == ["vc", "gone", "vu"]
assert lib["videos"][0]["segments"][0]["kind"] == "demo" and lib["videos"][0]["swings"][0]["box"] == [0, 0, 1, 1]
assert label("u1") == {**ok, "source": "claude"} and label("u2") == {}

assert http.get("/store/sheet.jpg").content == b"jpg"
part = http.get("/api/videos/vu/source", headers={"Range": "bytes=10-19"})
assert part.status_code == 206 and part.content == bytes(range(10, 20)), part.status_code
assert http.get("/api/videos/nope/source").status_code == 404
assert http.get("/api/videos/gone/source").status_code == 404
(root / "user/丢了").mkdir(parents=True)
(root / "user/丢了/play.mp4").write_bytes(b"copy")  # the browser copy is served first, and outlives the source
assert http.get("/api/videos/gone/source").content == b"copy"
assert http.get("/api/videos/gone/source?sound=1").content == b"copy"  # the source has the sound, when it is there

bad = http.put("/api/swings/u1/label", json={**ok, "camera": "背后"})
assert bad.status_code == 400 and bad.json()["detail"].startswith("camera='背后', expected one of"), bad.text
assert label("u1")["source"] == "claude"
# a person's label is patched field by field; usable=false deletes the swing from every comparison
assert http.put("/api/swings/u1/label", json={"camera": "left"}).status_code == 200
assert http.put("/api/swings/u1/label", json={"usable": False}).status_code == 200
assert label("u1") == {"usable": False, "camera": "left", "hit": 1.5, "source": "human"}
assert http.get("/api/compare").json()["pairs"] == {}
assert http.put("/api/swings/u1/label", json={"usable": None}).status_code == 200
assert label("u1") == {**ok, "camera": "left", "source": "human"}
assert http.delete("/api/swings/u1/label").status_code == 200
assert label("u1") == {**ok, "source": "claude"}

for call in (http.put("/api/swings/nope/label", json=ok), http.delete("/api/swings/nope/label")):
    assert call.status_code == 404, call.text
assert label("u1")["source"] == "claude"

m = http.get("/api/compare").json()
assert 0 in m["offsets"] and m["pairs"] == {"u1": ["c1"]}  # u2 has no hit: not comparable
assert [(s["id"], s["hit"], s["camera"]) for s in m["swings"]] == [("u1", 1.5, "back"), ("c1", 1.5, "back")]
assert m["swings"][0]["box"] == [0, 0, 1, 1]  # no pose file here: the swing's own box

# no coach demo filmed from the same place: my swing is still listed, with nobody to pair
http.put("/api/swings/u1/label", json={"camera": "left"})
m = http.get("/api/compare").json()
assert m["pairs"] == {"u1": []} and len(m["swings"]) == 2
assert http.get("/api/diagnose?me=u1&coach=c1").json()["checks"] is None  # no pose here: nothing to say
assert http.get("/api/diagnose?me=u2&coach=c1").status_code == 404
assert http.get("/api/swings/u2/thumb").status_code == 404  # no browser copy of that video
assert http.get("/api/nope").status_code == 404
assert "sqlite3" not in http.get("/..%2f..%2fproto/db.py").text  # the frontend route never serves a file outside dist
print("ok")
