import { useEffect, useImperativeHandle, useRef, useState } from 'react'
import { Pause, Play, StepBack, StepForward } from 'lucide-react'
import { type Box, clock, sourceUrl } from '@/lib/library'
import { cn } from '@/lib/utils'
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

  const seek = (t: number) => {
    video.current!.pause()
    video.current!.currentTime = t
  }
  const step = (frames: number) =>
    seek(video.current!.currentTime + frames / fps)
  const toggle = () =>
    video.current!.paused ? video.current!.play() : video.current!.pause()
  useImperativeHandle(ref, () => ({ seek, step, toggle }))

  // Covers a new start in the same video. A new video is positioned once its
  // metadata loads, below.
  useEffect(() => {
    video.current!.currentTime = start
  }, [start])

  // Phone video is variable frame rate, so currentTime is only where we asked
  // to be. mediaTime is the timestamp of the frame actually on screen.
  useEffect(() => {
    const v = video.current!
    let id = v.requestVideoFrameCallback(function tick(_now, frame) {
      setTime(frame.mediaTime)
      onFrame?.(frame.mediaTime)
      id = v.requestVideoFrameCallback(tick)
    })
    return () => v.cancelVideoFrameCallback(id)
  }, [onFrame])

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
            v.currentTime = start
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        />
        {still && (
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
          <span className='min-w-16 font-mono text-sm tabular-nums'>
            {format(time)}
          </span>
        </div>
      )}
    </div>
  )
}
