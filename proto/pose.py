"""Pose keypoints for every frame of a video, on a GPU. Runs on the server; needs only ffmpeg, numpy and ultralytics.

  python pose.py <video> <out.npz> [--model models/yolo11x-pose.pt] [--imgsz 960] [--batch 64] [--device 0]
  python pose.py all <videos dir> [--devices 0,1,2]   every video without keypoints -> store/<role>/<file name>/pose.npz,
                                                      one process per GPU (measured: one process fills one L40S)

Frames are decoded in the same order clean.py counts them, so row i of the output is frame i.
out.npz: kpts [frames, KEEP, 17, 3] (x, y as fractions of the frame, confidence), boxes [frames, KEEP, 4].
People are sorted by box area, largest first; missing people are zeros. Keypoints follow the COCO order.
"""
import queue, struct, subprocess, sys, threading, time
from pathlib import Path
import numpy as np

KEEP = 3
MODEL = str(Path(__file__).parent / "models/yolo11x-pose.pt")
NOSE, L_EYE, R_EYE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_HIP, R_HIP = 0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 12

def display_size(video):
    """Size after rotation: read it off the PNG header of the first decoded frame."""
    png = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"],
                         capture_output=True, check=True).stdout
    return struct.unpack(">II", png[16:24])

def run(video, out, model=MODEL, imgsz=960, batch=64, device=0):
    import torch
    from ultralytics import YOLO
    W, H = display_size(video)
    s = imgsz / max(W, H)
    sw, sh = round(W * s / 2) * 2, round(H * s / 2) * 2
    pw, ph = -(-sw // 32) * 32, -(-sh // 32) * 32  # the net wants multiples of 32: pad right and bottom
    # ffmpeg scales and pads, so Python only moves bytes to the GPU
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", video, "-vsync", "passthrough", "-vf",
                            f"scale={sw}:{sh},pad={pw}:{ph}:0:0", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                           stdout=subprocess.PIPE, bufsize=1 << 26)
    net = YOLO(model)
    size = pw * ph * 3
    kpts, boxes, t0 = [], [], time.time()
    q = queue.Queue(4)  # decode on a thread: otherwise ffmpeg stalls on the pipe while the GPU works, halving speed
    def feed():
        while buf := dec.stdout.read(size * batch):
            q.put(buf)
        q.put(None)
    threading.Thread(target=feed, daemon=True).start()
    while buf := q.get():
        n = len(buf) // size
        x = torch.frombuffer(bytearray(buf[:n * size]), dtype=torch.uint8).view(n, ph, pw, 3).to(device)
        x = x.permute(0, 3, 1, 2).float() / 255
        for r in net.predict(x, device=device, half=True, verbose=False, conf=0.25):
            k, b = np.zeros((KEEP, 17, 3), np.float16), np.zeros((KEEP, 4), np.float16)
            if r.boxes is not None and len(r.boxes):
                xy = r.boxes.xyxy
                top = ((xy[:, 2] - xy[:, 0]) * (xy[:, 3] - xy[:, 1])).argsort(descending=True)[:KEEP]
                m = len(top)
                k[:m] = r.keypoints.data[top].cpu().numpy()
                b[:m] = xy[top].cpu().numpy()
                k[:m, :, 0] /= sw; k[:m, :, 1] /= sh
                b[:m, 0::2] /= sw; b[:m, 1::2] /= sh
            kpts.append(k); boxes.append(b)
    if dec.wait():
        sys.exit(f"ffmpeg failed on {video}")
    dt = time.time() - t0
    tmp = Path(out).with_suffix(".tmp.npz")  # a killed run must not leave a half file that `all` would skip
    np.savez_compressed(tmp, kpts=np.array(kpts), boxes=np.array(boxes), model=model, imgsz=imgsz)
    tmp.replace(out)
    print(f"{len(kpts)} frames in {dt:.1f}s = {len(kpts) / dt:.0f} fps ({W}x{H} -> {pw}x{ph}, {model}, batch {batch})")

def run_all(videos, devices):
    import db, store
    # a video's folder is store/<role>/<file name>/, made by `clean.py prep`; unprepped videos are skipped
    todo = [(str(v), str(store.ROOT / r / v.stem / "pose.npz")) for v in sorted(Path(videos).iterdir())
            for r in db.ROLE if (store.ROOT / r / v.stem / "tiles.json").exists()]
    todo = [(v, o) for v, o in todo if not Path(o).exists()]
    print(f"{len(todo)} videos to do on GPUs {devices}")
    def work(i):
        for v, o in todo[i::len(devices)]:
            subprocess.run([sys.executable, __file__, v, o, "--device", devices[i]])
    ts = [threading.Thread(target=work, args=(i,)) for i in range(len(devices))]
    [t.start() for t in ts]; [t.join() for t in ts]

if __name__ == "__main__":
    a = sys.argv[1:]
    opt = {a[i][2:]: a[i + 1] for i in range(len(a)) if a[i].startswith("--")}
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    if pos[0] == "all":
        run_all(pos[1], opt.get("devices", "0").split(","))
    else:
        run(pos[0], pos[1], opt.get("model", MODEL), int(opt.get("imgsz", 960)), int(opt.get("batch", 64)),
            int(opt.get("device", 0)))
