#!/bin/bash
# 一条命令启动网页：前端有改动就重新构建，然后起 API（它同时提供网页）并打开浏览器。Ctrl-C 停止。
set -euo pipefail
cd "$(dirname "$0")"
URL=http://127.0.0.1:8000
if curl -sf "$URL/api/library" >/dev/null; then echo "已经在运行：$URL"; open "$URL"; exit; fi
[ -d web/node_modules ] || (cd web && pnpm install --frozen-lockfile)
if [ ! -f web/dist/index.html ] || [ -n "$(find web/src web/index.html web/package.json -newer web/dist/index.html -print -quit)" ]; then
  (cd web && pnpm build)
fi
(until curl -sf "$URL/api/library" >/dev/null; do sleep 0.3; done; open "$URL") &
cd proto && exec python3 api.py
