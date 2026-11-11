#!/bin/bash
# up | doctor | down — an isolated API + web pair on a scratch copy of the library
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
V="$ROOT/.verify"; API_PORT=8765; WEB_PORT=5273
alive() { [ -f "$V/$1.pid" ] && kill -0 "$(cat "$V/$1.pid")" 2>/dev/null; }
case "${1:-}" in
up)
  mkdir -p "$V/evidence"
  if [ -d "$ROOT/proto/store" ]; then rsync -a --delete "$ROOT/proto/store/" "$V/store/"; else mkdir -p "$V/store"; fi
  [ -d "$ROOT/web/node_modules" ] || (cd "$ROOT/web" && pnpm install --frozen-lockfile)
  alive api || { (cd "$ROOT/proto" && LENS_STORE="$V/store" exec python3 -m uvicorn api:app --host 127.0.0.1 --port $API_PORT) >"$V/api.log" 2>&1 & echo $! >"$V/api.pid"; }
  alive web || { (cd "$ROOT/web" && LENS_API="http://127.0.0.1:$API_PORT" exec node node_modules/vite/bin/vite.js --port $WEB_PORT --strictPort) >"$V/web.log" 2>&1 & echo $! >"$V/web.pid"; }
  for _ in $(seq 60); do curl -sf "http://localhost:$WEB_PORT/api/library" >/dev/null && exec "$0" doctor; sleep 0.5; done
  echo "not ready; see $V/api.log and $V/web.log"; exit 1;;
doctor)
  alive api && alive web || { echo "FAIL: not running (run.sh up)"; exit 1; }
  curl -sf "http://localhost:$WEB_PORT/api/library" | python3 -c "
import json,sys; l=json.load(sys.stdin); s=[x for v in l['videos'] for x in v['swings']]
print('OK http://localhost:$WEB_PORT  videos', len(l['videos']), 'swings', len(s), 'human labels', sum(x['label'].get('source')=='human' for x in s))";;
down)
  for n in api web; do alive $n && kill "$(cat "$V/$n.pid")"; rm -f "$V/$n.pid"; done; rm -rf "$V/store"; echo "stopped; evidence kept in $V/evidence";;
*) echo "usage: run.sh up|doctor|down"; exit 2;;
esac
