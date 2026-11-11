import { useEffect, useRef } from 'react'
import { Link, getRouteApi, notFound } from '@tanstack/react-router'
import { ChevronLeft, Columns2, Crosshair, Trash2, Undo2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  type LabelPatch,
  clock,
  useDeleteLabel,
  useLibrary,
  useSaveLabel,
} from '@/lib/library'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { FramePlayer, type FramePlayerHandle } from '@/components/frame-player'
import { Main } from '@/components/layout/main'

const route = getRouteApi('/_app/review/$swingId')

/** One swing, to fix what was read wrong: the camera or the hit. Each change saves at once. */
export function ReviewDetail() {
  const { swingId } = route.useParams()
  const { vocab, videos } = useLibrary()
  const navigate = route.useNavigate()
  const save = useSaveLabel()
  const revert = useDeleteLabel()
  const player = useRef<FramePlayerHandle>(null)

  const video = videos.find((v) => v.swings.some((s) => s.id === swingId))
  const swing = video?.swings.find((s) => s.id === swingId)
  if (!video || !swing) throw notFound()
  const { usable, camera, hit, source } = swing.label

  const onError = (e: Error) => toast.error(e.message)
  const set = (label: LabelPatch, done?: () => void) =>
    save.mutate({ id: swing.id, label }, { onError, onSuccess: done })

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const action = {
        ArrowLeft: () => player.current?.step(-1),
        ArrowRight: () => player.current?.step(1),
        ' ': () => player.current?.toggle(),
      }[e.key]
      // a focused button keeps its own space and arrows
      if (!action || e.target instanceof HTMLButtonElement) return
      e.preventDefault()
      action()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <Main fluid className='flex flex-col gap-4 pt-2'>
      <div className='flex flex-wrap items-center gap-x-3 gap-y-2'>
        <Button variant='ghost' size='sm' className='-ms-2' asChild>
          <Link to='/review' search>
            <ChevronLeft /> 挥拍
          </Link>
        </Button>
        <h1 className='truncate text-lg font-semibold'>{video.name}</h1>
        <span className='font-mono text-sm text-muted-foreground tabular-nums'>
          {clock(hit ?? swing.t0)}
        </span>
      </div>
      <div className='grid items-start gap-6 lg:grid-cols-[1fr_18rem]'>
        <Tabs defaultValue='player'>
          <TabsList>
            <TabsTrigger value='player'>只看球员</TabsTrigger>
            <TabsTrigger value='video'>整个画面</TabsTrigger>
          </TabsList>
          {(['player', 'video'] as const).map((view) => (
            <TabsContent
              key={view}
              value={view}
              className='flex flex-col items-center gap-2'
            >
              <FramePlayer
                ref={player}
                videoId={video.id}
                fps={video.fps}
                start={hit ?? swing.t0}
                maxHeight='calc(100svh - 18rem)'
                box={view === 'player' ? swing.box : null}
                range={[Math.max(0, swing.t0 - 0.5), swing.t1 + 0.5]}
                marks={hit === undefined ? [] : [{ t: hit, name: '击球点' }]}
              />
            </TabsContent>
          ))}
        </Tabs>

        <div className='flex flex-col gap-5'>
          <div className='flex flex-col gap-2'>
            <h2 className='text-sm font-medium'>机位</h2>
            <ToggleGroup
              type='single'
              variant='outline'
              size='sm'
              className='w-full'
              aria-label='机位'
              value={camera ?? ''}
              onValueChange={(v) => v && set({ camera: v })}
            >
              {Object.entries(vocab.camera).map(([key, name]) => (
                <ToggleGroupItem
                  key={key}
                  value={key}
                  className='flex-1 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground'
                >
                  {name}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>

          <div className='flex flex-col gap-2'>
            <h2 className='text-sm font-medium'>击球点</h2>
            <div className='flex gap-2'>
              <Button
                variant='outline'
                size='sm'
                className='flex-1 font-mono tabular-nums'
                disabled={hit === undefined}
                aria-label='跳到击球点'
                onClick={() => player.current?.seek(hit!)}
              >
                {hit === undefined ? '未标' : clock(hit)}
              </Button>
              <Button
                variant='outline'
                size='sm'
                className='flex-1'
                onClick={async () => {
                  const t = await player.current!.shown()
                  set({ hit: Math.round(t * 1000) / 1000 }, () =>
                    toast.success('击球点已改到当前帧')
                  )
                }}
              >
                <Crosshair /> 设为当前帧
              </Button>
            </div>
            <p className='text-xs text-muted-foreground'>
              ← → 逐帧，空格播放。对比按击球点对齐。
            </p>
          </div>

          <div className='flex flex-col gap-2 border-t pt-5'>
            {usable && hit !== undefined && (
              <Button asChild>
                <Link
                  to='/compare'
                  search={
                    video.role === 'user'
                      ? { swing: swing.id }
                      : { coach: swing.id }
                  }
                >
                  <Columns2 /> 对比
                </Link>
              </Button>
            )}
            {usable ? (
              <Button
                variant='outline'
                onClick={() =>
                  set({ usable: false }, () => {
                    toast('已删除')
                    navigate({ to: '/review', search: true })
                  })
                }
              >
                <Trash2 /> 删除
              </Button>
            ) : (
              <Button variant='outline' onClick={() => set({ usable: true })}>
                <Undo2 /> 恢复
              </Button>
            )}
            {source === 'human' && (
              <Button
                variant='ghost'
                onClick={() =>
                  revert.mutate(swing.id, {
                    onError,
                    onSuccess: () => toast.success('已回到自动识别的结果'),
                  })
                }
              >
                回到自动识别
              </Button>
            )}
          </div>
        </div>
      </div>
    </Main>
  )
}
