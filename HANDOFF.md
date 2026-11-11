# 前端交接

下一步：用 [shadcn-admin](https://github.com/satnaing/shadcn-admin) 做一个 macOS 本地网页前端，能浏览素材库、人工审核挥拍标签、并排看对比。后端已经稳定，见 `README.md`。

## 后端现状（提交 90596c6，分支 unify-data-model）

- 清洗管线、素材库、对比图都能跑。库里有 2 个教练视频（62 拍，23 拍可用）和 5 段用户视频（64 个候选，每段 1 拍可用）。
- 后端没有 HTTP 服务。前端要读的数据目前只能用 `python3 proto/db.py` 导出成 JSON。
- 看图标注由 Claude 子代理完成，代码不调用视觉模型。现有标签全部来自 Claude，没有人工真值。
- 姿态关键点已经算好、入库，但还不参与打标签。

## 数据

`db.library(c)` 返回前端要的一切，结构如下：

```jsonc
{
  "vocab": { "kind": {...}, "camera": {...}, "racket_side": {...}, "confidence": {...}, "phase": {...}, "role": {...} },
  "videos": [{
    "id": "a418482773d9", "role": "coach", "name": "转换重心",
    "src": "/Users/hong/Downloads/261109杀球模仿/转换重心.mp4",   // 源视频，本机绝对路径
    "fps": 30.0, "duration": 845.4, "added": 1794324319.7,
    "segments": [{ "id": "a418482773d9_s0015830", "t0": 15.83, "t1": 33.2, "kind": "talk",
                   "text": "转写文字", "clip": "coach/转换重心/clips/00m15.830s.mp4" }],
    "swings": [{ "id": "a418482773d9_0050900", "segment_id": "...", "t0": 50.3, "t1": 51.33,
                 "box": [0.38, 0.0, 0.64, 1.0],                  // 球员区域，占画面的比例 x0 y0 x1 y1
                 "sheet": "coach/转换重心/swings/00m50.900s.jpg",
                 "label": { "usable": true, "camera": "rear_oblique", "face_visible": true, "racket_side": "left",
                            "confidence": "high", "backswing": 50.3, "racket_low": 50.767, "hit": 50.9,
                            "follow": 51.3, "note": "...", "source": "claude" } }]
  }]
}
```

- 时间一律是源视频里的秒。前端不要用帧号。
- 字段和枚举值是英文，中文显示名从 `vocab` 取，前端不要自己写中文映射。
- `clip`、`sheet` 是相对 `store/` 的路径。
- 标签分 4 层：`model` < `pose` < `claude` < `human`，后者覆盖前者。`label.source` 是生效的最高层。人工在前端改的标签写 `human` 层，不覆盖下面的层，删掉就能回退。
- 标签写入前必须经过 `db.check_label`。它拒绝未知字段和未知枚举值，也拒绝阶段时间乱序，以及 `usable` 为真却缺 `backswing`、`racket_low` 或 `hit` 的标签。报错信息可以直接给用户看。
- `kind` 为 `demo` 或 `wrong_demo` 的片段才有挥拍。

## 文件

| 路径 | 内容 |
|---|---|
| `proto/store/lens.db` | SQLite 素材库 |
| `store/<role>/<视频名>/clips/<时间>.mp4` | 片段预览，360p，最长 30 秒 |
| `store/<role>/<视频名>/swings/<时间>.jpg` | 挥拍缩略图网格 |
| `store/<role>/<视频名>/pose.npz` | 每帧关键点 `kpts[帧, 3 人, 17 点, (x, y, 置信度)]`，坐标是画面比例 |
| `store/compare/<视频名>_<时间>.jpg` | 静态对比图 |
| 源视频 | 本机路径存在 `video.src` 里 |

## 建议先补的 API

用 FastAPI，新建 `proto/api.py`，只监听 `127.0.0.1`。

| 接口 | 做什么 |
|---|---|
| `GET /api/library` | 返回 `db.library(c)` |
| `GET /store/{path}` | 静态返回 store 下的文件 |
| `GET /api/videos/{id}/source` | 按 `video.src` 流式返回源视频，要支持 Range，前端逐帧拖动靠它 |
| `PUT /api/swings/{id}/label` | `db.set_label(c, id, "human", body)`，`ValueError` 转成 400 |
| `DELETE /api/swings/{id}/label` | 删掉 `human` 层 |
| `GET /api/swings/{id}/match` | 用 `compare.pick` 和 `compare.times` 返回匹配的教练挥拍和两边对齐的时间点，前端用视频跳转来渲染，不用 jpg |

## 页面

1. **素材库**：视频表格（角色、机位、拍数、可用数），点进去看片段和挥拍。
2. **挥拍审核**：缩略图网格加源视频播放器，编辑 `usable`、机位和 4 个阶段时间，保存到 `human` 层。人工真值集从这里来。
3. **对比**：教练和用户上下两行，按阶段对齐，每个阶段能逐帧前后拖动。
4. 诊断、要点卡以后再做，见 `DESIGN.md`。

## shadcn-admin

- 技术栈：Vite 8、React 19、TypeScript、TanStack Router / Query / Table、Tailwind 4、zod、zustand，MIT 协议。
- 放在仓库的 `web/` 下。去掉 Clerk 登录和示例页面（tasks、users、chats、apps），保留布局、侧边栏、表格和主题。
- 在 `vite.config` 里把 `/api` 和 `/store` 代理到后端。

## 注意

- 教练视频和由它生成的一切只在本地和内网服务器用，不进仓库，不上传第三方。
- 后端只监听本机，不监听 `0.0.0.0`。
- 浏览器 `<video>` 的 `currentTime` 跳转对手机的可变帧率视频不精确。逐帧显示要用 `requestVideoFrameCallback` 读实际帧时间，以库里的秒为准。
- 一部分旧标签的 `note` 里还留着旧帧号，比如"（1523）"，显示时别当成时间。
- 服务器：`ssh ubuntu-8-179`，只用密钥。同步命令见 `README.md`。
