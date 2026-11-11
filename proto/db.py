"""The library: videos, segments, swings and layered labels in SQLite (store/lens.db).

Every time is seconds of presentation time in the source video. Frame numbers never reach the library: they change
with a re-encode and drift on variable-frame-rate phone video.

  python3 db.py     dump the whole library as JSON (what a frontend or API reads)
"""
import hashlib, json, sqlite3, sys, time
from pathlib import Path
import store

# value -> 显示名. Code, prompts and the database use the English value; Chinese lives only in these tables.
KIND = {"talk": "口播讲解", "slow_demo": "慢速分解", "demo": "全速正确示范", "wrong_demo": "错误示范",
        "match": "比赛实战", "ad": "广告", "other": "其他"}
CAMERA = {"front": "正面", "back": "背后", "rear_oblique": "斜后", "side": "侧面", "front_oblique": "斜前"}
RACKET_SIDE = {"left": "画面左", "right": "画面右"}
CONFIDENCE = {"high": "高", "medium": "中", "low": "低"}
PHASE = {"backswing": "引拍侧身", "racket_low": "拍头最低点", "hit": "击球点", "follow": "随挥收拍"}
ROLE = {"coach": "教练", "user": "我"}
DEMO = {"demo", "wrong_demo"}
# label layers, later wins: legacy vision model, pose estimation (reserved for the GPU job), Claude subagent, person
SOURCE = {"model": "旧模型", "pose": "姿态", "claude": "Claude", "human": "人工"}
SOURCES = list(SOURCE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS video(id TEXT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('coach','user')),
  name TEXT NOT NULL, src TEXT NOT NULL, fps REAL NOT NULL, duration REAL NOT NULL, added REAL NOT NULL);
CREATE TABLE IF NOT EXISTS segment(id TEXT PRIMARY KEY, video_id TEXT NOT NULL REFERENCES video(id),
  t0 REAL NOT NULL, t1 REAL NOT NULL, kind TEXT NOT NULL, text TEXT, clip TEXT);
CREATE TABLE IF NOT EXISTS swing(id TEXT PRIMARY KEY, video_id TEXT NOT NULL REFERENCES video(id),
  segment_id TEXT REFERENCES segment(id), t0 REAL NOT NULL, t1 REAL NOT NULL, box TEXT, sheet TEXT);
CREATE TABLE IF NOT EXISTS label(swing_id TEXT NOT NULL REFERENCES swing(id), source TEXT NOT NULL,
  data TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY(swing_id, source));
"""

def connect():
    c = sqlite3.connect(store.path("lens.db"))
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c

def video_id(path):
    """Content hash, so a renamed or moved file keeps its id."""
    h = hashlib.sha1(str(Path(path).stat().st_size).encode())
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
    return h.hexdigest()[:12]

def check_label(d):
    """Labels are written by agents and people: nothing outside the vocabulary reaches the library."""
    enums = {"usable": (True, False), "face_visible": (True, False), "camera": CAMERA, "racket_side": RACKET_SIDE,
             "confidence": CONFIDENCE}
    for k, v in d.items():
        if k in enums:
            if v is not None and v not in enums[k]:
                raise ValueError(f"{k}={v!r}, expected one of {list(enums[k])}")
        elif k in PHASE:
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                raise ValueError(f"{k}={v!r}, expected seconds or null")
        elif k != "note":
            raise ValueError(f"unknown field {k!r}")
    seq = [d[k] for k in PHASE if d.get(k) is not None]
    if seq != sorted(seq):
        raise ValueError(f"phases out of order: {({k: d.get(k) for k in PHASE})}")
    if d.get("usable") and any(d.get(k) is None for k in ("backswing", "racket_low", "hit")):
        raise ValueError("usable swing needs backswing, racket_low and hit")
    return d

def set_label(c, swing_id, source, data):
    if source not in SOURCES:
        raise ValueError(f"source {source!r}, expected one of {SOURCES}")
    c.execute("INSERT OR REPLACE INTO label VALUES(?,?,?,?)",
              (swing_id, source, json.dumps(check_label(data), ensure_ascii=False), time.time()))

def swings(c, role=None):
    """Every swing with its video, segment kind and effective label (layers merged in SOURCES order)."""
    layers = {}
    for r in c.execute("SELECT * FROM label"):
        layers.setdefault(r["swing_id"], {})[r["source"]] = json.loads(r["data"])
    out = []
    for r in c.execute("SELECT s.*, v.role, v.name, v.src, v.fps, g.kind FROM swing s JOIN video v ON v.id = s.video_id "
                       "LEFT JOIN segment g ON g.id = s.segment_id ORDER BY v.name, s.t0"):
        if role and r["role"] != role:
            continue
        label = {}
        for src in SOURCES:
            if src in layers.get(r["id"], {}):
                label.update({k: v for k, v in layers[r["id"]][src].items() if v is not None}, source=src)
        out.append({**dict(r), "box": json.loads(r["box"]) if r["box"] else None, "label": label})
    return out

def library(c):
    sw = swings(c)
    return {"vocab": {"kind": KIND, "camera": CAMERA, "racket_side": RACKET_SIDE, "confidence": CONFIDENCE,
                      "phase": PHASE, "role": ROLE, "source": SOURCE},
            "videos": [{**dict(v),
                        "segments": [dict(g) for g in c.execute("SELECT * FROM segment WHERE video_id=? ORDER BY t0", (v["id"],))],
                        "swings": [{k: s[k] for k in ("id", "segment_id", "t0", "t1", "box", "sheet", "label")}
                                   for s in sw if s["video_id"] == v["id"]]}
                       for v in c.execute("SELECT * FROM video ORDER BY role, name").fetchall()]}

if __name__ == "__main__":
    json.dump(library(connect()), sys.stdout, ensure_ascii=False, indent=1)
