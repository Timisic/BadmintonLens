"""Local HTTP API over the library, for the web frontend in ../web. Binds 127.0.0.1 only: coach material stays on
this machine.

  python3 api.py     http://127.0.0.1:8000   also serves the built frontend, once `pnpm build` has run in ../web
"""
from pathlib import Path
from contextlib import closing
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import compare, db, store

app = FastAPI()
app.mount("/store", StaticFiles(directory=store.ROOT), name="store")

def need_swing(c, swing_id):
    # SQLite does not enforce the label -> swing foreign key
    if not c.execute("SELECT 1 FROM swing WHERE id=?", (swing_id,)).fetchone():
        raise HTTPException(404, f"没有这一拍：{swing_id}")

@app.get("/api/library")
def library():
    with closing(db.connect()) as c:
        return db.library(c)

@app.get("/api/videos/{video_id}/source")
def source(video_id: str):
    with closing(db.connect()) as c:
        v = c.execute("SELECT role, name, src FROM video WHERE id=?", (video_id,)).fetchone()
    # the browser copy (clean.py play) when there is one: it plays everywhere and survives the source moving
    for f in (v and store.ROOT / v["role"] / v["name"] / "play.mp4", v and store.src(v["src"])):
        if f and f.is_file():
            return FileResponse(f)
    raise HTTPException(404, "找不到源视频")

@app.put("/api/swings/{swing_id}/label")
def save_label(swing_id: str, body: dict):
    # shortcut: db.swings drops nulls when merging layers, so the human layer cannot clear a phase a lower layer
    # set; give the merge a real "cleared" value when a reviewer needs to remove one
    with closing(db.connect()) as c:
        need_swing(c, swing_id)
        try:
            db.set_label(c, swing_id, "human", body)
        except ValueError as e:
            raise HTTPException(400, str(e))
        c.commit()

@app.delete("/api/swings/{swing_id}/label")
def revert_label(swing_id: str):
    with closing(db.connect()) as c:
        need_swing(c, swing_id)
        c.execute("DELETE FROM label WHERE swing_id=? AND source='human'", (swing_id,))
        c.commit()

@app.get("/api/swings/{swing_id}/match")
def match(swing_id: str):
    with closing(db.connect()) as c:
        lib = db.swings(c)
    user = next((s for s in lib if s["id"] == swing_id), None)
    if not user:
        raise HTTPException(404, f"没有这一拍：{swing_id}")
    if not compare.ready(user):
        need = "、".join(db.PHASE[k] for k in ("backswing", "racket_low", "hit"))
        raise HTTPException(400, f"这一拍还不能对比：要先标为可用，并标好{need}")
    coach, note = compare.pick(user, compare.demos(lib))
    side = lambda s: {"swing": s, "times": compare.times(s["label"]), "box": compare.view(s)}
    return {"cols": compare.COLS, "step": compare.N + 1, "note": note, "user": side(user),
            "coach": coach and side(coach)}

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
