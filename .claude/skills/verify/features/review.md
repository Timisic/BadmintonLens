# Swings (route /review)

## Sub-features
- Grid of every usable swing as a picture of its hit, grouped by video, with the camera name on the group. Toggle 我 / 教练.
- The bin button on a card deletes the swing (`usable: false` in the human layer). Toggle `已删除 N` shows deleted swings and the candidates the pose rejected, each with a 恢复 button. A toast offers 撤销.
- Swing page: player (只看球员 / 整个画面), 机位 with four values, 击球点 with `设为当前帧`, then 对比, 删除 or 恢复, and 回到自动识别 when a person changed something. Every change saves at once.
- A missing or undecodable source shows `视频打不开` in the picture.

## How to get to it (user POV)
Sidebar 挥拍, then click a picture. Or click a swing on a video page. URL: `/review?who=coach&deleted=true`, `/review/<swingId>`.

## Driving it with shoot.mjs
```bash
node .claude/skills/verify/shoot.mjs swing-fix /review/<swingId> --do '
  await page.waitForTimeout(1500)
  await page.getByRole("button", { name: "下一帧" }).first().click()
  await page.getByRole("button", { name: "设为当前帧" }).click()
  await page.getByRole("radio", { name: "右侧面" }).click()
  await page.waitForTimeout(600)'
```
Proof: `/api/library` shows the new `hit` and `camera` with `source: "human"`. Then 回到自动识别 brings the pose values back, 删除 returns to the grid and the label reads `usable: false`, and 恢复 under `/review?deleted=true` makes it `true` again.

On the grid, reach one card with `page.locator('li:has(a[href*="<swingId>"])').getByRole("button", { name: "删除" })`.

Stepping must be exact: 12 presses of `ArrowRight` give 12 new frame times and 12 of `ArrowLeft` return to the first. Read the time from `span.min-w-16` under the picture.

## Gotchas
- The picture is `/api/swings/<id>/thumb`, cut from `play.mp4`. Without that file the card is an empty grey box.
- A restored candidate the pose never read has no hit, so it is not comparable until `设为当前帧`.
- Arrow keys and space go to the player unless a button has focus.
