#!/bin/bash
# 全部自检：Python 自检、前端测试、类型检查和构建、lint、格式、死代码（knip）
set -euo pipefail
cd "$(dirname "$0")"
(cd proto && python3 test_db.py && python3 test_api.py)
cd web && pnpm test && pnpm build && pnpm lint && pnpm format:check && pnpm knip
