"""Contact-sheet grids: numbered frames cropped to the moving player."""
import subprocess, io
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import motion

FPS = 60000 / 1001

def frames(path, idx, size=None):
    """Decode specific frame indices (full res) via ffmpeg select."""
    sel = "+".join(f"eq(n\\,{i})" for i in idx)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"select='{sel}'",
                          "-vsync", "0", "-f", "image2pipe", "-c:v", "png", "-"],
                         capture_output=True, check=True).stdout
    out, pos = [], 0
    while (pos := raw.find(b"\x89PNG", pos)) != -1:
        nxt = raw.find(b"\x89PNG", pos + 8)
        out.append(Image.open(io.BytesIO(raw[pos:nxt if nxt != -1 else None])).convert("RGB"))
        pos = pos + 8
    assert len(out) == len(idx), (len(out), len(idx))
    return out

def player_box(path, a, b):
    """Bounding box of motion between frames a..b, in display pixels (rotation applied), with margin."""
    W, H = frames(path, [a])[0].size
    sw, sh = W // 10, H // 10
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf",
                          f"select='between(n\\,{a}\\,{b})',scale={sw}:{sh},format=gray",
                          "-vsync", "0", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, sh, sw).astype(np.float32)
    m = np.abs(np.diff(f, axis=0)).max(axis=0) > 25
    ys, xs = np.nonzero(m)
    x0, x1 = np.percentile(xs, [2, 98]) * 10
    y0, y1 = np.percentile(ys, [2, 98]) * 10
    pad = 0.12 * max(x1 - x0, y1 - y0)
    return (int(max(0, x0 - pad)), int(max(0, y0 - pad)), int(min(W, x1 + pad)), int(min(H, y1 + pad)))

def sheet(path, idx, box, cols=4, tile_w=360):
    ims = [im.crop(box) for im in frames(path, idx)]
    th = int(tile_w * ims[0].height / ims[0].width)
    rows = -(-len(ims) // cols)
    canvas = Image.new("RGB", (cols * tile_w, rows * th), "white")
    d = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=28)
    for k, (i, im) in enumerate(zip(idx, ims)):
        x, y = (k % cols) * tile_w, (k // cols) * th
        canvas.paste(im.resize((tile_w, th)), (x, y))
        d.rectangle([x, y, x + 110, y + 36], fill="black")
        d.text((x + 6, y + 3), f"#{i}", fill="yellow", font=font)
    return canvas
