# BadmintonLens

本地运行的羽毛球动作对照工具。先把教练视频清洗成按机位、按阶段标注的挥拍库，再把你自己拍的挥拍和同机位的教练示范逐阶段并排对比。MVP 只做杀球。

## 目录

- `DESIGN.md` 是设计文档。
- `proto/clean.py` 是教练视频清洗管线（prep、classify、swings、phases、fine、table、review）。
- `proto/label.py` 封装视觉模型调用，默认走 DashScope 上的 Qwen。
- `proto/compare_angle.py` 从清洗好的库里按 脸 / 拍位 / 机位 自动匹配示范，生成对比图。
- `proto/.claude/skills/clean-coach-video/` 是 Claude Code 的 skill，让 Claude 跑管线并复核模型标签。

## 依赖

Python 3、ffmpeg、`pip install pillow numpy anthropic`。

## 用法

```bash
export DASHSCOPE_API_KEY=...   # 只放环境变量，不要写进文件
cd proto
python3 clean.py prep "<教练视频>"   # 依次跑 classify / swings / phases / fine --model / table
python3 compare_angle.py              # 用户片段配置在 user_clips.json
```

清洗结果在 `proto/work/<视频名>/segments.json`，这是前端读取的数据，字段只增不改。

## 素材

教练视频及由它生成的帧图、转写和清洗结果只在本地使用，已在 `.gitignore` 里排除，不要提交。
