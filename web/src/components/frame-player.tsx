import { useEffect, useImperativeHandle, useRef, useState } from 'react'
import { type Box, clock, sourceUrl } from '@/lib/library'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

export type FramePlayerHandle = {
  seek: (t: number) => void
  step: (frames: number) => void
}

type FramePlayerProps = {
  ref?: React.Ref<FramePlayerHandle>
  videoId: string
  fps: number
  start: number
  box?: Box | null
  range?: [number, number]
  onFrame?: (t: number) => void
  className?: string
}

export function FramePlayer({
  ref,
  videoId,
  fps,
  start,
  box,
  range,
  onFrame,
  className,
}: FramePlayerProps) {
  const video = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(start)
  const [aspect, setAspect] = useState(16 / 9)
  const [playing, setPlaying] = useState(false)
  const [x0, y0, x1, y1] = box ?? [0, 0, 1, 1]

  const seek = (t: number) => {
    video.current!.pause()
    video.current!.currentTime = t
  }
  const step = (frames: number) =>
    seek(video.current!.currentTime + frames / fps)
  useImperativeHandle(ref, () => ({ seek, step }))

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

  return (
    <div className='flex flex-col gap-2'>
      <div
        className={cn(
          'self-start overflow-hidden rounded-md bg-black',
          className
        )}
        style={{ aspectRatio: (aspect * (x1 - x0)) / (y1 - y0) }}
      >
        <video
          ref={video}
          src={sourceUrl(videoId)}
          muted
          playsInline
          className='block max-w-none'
          style={{
            width: `${100 / (x1 - x0)}%`,
            transform: `translate(${-x0 * 100}%, ${-y0 * 100}%)`,
          }}
          onLoadedMetadata={({ currentTarget: v }) => {
            setAspect(v.videoWidth / v.videoHeight)
            v.currentTime = start
          }}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        />
      </div>
      {range && (
        <input
          type='range'
          aria-label='在这一拍里拖动'
          min={range[0]}
          max={range[1]}
          step={1 / fps}
          value={time}
          onChange={(e) => seek(e.target.valueAsNumber)}
        />
      )}
      <div className='flex items-center gap-2'>
        <Button variant='outline' size='sm' onClick={() => step(-1)}>
          −1 帧
        </Button>
        <Button
          variant='outline'
          size='sm'
          onClick={() =>
            playing ? video.current!.pause() : video.current!.play()
          }
        >
          {playing ? '暂停' : '播放'}
        </Button>
        <Button variant='outline' size='sm' onClick={() => step(1)}>
          +1 帧
        </Button>
        <span className='font-mono text-sm tabular-nums'>{clock(time)}</span>
      </div>
    </div>
  )
}
