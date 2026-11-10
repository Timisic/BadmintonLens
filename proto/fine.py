"""Usage: python3 fine.py <video_path> <peak_time_s> <start_frame> <end_frame> <out.jpg>  (every frame, max 16)"""
import sys, grid
p, t, a, b, out = sys.argv[1], float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
assert 0 <= b - a < 16, "range must be 1..16 frames"
c = int(t * grid.FPS)
grid.sheet(p, list(range(a, b + 1)), grid.player_box(p, c - 90, c + 45), tile_w=300).save(out, quality=85)
print("ok")
