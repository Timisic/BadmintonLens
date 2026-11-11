import { useRef, useState } from 'react'
import { getRouteApi } from '@tanstack/react-router'
import { Pause, Play, StepBack, StepForward } from 'lucide-react'
import {
  type Comparable,
  type Compare as Comparison,
  clock,
  useCompare,
  useLibrary,
} from '@/lib/library'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Choice } from '@/components/choice'
import { FramePlayer, type FramePlayerHandle } from '@/components/frame-player'
import { IconButton } from '@/components/icon-button'
import { Main } from '@/components/layout/main'

const route = getRouteApi('/_app/compare')

// rank of a swing that is no partner at all
const FAR = 1e9

const fromHit = (d: number) => {
  const s = Math.abs(d).toFixed(2)
  return `${+s === 0 ? '' : d < 0 ? '−' : '+'}${s}s`
}

export function Compare() {
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const { vocab } = useLibrary()
  const { data, error, isPending } = useCompare()

  const mine = data?.swings.filter((s) => s.role === 'user') ?? []
  const coaches = data?.swings.filter((s) => s.role === 'coach') ?? []
  const pairs = data?.pairs ?? {}
  const fits = (me?: string, coach?: string) =>
    !!me && !!coach && pairs[me]?.includes(coach)

  // Either side can lead. The one named in the URL without a partner gets
  // the best partner filmed from its side.
  // my swing for a coach demo: one it is the best match for, else any from its side
  const partner = (coach?: string) =>
    mine.find((s) => !!coach && pairs[s.id]?.[0] === coach) ??
    mine.find((s) => fits(s.id, coach))
  const coachAsked = coaches.find((s) => s.id === search.coach)
  const me =
    mine.find((s) => s.id === search.swing) ??
    partner(coachAsked?.id) ??
    mine[0]
  const coach =
    coachAsked ?? coaches.find((s) => s.id === pairs[me?.id ?? '']?.[0])

  const name = (s: Comparable) =>
    [s.camera && vocab.camera[s.camera], s.name, clock(s.hit)]
      .filter(Boolean)
      .join(' · ')
  // partners filmed from the same side first, best first; the others say so
  const options = (list: Comparable[], rank: (s: Comparable) => number) =>
    Object.fromEntries(
      [...list]
        .sort((a, b) => rank(a) - rank(b))
        .map((s) => [s.id, rank(s) < FAR ? name(s) : `${name(s)}（不同侧）`])
    )
  const order = (i: number) => (i < 0 ? FAR : i)
  const choose = (swing?: string, other?: string) =>
    navigate({ search: { swing, coach: other } })

  return (
    <Main fluid className='flex flex-col gap-4 pt-2'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <h1 className='text-2xl font-bold tracking-tight'>对比</h1>
        {mine.length > 0 && (
          <div className='flex flex-wrap items-center gap-2'>
            <div className='w-72'>
              <Choice
                aria-label='选教练的一拍'
                none='自动选教练'
                value={coach?.id}
                options={options(coaches, (s) =>
                  order((pairs[me?.id ?? ''] ?? []).indexOf(s.id))
                )}
                onChange={(id) =>
                  choose(
                    // the coach leads: my swing follows to the one it suits best
                    !id || pairs[me?.id ?? '']?.[0] === id
                      ? me?.id
                      : (partner(id)?.id ?? me?.id),
                    id
                  )
                }
              />
            </div>
            <div className='w-72'>
              <Choice
                aria-label='选我的一拍'
                none='选我的一拍'
                value={me?.id}
                options={options(mine, (s) =>
                  coach ? order((pairs[s.id] ?? []).indexOf(coach.id)) : 0
                )}
                // my swing leads: the coach follows to its best match
                onChange={(id) => choose(id)}
              />
            </div>
          </div>
        )}
      </div>
      {isPending && <Skeleton className='h-[70svh]' />}
      {error && (
        <Alert variant='destructive'>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}
      {data && !me && (
        <p className='rounded-lg border border-dashed p-8 text-center text-muted-foreground'>
          还没有可以对比的挥拍。先在审核里把我的一拍标为可用，并标好击球点。
        </p>
      )}
      {data && me && coach && !fits(me.id, coach.id) && (
        <Alert>
          <AlertDescription>
            这两拍不是从同一侧拍的，姿态不能直接对照。
          </AlertDescription>
        </Alert>
      )}
      {data &&
        me &&
        coach &&
        fits(me.id, coach.id) &&
        coach.camera !== me.camera && (
          <Alert>
            <AlertDescription>
              机位不完全相同：教练是
              {vocab.camera[coach.camera ?? ''] ?? '未标'}，我是
              {vocab.camera[me.camera ?? ''] ?? '未标'}。
            </AlertDescription>
          </Alert>
        )}
      {data && me && (
        <Tabs defaultValue='stills' key={`${coach?.id} ${me.id}`}>
          <TabsList>
            <TabsTrigger value='stills'>逐帧</TabsTrigger>
            {coach && <TabsTrigger value='slow'>同步慢放</TabsTrigger>}
          </TabsList>
          <TabsContent value='stills'>
            <Stills data={data} coach={coach} me={me} />
          </TabsContent>
          {coach && (
            <TabsContent value='slow'>
              <Slow span={data.span} coach={coach} me={me} />
            </TabsContent>
          )}
        </Tabs>
      )}
    </Main>
  )
}

function Who({ swing }: { swing: Comparable }) {
  const { vocab } = useLibrary()
  return (
    <div className='flex min-w-0 flex-col items-start gap-1 text-sm'>
      <Badge variant={swing.role === 'coach' ? 'default' : 'outline'}>
        {vocab.role[swing.role]}
        {swing.camera && ` · ${vocab.camera[swing.camera]}`}
      </Badge>
      <span className='w-full truncate text-muted-foreground'>
        {swing.name}
      </span>
    </div>
  )
}

/** Both swings at the same moments before and after the hit. */
function Stills({
  data: { offsets },
  coach,
  me,
}: {
  data: Comparison
  coach?: Comparable
  me: Comparable
}) {
  const row = (swing: Comparable) => (
    <>
      <Who swing={swing} />
      {offsets.map((d) => (
        <FramePlayer
          key={d}
          still
          frame={9 / 16}
          videoId={swing.video_id}
          fps={swing.fps}
          start={swing.hit + d}
          maxHeight='calc(50svh - 9rem)'
          box={swing.box}
          format={(t) => fromHit(t - swing.hit)}
        />
      ))}
    </>
  )
  return (
    // nine pictures need room: a narrow screen scrolls sideways
    <div className='overflow-x-auto'>
      <div
        className='grid min-w-3xl items-center gap-x-2 gap-y-3'
        style={{
          gridTemplateColumns: `6rem repeat(${offsets.length}, minmax(0, 1fr))`,
        }}
      >
        <span />
        {offsets.map((d) =>
          d === 0 ? (
            <h2 key={d} className='text-center text-sm font-medium'>
              击球点
            </h2>
          ) : (
            <span key={d} />
          )
        )}
        {coach ? (
          row(coach)
        ) : (
          <p className='col-span-full rounded-lg border border-dashed p-8 text-center text-muted-foreground'>
            库里没有同侧机位的教练示范，只显示我的这一拍。
          </p>
        )}
        {row(me)}
      </div>
    </div>
  )
}

/** Both swings played on one clock, the hit at the same instant. */
function Slow({
  span: [from, to],
  coach,
  me,
}: {
  span: [number, number]
  coach: Comparable
  me: Comparable
}) {
  const a = useRef<FramePlayerHandle>(null)
  const b = useRef<FramePlayerHandle>(null)
  const [at, setAt] = useState(from)
  const [playing, setPlaying] = useState(false)
  const [rate, setRate] = useState(0.25)

  const pause = () => {
    a.current!.pause()
    b.current!.pause()
    setPlaying(false)
  }
  const seek = (d: number) => {
    pause()
    a.current!.seek(coach.hit + d)
    b.current!.seek(me.hit + d)
    setAt(d)
  }
  // both pictures land on the start before either moves
  const play = async (d: number, r = rate) => {
    seek(d)
    await Promise.all([a.current!.shown(), b.current!.shown()])
    a.current!.play(r)
    b.current!.play(r)
    setPlaying(true)
  }

  return (
    <div className='mx-auto flex max-w-3xl flex-col gap-3'>
      <div className='grid grid-cols-2 justify-items-center gap-4'>
        {[coach, me].map((swing) => (
          <div key={swing.id} className='flex w-full flex-col gap-2'>
            <Who swing={swing} />
            <div className='flex justify-center'>
              <FramePlayer
                ref={swing === coach ? a : b}
                still
                frame={9 / 16}
                videoId={swing.video_id}
                fps={swing.fps}
                start={swing.hit + from}
                maxHeight='calc(100svh - 21rem)'
                box={swing.box}
                format={(t) => fromHit(t - swing.hit)}
                onFrame={
                  swing === me
                    ? (t) => {
                        setAt(t - me.hit)
                        if (playing && t - me.hit >= to) play(from)
                      }
                    : undefined
                }
              />
            </div>
          </div>
        ))}
      </div>
      <Slider
        aria-label='拖动两边到同一时刻'
        min={from}
        max={to}
        step={0.01}
        value={[at]}
        onValueChange={([d]) => seek(d)}
      />
      <div className='flex items-center justify-center gap-1.5'>
        <IconButton
          label='两边后退一帧'
          variant='ghost'
          className='size-7'
          onClick={() => seek(Math.max(from, at - 1 / 30))}
        >
          <StepBack />
        </IconButton>
        <IconButton
          label={playing ? '暂停' : '同步播放'}
          variant='ghost'
          className='size-7'
          onClick={() => (playing ? pause() : play(at >= to ? from : at))}
        >
          {playing ? <Pause /> : <Play />}
        </IconButton>
        <IconButton
          label='两边前进一帧'
          variant='ghost'
          className='size-7'
          onClick={() => seek(Math.min(to, at + 1 / 30))}
        >
          <StepForward />
        </IconButton>
        <ToggleGroup
          type='single'
          variant='outline'
          size='sm'
          aria-label='播放速度'
          value={String(rate)}
          onValueChange={(v) => {
            if (!v) return
            setRate(+v)
            if (playing) play(at, +v)
          }}
        >
          {[0.5, 0.25, 0.1].map((r) => (
            <ToggleGroupItem key={r} value={String(r)} className='font-mono'>
              {r}×
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <span className='min-w-16 text-right font-mono text-sm tabular-nums'>
          {fromHit(at)}
        </span>
      </div>
    </div>
  )
}
