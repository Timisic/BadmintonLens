# Review

## Sub-features
- Left list of swings grouped by video. A dot means usable, a person-check icon means human reviewed. Filters: video, 全部 / 可用 / 未审.
- Player on the source video with frame stepping, a scrubber limited to the swing, and phase marks. Tabs: 视频, 只看球员 (cropped to the player box), 连拍图.
- Form: usable yes/no, four phase times, and a collapsed section for camera, racket side, face and note.
- Save writes the human layer. 撤销 removes it and the lower layer shows again.

## How to get to it (user POV)
Sidebar 审核, then pick a swing. Or click a swing on a video page.

## Driving it with shoot.mjs
```bash
node .claude/skills/verify/shoot.mjs review-save /review/<swingId> --do '
  await page.waitForTimeout(1200)
  await page.getByRole("button", { name: "跳到击球点" }).last().click()
  for (let i = 0; i < 6; i++) { await page.keyboard.press("ArrowRight"); await page.waitForTimeout(250) }
  await page.keyboard.press("4")
  await page.getByRole("button", { name: "保存" }).click()
  await page.getByRole("button", { name: "撤销" }).waitFor()'
```
Proof: the 撤销 button appears, and `/api/library` shows `source: "human"` with the new `follow` for that swing. Then click 撤销 and check `human labels 0` in doctor.

## Gotchas
- A phase key captures the frame on screen. HEVC seeks take a moment, so wait about 250ms after each step before pressing `1`–`4`.
- `跳到<阶段>` names two buttons: the mark on the scrubber and the time in the form. Use `.last()` for the form one.
- The backend rejects phase times out of order with a 400. The message shows in the form as is. Set 随挥 after 击球点.
- The human layer cannot clear a phase a lower layer set.
- The layout is for desktop. At 390px it is usable but cramped.
