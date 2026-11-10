"""Phase-aligned side-by-side: top row coach, bottom row user, one column per phase."""
import grid
from PIL import Image, ImageDraw, ImageFont
CJK = "/System/Library/Fonts/STHeiti Medium.ttc"  # PIL default font has no Chinese glyphs
COACH = "/Users/hong/Downloads/261109杀球模仿/转换重心.mp4"
# coach full swing @787s (30fps): 引拍侧身, 拍头最低点, 击球点, 随挥(+8f≈0.27s), 收拍(+18f≈0.6s)
COACH_PH = [23622, 23630, 23634, 23642, 23652]
NAMES = ["引拍侧身", "拍头最低点", "击球点", "随挥 +0.27s", "收拍 +0.6s"]

def user_phases(backswing, low, hit, fps=grid.FPS):
    return [backswing, low, hit, hit + round(0.27 * fps), hit + round(0.6 * fps)]

def build(user_path, user_ph, user_box, out, label):
    tw, th = 300, 420
    font = ImageFont.truetype(CJK, 24)
    rows = [("教练 787s", grid.frames(COACH, COACH_PH), grid.player_box(COACH, 23600, 23670), COACH_PH),
            (label, grid.frames(user_path, user_ph), user_box, user_ph)]
    c = Image.new("RGB", (tw * 5, 40 + th * 2), "white"); d = ImageDraw.Draw(c)
    for k, n in enumerate(NAMES):
        d.text((k * tw + 8, 8), n, fill="black", font=font)
    for r, (name, ims, box, idx) in enumerate(rows):
        for k, im in enumerate(ims):
            t = im.crop(box); t.thumbnail((tw, th))
            x, y = k * tw + (tw - t.width) // 2, 40 + r * th
            c.paste(t, (x, y))
            d.rectangle([k * tw, y, k * tw + 200, y + 30], fill="black")
            d.text((k * tw + 4, y + 2), f"{name} #{idx[k]}", fill="yellow", font=ImageFont.truetype(CJK, 18))
    c.save(out, quality=85)
