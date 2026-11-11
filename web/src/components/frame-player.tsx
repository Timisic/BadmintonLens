import { useEffect, useImperativeHandle, useRef, useState } from 'react'
import { Loader2, Pause, Play, StepBack, StepForward } from 'lucide-react'
import { type Box, clock, sourceUrl } from '@/lib/library'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { IconButton } from '@/components/icon-button'

export type FramePlayerHandle = {
  seek: (t: number) => void
  step: (frames: number) => void
  toggle: () => void
  play: (rate: number) => void
  pause: () => void
  /** Time of the frame on screen, once any seek under way has landed. */
  shown: () => Promise<number>
}

type FramePlayerProps = {
  ref?: React.Ref<FramePlayerHandle>
  videoId: string
  fps: number
  start: number
  /** CSS length the picture may not exceed; its width follows the aspect. */
  maxHeight: string
  box?: Box | null
  /** Scrub bar over this span, with a tick for each mark. */
  range?: [number, number]
  marks?: { t: number; name: string }[]
  /** A cell in a grid of stills: step buttons appear over the picture. */
  still?: boolean
  /** Width over height every picture should share; the box is fitted inside it. */
  frame?: number
  format?: (t: number) => string
  onFrame?: (t: number) => void
}

export function FramePlayer({
  ref,
  videoId,
  fps,
  start,
  maxHeight,
  box,
  range,
  marks = [],
  still,
  frame,
  format = clock,
  onFrame,
}: FramePlayerProps) {
  const video = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(start)
  const [aspect, setAspect] = useState(16 / 9)
  const [playing, setPlaying] = useState(false)
  const [x0, y0, x1, y1] = box ?? [0, 0, 1, 1]
  const ratio = frame ?? (aspect * (x1 - x0)) / (y1 - y0)
  // Scale the picture until the whole box fits the frame, then centre the box.
  // Whatever of the picture lies around the box fills the rest of the frame.
  const scale = Math.min(1 / (x1 - x0), aspect / (ratio * (y1 - y0)))
  const tall = (scale * ratio) / aspect

  // start of the frame on screen, the time we are heading for, and the step
  // that sent us there
  const shown = useRef(start)
  const want = useRef(start)
  const stepping = useRef({ from: start, by: 0, tries: 0 })
  const waiting = useRef<((t: number) => void)[]>([])
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [rate, setRate] = useState(1)

  // A seek shows the frame that holds t. The millisecond is there because a
  // seek to the exact start of a frame can land on the one before it. A step
  // aims for the middle of its frame instead: frames are not evenly spaced.
  const go = (t: number, pad = 0.001) => {
    want.current = t
    video.current!.currentTime = Math.max(0, t + pad)
  }
  const seek = (t: number) => {
    video.current!.pause()
    stepping.current.by = 0
    go(t)
  }
  const step = (frames: number) => {
    const v = video.current!
    v.pause()
    // from where we are heading when a seek is still under way, so held keys add up
    const from = v.seeking ? want.current : shown.current
    stepping.current = { from: shown.current, by: frames, tries: 0 }
    go(from + frames / fps, 0.5 / fps)
  }
  const toggle = () =>
    video.current!.paused ? video.current!.play() : video.current!.pause()
  useImperativeHandle(ref, () => ({
    seek,
    step,
    toggle,
    play: (rate) => {
      video.current!.playbackRate = rate
      video.current!.play()
    },
    pause: () => video.current!.pause(),
    shown: () =>
      video.current!.seeking
        ? new Promise((done) => {
            waiting.current.push(done)
            // a seek that lands on the frame already shown paints nothing new
            setTimeout(() => done(shown.current), 1000)
          })
        : Promise.resolve(shown.current),
  }))

  // Covers a new start in the same video. A new video is positioned once its
  // metadata loads, below.
  useEffect(() => {
    go(start)
  }, [start])

  useEffect(() => {
    video.current!.playbackRate = rate
  }, [rate])

  // Phone video is variable frame rate, so currentTime is only where we asked
  // to be. mediaTime is the timestamp of the frame actually on screen.
  const [from, to] = range ?? [0, Infinity]
  useEffect(() => {
    const v = video.current!
    let id = v.requestVideoFrameCallback(function tick(_now, frame) {
      id = v.requestVideoFrameCallback(tick)
      const t = frame.mediaTime
      const s = stepping.current
      // A frame longer than 1/fps swallows a step. Push on until the picture changes.
      if (s.by && t === s.from && !v.seeking && s.tries++ < 4)
        return go(want.current + Math.sign(s.by) / fps, 0.5 / fps)
      s.by = 0
      // play the swing on a loop
      if (!v.paused && t >= to) v.currentTime = from
      shown.current = t
      setState('ready')
      setTime(t)
      onFrame?.(t)
      waiting.current.splice(0).forEach((done) => done(t))
    })
    return () => v.cancelVideoFrameCallback(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onFrame, from, to])

  const stepButton = (frames: number, className?: string) => (
    <IconButton
      label={frames < 0 ? '上一帧' : '下一帧'}
      variant={still ? 'secondary' : 'ghost'}
      className={cn('size-7', className)}
      onClick={() => step(frames)}
    >
      {frames < 0 ? <StepBack /> : <StepForward />}
    </IconButton>
  )

  return (
    <div
      className='flex flex-col gap-2'
      style={{ width: `min(100%, calc(${maxHeight} * ${ratio}))` }}
    >
      <div
        className='group relative overflow-hidden rounded-lg bg-black'
        style={{ aspectRatio: ratio }}
      >
        <video
          ref={video}
          src={sourceUrl(videoId)}
          muted
          playsInline
          className='absolute max-w-none'
          style={{
            width: `${scale * 100}%`,
            left: `${(0.5 - (scale * (x0 + x1)) / 2) * 100}%`,
            top: `${(0.5 - (tall * (y0 + y1)) / 2) * 100}%`,
          }}
          onLoadedMetadata={({ currentTarget: v }) => {
            setAspect(v.videoWidth / v.videoHeight)
            go(start)
          }}
          onError={() => setState('error')}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        />
        {state === 'loading' && (
          <Loader2 className='absolute inset-0 m-auto size-5 animate-spin text-white/70' />
        )}
        {state === 'error' && (
          <p className='absolute inset-0 flex items-center justify-center bg-black p-3 text-center text-sm text-white'>
            {still
              ? '打不开'
              : '视频打不开。源文件可能被移走了，或者浏览器不支持它的编码。'}
          </p>
        )}
        {still && state === 'ready' && (
          <div className='absolute inset-x-1.5 bottom-1.5 flex justify-between opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100'>
            {stepButton(-1)}
            {stepButton(1)}
          </div>
        )}
      </div>
      {range && (
        <div className='relative pt-4'>
          {marks.map(({ t, name }) => (
            <Tooltip key={name}>
              <TooltipTrigger asChild>
                <button
                  type='button'
                  aria-label={`跳到${name}`}
                  onClick={() => seek(t)}
                  className='absolute top-0 h-3 w-2 -translate-x-1/2 rounded-sm bg-primary/70 hover:bg-primary'
                  style={{
                    left: `${((t - range[0]) / (range[1] - range[0])) * 100}%`,
                  }}
                />
              </TooltipTrigger>
              <TooltipContent>
                {name} {format(t)}
              </TooltipContent>
            </Tooltip>
          ))}
          <Slider
            aria-label='在这一拍里拖动'
            min={range[0]}
            max={range[1]}
            step={1 / fps}
            value={[time]}
            onValueChange={([t]) => seek(t)}
          />
        </div>
      )}
      {still ? (
        <span className='text-center font-mono text-sm tabular-nums'>
          {format(time)}
        </span>
      ) : (
        <div className='flex items-center justify-center gap-1.5'>
          {stepButton(-1)}
          <IconButton
            label={playing ? '暂停' : '播放'}
            variant='ghost'
            className='size-7'
            onClick={toggle}
          >
            {playing ? <Pause /> : <Play />}
          </IconButton>
          {stepButton(1)}
          <Button
            type='button'
            variant='ghost'
            size='sm'
            className='h-7 w-12 font-mono tabular-nums'
            aria-label='播放速度'
            onClick={() => setRate(rate === 1 ? 0.5 : rate === 0.5 ? 0.25 : 1)}
          >
            {rate}×
          </Button>
          <span className='min-w-16 font-mono text-sm tabular-nums'>
            {format(time)}
          </span>
        </div>
      )}
    </div>
  )
}
