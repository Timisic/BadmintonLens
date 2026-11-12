"""Local HTTP API over the library, for the web frontend in ../web. Binds 127.0.0.1 only: coach material stays on
this machine.

  python3 api.py     http://127.0.0.1:8000   also serves the built frontend, once `pnpm build` has run in ../web
"""
import json, subprocess
from pathlib import Path
from contextlib import closing
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import compare, db, diagnose, store

app = FastAPI()
app.mount("/store", StaticFiles(directory=store.ROOT), name="store")

def need_swing(c, swing_id):
    # SQLite does not enforce the label -> swing foreign key
    if not c.execute("SELECT 1 FROM swing WHERE id=?", (swing_id,)).fetchone():
        raise HTTPException(404, f"没有这一拍：{swing_id}")

def play_copy(s):
    return store.ROOT / s["role"] / s["name"] / "play.mp4"

@app.get("/api/library")
def library():
    with closing(db.connect()) as c:
        return db.library(c)

@app.get("/api/videos/{video_id}/source")
def source(video_id: str, sound: bool = False):
    with closing(db.connect()) as c:
        v = c.execute("SELECT role, name, src FROM video WHERE id=?", (video_id,)).fetchone()
    # the browser copy (clean.py play) when there is one: it plays everywhere and survives the source moving.
    # It is silent, so a coach explaining plays from the source.
    files = [v and play_copy(v), v and store.src(v["src"])]
    for f in files[::-1] if sound else files:
        if f and f.is_file():
            return FileResponse(f)
    raise HTTPException(404, "找不到源视频")

@app.put("/api/swings/{swing_id}/label")
def save_label(swing_id: str, body: dict):
    """What a person says about a swing, field by field: a field left out keeps what they said before, null takes
    it back. usable=false is how a swing is deleted."""
    with closing(db.connect()) as c:
        need_swing(c, swing_id)
        old = c.execute("SELECT data FROM label WHERE swing_id=? AND source='human'", (swing_id,)).fetchone()
        new = {k: v for k, v in {**json.loads(old["data"] if old else "{}"), **body}.items() if v is not None}
        try:
            db.set_label(c, swing_id, "human", new)
        except ValueError as e:
            raise HTTPException(400, str(e))
        c.commit()

@app.get("/api/swings/{swing_id}/thumb")
def thumb(swing_id: str):
    """The player at the hit (the middle of the clip when there is none), as a small picture. Made once."""
    with closing(db.connect()) as c:
        s = next((s for s in db.swings(c) if s["id"] == swing_id), None)
    if not s or not play_copy(s).is_file():
        raise HTTPException(404, "没有这一拍的画面")
    hit = s["label"].get("hit")
    t = (s["t0"] + s["t1"]) / 2 if hit is None else hit
    f = store.path(f"{s['role']}/{s['name']}/thumbs/{swing_id}-{round(t * 1000)}.jpg")
    if not f.is_file():
        x0, y0, x1, y1 = (s["box"] if hit is None else compare.view(s)) or (0, 0, 1, 1)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", play_copy(s), "-frames:v", "1", "-vf",
                        f"crop=iw*{x1 - x0:.4f}:ih*{y1 - y0:.4f}:iw*{x0:.4f}:ih*{y0:.4f},scale=-2:320", f], check=True)
    return FileResponse(f, headers={"Cache-Control": "max-age=86400"})

@app.delete("/api/swings/{swing_id}/label")
def revert_label(swing_id: str):
    with closing(db.connect()) as c:
        need_swing(c, swing_id)
        c.execute("DELETE FROM label WHERE swing_id=? AND source='human'", (swing_id,))
        c.commit()

@app.get("/api/compare")
def comparable():
    """Every swing that can be compared, and for each of mine the coach demos filmed from the same place."""
    with closing(db.connect()) as c:
        lib = db.swings(c)
    pairs = compare.pairs(lib)
    return {"offsets": compare.OFFSETS, "span": compare.SPAN, "pairs": pairs,
            "swings": [{**{k: s[k] for k in ("id", "role", "name", "video_id", "fps")}, "hit": s["label"]["hit"],
                        "camera": s["label"].get("camera"), "box": compare.view(s)}
                       for s in lib if s["id"] in pairs or s in compare.demos(lib)]}

@app.get("/api/diagnose")
def diagnosis(me: str, coach: str):
    """Where my swing falls short of the coach's, with what the coach says about each."""
    with closing(db.connect()) as c:
        lib = {s["id"]: s for s in db.swings(c)}
        if not all(i in lib and compare.ready(lib[i]) for i in (me, coach)):
            raise HTTPException(404, "这两拍不能对比")
        ready = [s for s in lib.values() if compare.ready(s)]
        return {"video": {"name": lib[me]["name"], "swings": sum(s["video_id"] == lib[me]["video_id"] for s in ready)},
                "checks": diagnose.diagnose(c, lib[me], lib[coach], ready)}

DIST = Path(__file__).resolve().parent.parent / "web/dist"

@app.get("/{path:path}")
def page(path: str):
    """The built frontend. Its routes live in the browser, so any path that is not a file gets the app shell."""
    if path.startswith(("api/", "store/")):
        raise HTTPException(404)
    f = (DIST / path).resolve()
    if path and f.is_file() and f.is_relative_to(DIST):
        return FileResponse(f)
    if not (DIST / "index.html").is_file():
        raise HTTPException(404, "前端还没构建：cd web && pnpm build")
    return FileResponse(DIST / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
