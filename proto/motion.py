"""Swing window detection by frame differencing (zero tokens)."""
import subprocess, sys, json
import numpy as np

W, H = 96, 54

def motion_energy(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
    e = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    return np.concatenate([[0], e])

def peaks(e, fps, min_gap_s=1.2):
    k = max(1, int(fps * 0.25))
    s = np.convolve(e, np.ones(k) / k, mode="same")
    gap = int(fps * min_gap_s)
    # local maxima that dominate +-gap/2
    cand = [i for i in range(len(s)) if s[i] == s[max(0, i - gap // 2):i + gap // 2 + 1].max()]
    # prominence over the local floor
    cand = [i for i in cand if s[i] > 1.5 * s[max(0, i - gap):i + gap + 1].min() + 0.1]
    if not cand:
        return [], s, 0.0
    med = float(np.median([s[i] for i in cand]))
    # walking in/out or touching the phone is far bigger than a swing
    keep = [i for i in cand if 0.5 * med <= s[i] <= 2.5 * med]
    return keep, s, med

if __name__ == "__main__":
    path, fps = sys.argv[1], 60000 / 1001
    e = motion_energy(path)
    pk, s, thr = peaks(e, fps)
    print(json.dumps({"frames": len(e), "thr": round(float(thr), 2),
                      "peaks": [{"frame": p, "t": round(p / fps, 2), "energy": round(float(s[p]), 2)} for p in pk]}))
