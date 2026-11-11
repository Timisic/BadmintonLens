import { createRef } from 'react'
import { createRoot } from 'react-dom/client'
import { expect, it, vi } from 'vitest'
import { FramePlayer, type FramePlayerHandle } from './frame-player'
// two seconds of a 30 fps test pattern
import clip from './frame-player.test.webm?url'

vi.mock('@/lib/library', async (real) => ({
  ...(await real<typeof import('@/lib/library')>()),
  sourceUrl: () => clip,
}))

it('steps one frame at a time, there and back', async () => {
  const player = createRef<FramePlayerHandle>()
  const host = document.body.appendChild(document.createElement('div'))
  createRoot(host).render(
    <FramePlayer
      ref={player}
      still
      videoId='x'
      fps={30}
      start={1}
      maxHeight='90px'
    />
  )
  await expect.poll(() => host.querySelector('video')?.readyState).toBe(4)
  const p = player.current!
  const frame = async () => Math.round((await p.shown()) * 30)
  // the picture needs a moment to follow a seek
  const after = async (act: () => void) => {
    act()
    await new Promise((r) => setTimeout(r, 50))
    return frame()
  }

  expect(await frame()).toBe(30)
  const seen = []
  for (let i = 0; i < 12; i++) seen.push(await after(() => p.step(1)))
  expect(seen).toEqual(Array.from({ length: 12 }, (_, i) => 31 + i))
  for (let i = 0; i < 12; i++) await after(() => p.step(-1))
  expect(await frame()).toBe(30)

  // held key: steps arrive faster than seeks land, and still add up
  expect(
    await after(() => {
      for (let i = 0; i < 8; i++) p.step(1)
    })
  ).toBe(38)

  // a seek shows the frame that holds the time, not the nearest one
  expect(await after(() => p.seek(1.03))).toBe(30)
  expect(await after(() => p.seek(0.5))).toBe(15)
})
