"""Timestamped transcript via DashScope Fun-ASR flash. Key from env DASHSCOPE_API_KEY."""
import base64, json, os, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
MODEL = os.environ.get("ASR_MODEL", "fun-asr-flash-2026-06-15")
CHUNK = 60

def chunk(path, start):
    wav = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(CHUNK), "-i", path, "-vn",
                          "-ac", "1", "-ar", "16000", "-f", "wav", "-"], capture_output=True, check=True).stdout
    body = {"model": MODEL, "input": {"messages": [{"role": "user", "content": [
        {"audio": "data:audio/wav;base64," + base64.b64encode(wav).decode()}]}]},
        "parameters": {"format": "wav", "sample_rate": 16000}}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {
        "Authorization": "Bearer " + os.environ["DASHSCOPE_API_KEY"], "Content-Type": "application/json"})
    out = json.loads(urllib.request.urlopen(req, timeout=180).read())["output"]["output"]
    sents = out.get("sentences") or ([out["sentence"]] if "sentence" in out else [])
    return [{"t0": start + s["begin_time"] / 1000, "t1": start + s["end_time"] / 1000, "text": s["text"],
             "words": [{"t0": start + w["begin_time"] / 1000, "t1": start + w["end_time"] / 1000,
                        "w": w["text"] + w.get("punctuation", "")} for w in s.get("words", [])]} for s in sents]

if __name__ == "__main__":
    path, out = sys.argv[1], sys.argv[2]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                               capture_output=True, text=True).stdout)
    with ThreadPoolExecutor(4) as ex:
        res = [s for part in ex.map(lambda st: chunk(path, st), range(0, int(dur) + 1, CHUNK)) for s in part]
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    for s in res: print(f"{s['t0']:7.1f}-{s['t1']:6.1f} {s['text']}")
