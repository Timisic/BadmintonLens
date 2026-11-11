# BadmintonLens

把你的杀球和同机位的教练示范逐阶段并排对比。设计见 `DESIGN.md`，前端交接见 `HANDOFF.md`。

## 结构

```
proto/
  clean.py     清洗管线：prep → swings → fine → ingest
  db.py        SQLite 素材库和全部词表
  store.py     派生文件位置，与服务器同步
  compare.py   对比的配对规则；从姿态读出真挥拍、击球点和机位；教练示范精选
  diagnose.py  两拍差在哪，和教练讲到它的字幕片段
  pose.py      GPU 姿态关键点（在服务器上跑）
  asr.py       没有 SRT 时的语音转写
  api.py       本机 HTTP API，前端读写素材库都走它
  test_db.py   自检
  test_api.py  API 自检
  store/       派生文件（不进仓库）
    lens.db                 素材库
    coach/<视频名>/         教练视频：缩略图、挥拍图、预览片段、标签
    user/<视频名>/          你的视频，同上
    compare/<视频名>_<时间>.jpg   对比图
web/           本地网页前端，基于 shadcn-admin（MIT，见 web/LICENSE）
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
python3 clean.py ingest "<视频>"   # 同时生成网页播放用的 play.mp4
python3 clean.py play              # 给库里还没有 play.mp4 的视频补一份
python3 clean.py relocate "<目录>" # 源视频挪了位置：按内容在目录下重新找到并更新路径
python3 compare.py refine          # 有 pose.npz 之后：认出真挥拍，读出击球时间和机位（pose 层）。新视频入库后要重跑
python3 compare.py standard        # 教练每个机位只留最好的一拍示范，其余教练挥拍删掉；片段和字幕保留
```

姿态关键点：

```bash
rsync -a pose.py db.py store.py ubuntu-8-179:badminton-lens/
ssh ubuntu-8-179 'cd badminton-lens && .venv/bin/python pose.py all videos --devices 0,1,2'
LENS_REMOTE=ubuntu-8-179:badminton-lens/store python3 store.py pull
```

## 前端

开两个终端：

```bash
cd proto && python3 api.py         # API，只监听 127.0.0.1:8000
cd web && pnpm install && pnpm dev # 网页，http://localhost:5173
# 或者一条命令：./start.sh（需要时构建前端，起 API 并打开 http://127.0.0.1:8000）
```

Vite 把 `/api` 和 `/store` 代理到 API，所以浏览器只访问 5173 端口。三个页面：

- **素材库**：视频表格，点进去看片段和挥拍。
- **挥拍**：每一拍一张击球瞬间的图。只有留下和删除两个决定，删掉的在「已删除」里可以恢复。点进一拍可以改机位和击球点，每次改动立即存到 `human` 层。
- **对比**：先选机位，再从缩略图里各选一拍，教练只列同机位的示范。「逐帧」是离击球点相同时刻的七帧，「同步慢放」是两边在同一个时钟上循环播放。下面的「差在哪」列出教练做到而我没做到的地方，圈出位置，并配上教练讲到它的字幕和原片片段（带声音，来自源视频）。

网页播放的是 `store/<角色>/<视频名>/play.mp4`：H.264、半秒一个关键帧、索引在文件头，每一帧的时间与源视频完全一致（生成时逐帧校验）。它跟着 store 同步，所以源视频挪走或换一台机器，网页照常能看。没有这份文件时退回源视频。

依赖：Node 20.19+、pnpm、`pip install fastapi uvicorn httpx`（httpx 只有自检用）。自检：`cd proto && python3 test_db.py && python3 test_api.py`，`cd web && pnpm test && pnpm build && pnpm lint`（`pnpm test` 用本机的 Chrome）。

## 约定

- 时间一律是源视频里的秒，字段和枚举一律英文，中文显示名只在 `db.py`。
- 库里的 id 由内容哈希和时间组成，重跑不变；目录和文件名用视频名和时间，方便人看。
- 标签分层，后者覆盖前者：`model` < `claude` < `pose` < `human`。`pose` 层管可用、击球时间和机位。标签只有三项：`usable`（否就是删除）、`camera`（正面、左侧面、右侧面、背后，教练和我同一套）、`hit`。
- 机位看两肩的左右顺序：引拍和击球后各看一次，对着镜头还是背着镜头。同一个三脚架的视频取多数。
- 「差在哪」只比关节的高低差，以躯干长度为单位，所以不受机位远近影响。现有五项：持拍侧抬腿、击球高度、持拍肩顶起、非持拍手上举和下拉。
- 对比只以击球点为锚：上下两行取离击球点相同的时刻，所以一拍只要标为可用并有击球点就能对比。
- 环境变量：`LENS_STORE` 存储根目录，`LENS_REMOTE` 同步目标，`LENS_VIDEOS` 源视频根目录，`LENS_FONT` 中文字体。
- 依赖：Python 3.10+、ffmpeg、rsync、`pip install pillow numpy`。

## 素材

教练视频和由它生成的一切只在本地和内网服务器使用，不进仓库。字幕优先读视频旁的 SRT；没有时，设置了 `DASHSCOPE_API_KEY` 才调用阿里语音转写。
