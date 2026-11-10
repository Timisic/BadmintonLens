# BadmintonLens

本地运行的羽毛球动作对照工具。先把教练视频清洗成按机位、按阶段标注的挥拍库，再把你自己拍的挥拍和同机位的教练示范逐阶段并排对比。MVP 只做杀球。

## 目录

- `DESIGN.md` 是设计文档。
- `proto/clean.py` 是清洗管线（prep、swings、fine、ingest），教练视频和你自己的视频都走它。代码不调用模型。
- `proto/db.py` 是素材库（SQLite）和全部词表。`python3 db.py` 把整个库导出成 JSON，前端读这个。
- `proto/store.py` 是存储接口，负责派生文件的位置和与内网服务器的同步。
- `proto/compare.py` 从库里按机位自动匹配教练示范，生成对比图。
- `proto/.claude/skills/clean-coach-video/` 是 Claude Code 的 skill。看图标注由 Claude 子代理完成。

## 依赖

Python 3.10+、ffmpeg、rsync、`pip install pillow numpy`（Pillow 10.1 以上）。

## 用法

在 Claude Code 里说"清洗这个教练视频 <路径>"或"处理我的挥拍视频 <路径>"，skill 会跑完整个流程。手动跑：

```bash
cd proto
python3 clean.py prep "<视频>"        # 自己的视频加 --user
python3 clean.py swings "<视频>"      # 之后由 Claude 写 phase_labels.json
python3 clean.py fine "<视频>"        # 之后由 Claude 写 fine_labels.json
python3 clean.py ingest "<视频>"      # 校验标签，写入 store/lens.db
python3 compare.py                    # 对比图在 store/compare/
python3 test_db.py                    # 自检
```

## 数据约定

- 时间一律是源视频里的秒。帧号只存在于缓存里，不进库。
- 字段名和枚举值一律英文（`hit`、`racket_low`、`rear_oblique`），中文显示名只在 `db.py` 的词表里。
- 视频 id 是内容哈希，片段和挥拍的 id 由视频 id 加时间组成，重跑不变。
- 标签分层，后者覆盖前者：`model` < `pose` < `claude` < `human`。

## 存储

派生文件（缩略图、预览片段、数据库）都在 `proto/store/`，库里只记相对路径。

| 环境变量 | 作用 |
|---|---|
| `LENS_STORE` | 本地存储根目录，默认 `proto/store`。也可以指向挂载的共享盘。 |
| `LENS_REMOTE` | rsync 目标，例如 `ubuntu-8-179:badminton-lens/store`。只用 SSH 密钥，不写密码。 |
| `LENS_VIDEOS` | 源视频根目录。设了以后库里记相对路径，换机器也能找到源视频。 |
| `LENS_FONT` | 对比图用的中文字体，默认 macOS 的黑体。 |

```bash
LENS_REMOTE=ubuntu-8-179:badminton-lens/store python3 store.py push
```

## 素材

教练视频及由它生成的帧图、转写和清洗结果只在本地和内网服务器使用，已在 `.gitignore` 里排除，不要提交。没有 SRT 的视频只有在设置了 `DASHSCOPE_API_KEY` 时才会调用云端语音转写，否则不带字幕分类。
