# Compare

## Sub-features
- Pick one of my videos (`选我的视频`, with its camera and swing count), then one of its swings from numbered pictures. On the right the coach demos filmed from the same camera, best first.
- Either side leads. `?coach=<id>` alone brings one of my swings filmed from the same place.
- Tab 逐帧: seven stills per row at the same seconds from the hit, coach above me. The centre column is `击球`.
- Tab 同步慢放: both swings side by side on one clock, looping from −0.9 s to +0.7 s around the hit, at 0.5×, 0.25× or 0.1×.
- Section 诊断: one sentence for the whole video, then a table of every check in swing order (phase, what, this swing as a percentage of the coach, how many swings of the video fall short, verdict). Below it one card per check that this swing or most of the video falls short on: three stills per side at the same seconds from the hit with a ring on the joint, and up to three passages of a coach explaining it (text plus the source video at that time, with sound).

## How to get to it (user POV)
Sidebar 对比. Or the 对比 button on a swing page. URL: `/compare?swing=<mine>&coach=<coach>`, either or both.

## Driving it with shoot.mjs
```bash
node .claude/skills/verify/shoot.mjs compare /compare --full --do '
  await page.waitForTimeout(3000)
  return [await page.locator("article h3").allTextContents(),
    await page.locator("article video").evaluateAll(v => v.map(x => [x.readyState, Math.round(x.currentTime)]))]'
```
Proof for the findings: the titles match `/api/diagnose?me=&coach=` entries with `short: true`, and each lesson video sits at its `t0`. Proof for playback: in 同步慢放 press `同步播放`, then subtract each swing's `hit` from the two visible videos' times; the offsets agree within a frame.

Pickers: `getByRole("combobox", { name: "选我的视频" })` then `getByRole("option", { name: /5519/ })`; `getByRole("radiogroup", { name: "选我的一拍" }).getByRole("radio").nth(i)` for a swing. The table rows are `tbody tr`.

## Gotchas
- Usable, hit and camera come from `compare.py refine` reading `pose.npz`. Whatever a person set wins.
- The racket hand is the majority over a video's swings, and `refine` always reads a swing in its own window, so a second run changes nothing. A hit that looks off in 逐帧 means the pose was misread: fix it on the swing page.
- Lesson videos need the source file (`?sound=1`); `play.mp4` is silent and is the fallback.
- Under about 700px the stills keep their width and scroll sideways.
