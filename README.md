# BadmintonLens

把你的杀球和同机位的教练示范逐阶段并排对比。设计见 `DESIGN.md`。

## 结构

```
proto/
  clean.py     清洗管线：prep → swings → fine → ingest
  db.py        SQLite 素材库和全部词表
  store.py     派生文件位置，与服务器同步
  compare.py   生成对比图
  pose.py      GPU 姿态关键点（在服务器上跑）
  asr.py       没有 SRT 时的语音转写
  test_db.py   自检
  store/       派生文件（不进仓库）
    lens.db                 素材库
    coach/<视频名>/         教练视频：缩略图、挥拍图、预览片段、标签
    user/<视频名>/          你的视频，同上
    compare/<视频名>_<时间>.jpg   对比图
```

视频目录里的文件按它在视频里的时间命名，例如 `swings/01m04.167s.jpg`。

服务器 `ubuntu-8-179:~/badminton-lens/` 是同样的布局：`pose.py db.py store.py`、`store/`、`videos/`（源视频）、`models/`（姿态权重）、`.venv/`。

## 用法

在 Claude Code 里说"清洗这个教练视频 <路径>"或"处理我的挥拍视频 <路径>"，`clean-coach-video` skill 会跑完全程。看图标注由 Claude 子代理完成，代码不调用视觉模型。

```bash
cd proto
python3 clean.py prep "<视频>"     # 自己的视频加 --user
python3 clean.py swings "<视频>"
python3 clean.py fine "<视频>"
python3 clean.py ingest "<视频>"
python3 compare.py                 # 输出到 store/compare/
```

姿态关键点：

```bash
rsync -a pose.py db.py store.py ubuntu-8-179:badminton-lens/
ssh ubuntu-8-179 'cd badminton-lens && .venv/bin/python pose.py all videos --devices 0,1,2'
LENS_REMOTE=ubuntu-8-179:badminton-lens/store python3 store.py pull
```

## 约定

- 时间一律是源视频里的秒，字段和枚举一律英文，中文显示名只在 `db.py`。
- 库里的 id 由内容哈希和时间组成，重跑不变；目录和文件名用视频名和时间，方便人看。
- 标签分层，后者覆盖前者：`model` < `pose` < `claude` < `human`。
- 环境变量：`LENS_STORE` 存储根目录，`LENS_REMOTE` 同步目标，`LENS_VIDEOS` 源视频根目录，`LENS_FONT` 中文字体。
- 依赖：Python 3.10+、ffmpeg、rsync、`pip install pillow numpy`。

## 素材

教练视频和由它生成的一切只在本地和内网服务器使用，不进仓库。字幕优先读视频旁的 SRT；没有时，设置了 `DASHSCOPE_API_KEY` 才调用阿里语音转写。
