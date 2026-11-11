// node shoot.mjs <name> <path> [--dark] [--mobile] [--full] [--do '<js run with page>']
// Screenshot one route of the verify instance into .verify/evidence/<name>.png; exits 1 on console or page errors.
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const { chromium } = createRequire(path.join(root, 'web/'))('playwright')
const [name, route, ...flags] = process.argv.slice(2)
const has = (f) => flags.includes(f)
const act = flags[flags.indexOf('--do') + 1]

// System Chrome, not Playwright's Chromium: the user's phone video is HEVC, which only the real browser decodes.
const browser = await chromium.launch({ channel: 'chrome' })
const page = await browser.newPage({
  viewport: has('--mobile') ? { width: 390, height: 844 } : { width: 1440, height: 900 },
  colorScheme: has('--dark') ? 'dark' : 'light',
})
const errors = []
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
page.on('pageerror', (e) => errors.push(String(e)))
await page.goto(`http://localhost:5273${route}`, { waitUntil: 'networkidle' })
if (has('--do')) console.log(await new Function('page', `return (async () => { ${act} })()`)(page))
await page.waitForTimeout(400)
const out = path.join(root, '.verify/evidence', `${name}.png`)
await page.screenshot({ path: out, fullPage: has('--full') })
await browser.close()
console.log(out)
if (errors.length) { console.error(errors.join('\n')); process.exit(1) }
