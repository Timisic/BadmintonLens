"""Phase labeling via local magpie gateway (Anthropic Messages API)."""
import base64, io, json, os, re
import anthropic

# default Qwen on DashScope; COACH_* switch to any OpenAI-format (compatible-mode) or Anthropic-format endpoint
MODEL = os.environ.get("COACH_MODEL", "qwen3.6-plus")
client = anthropic.Anthropic(base_url=os.environ.get("COACH_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                             api_key=os.environ.get("COACH_API_KEY") or os.environ.get("DASHSCOPE_API_KEY", "unset"))
# DeepSeek (COACH_BASE_URL=https://api.deepseek.com/anthropic, COACH_MODEL=deepseek-flash) thinks by default; labels don't need it
EXTRA = {"thinking": {"type": "disabled"}} if "deepseek" in client.base_url.host else {}
PHASES = ["准备", "引拍侧身", "拍头最低点", "击球点", "随挥收拍"]

def ask(img, prompt, max_tokens=800):
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=85)
    if "compatible-mode" in str(client.base_url):  # DashScope (Qwen) speaks the OpenAI format
        return ask_openai(buf.getvalue(), prompt, max_tokens)
    r = client.messages.create(model=MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                     "data": base64.b64encode(buf.getvalue()).decode()}},
        {"type": "text", "text": prompt}]}], **EXTRA)
    text = next(b.text for b in r.content if b.type == "text")  # thinking models put a thinking block first
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)), r.usage, text

def ask_openai(jpg, prompt, max_tokens):
    import urllib.request
    from types import SimpleNamespace
    body = {"model": MODEL, "max_tokens": max_tokens, "enable_thinking": False, "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpg).decode()}},
        {"type": "text", "text": prompt}]}]}
    req = urllib.request.Request(str(client.base_url).rstrip("/") + "/chat/completions", json.dumps(body).encode(),
                                 {"Authorization": "Bearer " + client.api_key, "Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    text = r["choices"][0]["message"]["content"]
    u = r["usage"]
    return json.loads(re.search(r"\{.*\}", text, re.S).group(0)), \
        SimpleNamespace(input_tokens=u["prompt_tokens"], output_tokens=u["completion_tokens"]), text

COARSE = """这是一次羽毛球杀球（空挥，可能没有球）的缩略图网格，每格左上角是帧号，按时间顺序排列（60fps）。
请为以下阶段各选出最能代表的那一帧帧号：准备、引拍侧身、拍头最低点、击球点、随挥收拍。
如果某阶段落在两格之间，给出你估计的帧号区间 [起, 止]。
只输出 JSON：{"准备": 帧号, "引拍侧身": 帧号, "拍头最低点": [起, 止], "击球点": [起, 止], "随挥收拍": 帧号, "备注": "一句话"}"""

FINE = """这是同一次杀球在击球前后的逐帧网格（60fps，每格左上角为帧号）。空挥没有球，击球点指拍面挥到最高、最前、速度最快的那一帧。
拍头最低点指引拍后拍头在背后下沉到最低的那一帧（如果不在本网格内则为 null）。
只输出 JSON：{"拍头最低点": 帧号或null, "击球点": 帧号, "置信度": "高/中/低", "备注": "一句话"}"""
