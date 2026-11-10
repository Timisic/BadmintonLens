"""Rows of candidate swings: each row = 12 frames, step 4 @30fps, centered on a time."""
import sys, grid
from PIL import Image, ImageDraw, ImageFont
P = "/Users/hong/Downloads/261109杀球模仿/转换重心.mp4"
def rows(times, out, step=4, n=12, tw=150):
    f = ImageFont.load_default(size=16); sheet = None
    for r, t in enumerate(times):
        c = int(t * 30); idx = [c - step * (n // 2) + step * k for k in range(n)]
        ims = grid.frames(P, idx)
        W, H = ims[0].size; box = (int(W * .3), 0, int(W * .7), H)
        th = int(tw * H / (W * .4))
        if sheet is None: sheet = Image.new("RGB", (n * tw, len(times) * th)); d = ImageDraw.Draw(sheet)
        for k, (i, im) in enumerate(zip(idx, ims)):
            x, y = k * tw, r * th; sheet.paste(im.crop(box).resize((tw, th)), (x, y))
            d.rectangle([x, y, x + 64, y + 18], fill="black"); d.text((x + 2, y + 1), f"{i}", fill="yellow", font=f)
    sheet.save(out, quality=80)
if __name__ == "__main__":
    rows([float(t) for t in sys.argv[2:]], sys.argv[1])
