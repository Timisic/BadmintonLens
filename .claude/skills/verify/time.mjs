// node time.mjs <path> [n]   Milliseconds from navigation until every <video> on the page shows its frame.
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const { chromium } = createRequire(path.join(root, 'web/'))('playwright')
const [route, n = 3] = process.argv.slice(2)
const browser = await chromium.launch({ channel: 'chrome' })
for (let i = 0; i < n; i++) {
  // a fresh context per run, closed after it: no cache carried over, and no video stream left open to hang close()
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await context.newPage()
  await page.goto(`http://localhost:5273${route}`, { waitUntil: 'commit' })
  const ms = await page.evaluate(() => new Promise((done) => {
    const check = () => {
      const v = [...document.querySelectorAll('video')]
      if (v.length && v.every((x) => x.readyState >= 2 && !x.seeking)) done(Math.round(performance.now()))
      else requestAnimationFrame(check)
    }
    check()
  }))
  console.log(ms, 'ms', await page.locator('video').count(), 'videos')
  await context.close()
}
await browser.close()
