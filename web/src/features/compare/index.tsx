import { useRef, useState } from 'react'
import { Link, getRouteApi } from '@tanstack/react-router'
import { Pause, Play, StepBack, StepForward } from 'lucide-react'
import {
  type Check,
  type Comparable,
  clock,
  lessonUrl,
  thumbUrl,
  useCompare,
  useDiagnosis,
  useLibrary,
} from '@/lib/library'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { FramePlayer, type FramePlayerHandle } from '@/components/frame-player'
import { IconButton } from '@/components/icon-button'
import { Main } from '@/components/layout/main'

const route = getRouteApi('/_app/compare')

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
  // Either side can lead. A coach demo named alone brings one of my swings
  // filmed from the same place. Nothing named starts with one that has a partner.
  const me =
    mine.find((s) => s.id === search.swing) ??
    mine.find((s) => pairs[s.id]?.includes(search.coach ?? '')) ??
    mine.find((s) => pairs[s.id]?.length) ??
    mine[0]
  // the coach demos filmed from where I was filmed, best first
  const partners = (pairs[me?.id ?? ''] ?? []).flatMap(
    (id) => coaches.find((s) => s.id === id) ?? []
  )
  const coach = partners.find((s) => s.id === search.coach) ?? partners[0]
  const cameras = [...new Set(mine.flatMap((s) => s.camera ?? []))]

  return (
    <Main fluid className='flex flex-col gap-5 pt-2'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <h1 className='text-2xl font-bold tracking-tight'>对比</h1>
        {cameras.length > 1 && (
          <ToggleGroup
            type='single'
            variant='outline'
            size='sm'
            aria-label='机位'
            value={me?.camera ?? ''}
            onValueChange={(v) =>
              v &&
              navigate({
                search: { swing: mine.find((s) => s.camera === v)?.id },
              })
            }
          >
            {cameras.map((c) => (
              <ToggleGroupItem key={c} value={c}>
                {vocab.camera[c] ?? c}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
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
          还没有可以对比的挥拍。去
          <Link to='/review' className='underline underline-offset-4'>
            挥拍
          </Link>
          看看有没有被删掉的。
        </p>
      )}
      {data && me && (
        <>
          <div className='flex flex-col gap-1'>
            <Strip
              title='我'
              swings={mine.filter((s) => s.camera === me.camera)}
              value={me.id}
              onPick={(swing) =>
                navigate({ search: { swing, coach: coach?.id } })
              }
            />
            {coach ? (
              <Strip
                title='教练'
                swings={partners}
                value={coach.id}
                onPick={(id) =>
                  navigate({ search: { swing: me.id, coach: id } })
                }
              />
            ) : (
              <p className='rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground'>
                库里没有从{vocab.camera[me.camera ?? ''] ?? '这个机位'}
                拍的教练示范，只能看我自己的这一拍。
              </p>
            )}
          </div>
          <Tabs defaultValue='stills' key={`${coach?.id} ${me.id}`}>
            <TabsList>
              <TabsTrigger value='stills'>逐帧</TabsTrigger>
              {coach && <TabsTrigger value='slow'>同步慢放</TabsTrigger>}
            </TabsList>
            <TabsContent value='stills'>
              <Stills offsets={data.offsets} coach={coach} me={me} />
            </TabsContent>
            {coach && (
              <TabsContent value='slow'>
                <Slow span={data.span} coach={coach} me={me} />
              </TabsContent>
            )}
          </Tabs>
          {coach && <Diagnosis coach={coach} me={me} />}
        </>
      )}
    </Main>
  )
}

/** One side's swings as small pictures. The picture is the name. */
function Strip({
  title,
  swings,
  value,
  onPick,
}: {
  title: string
  swings: Comparable[]
  value: string
  onPick: (id: string) => void
}) {
  return (
    <div className='flex items-center gap-3'>
      <h2 className='w-8 shrink-0 text-sm font-medium'>{title}</h2>
      <div
        role='radiogroup'
        aria-label={`选${title}的一拍`}
        className='flex gap-4 overflow-x-auto p-1.5'
      >
        {[...new Set(swings.map((s) => s.name))].map((name) => (
          <div key={name} className='flex shrink-0 flex-col gap-1.5'>
            <span className='sticky left-0 w-fit text-xs text-muted-foreground'>
              {name}
            </span>
            <div className='flex gap-2'>
              {swings
                .filter((s) => s.name === name)
                .map((s) => (
                  <button
                    key={s.id}
                    type='button'
                    role='radio'
                    aria-checked={s.id === value}
                    aria-label={`${s.name} ${clock(s.hit)}`}
                    title={`${s.name} ${clock(s.hit)}`}
                    ref={(el) => {
                      if (s.id === value)
                        el?.scrollIntoView({
                          block: 'nearest',
                          inline: 'nearest',
                        })
                    }}
                    onClick={() => onPick(s.id)}
                    className={cn(
                      'w-9 shrink-0 overflow-hidden rounded-md bg-muted ring-offset-2 ring-offset-background transition-opacity',
                      s.id === value
                        ? 'ring-2 ring-primary'
                        : 'opacity-50 hover:opacity-100'
                    )}
                  >
                    <img
                      src={thumbUrl(s.id, s.hit)}
                      alt=''
                      loading='lazy'
                      className='aspect-[1/2] w-full object-cover'
                    />
                  </button>
                ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const side = (swing: Comparable) => (swing.role === 'coach' ? '教练' : '我')

/** Both swings at the same moments before and after the hit. */
function Stills({
  offsets,
  coach,
  me,
}: {
  offsets: number[]
  coach?: Comparable
  me: Comparable
}) {
  return (
    // seven pictures need room: a narrow screen scrolls sideways
    <div className='overflow-x-auto'>
      <div
        className='grid min-w-2xl items-center justify-items-center gap-x-2 gap-y-2'
        style={{
          gridTemplateColumns: `2rem repeat(${offsets.length}, minmax(0, 1fr))`,
        }}
      >
        <span />
        {offsets.map((d) => (
          <span
            key={d}
            className={cn(
              'font-mono text-xs tabular-nums',
              d === 0
                ? 'font-sans font-medium text-foreground'
                : 'text-muted-foreground'
            )}
          >
            {d === 0 ? '击球' : fromHit(d)}
          </span>
        ))}
        {[coach, me].map(
          (swing) =>
            swing && (
              <div key={swing.id} className='contents'>
                <h3 className='justify-self-start text-sm font-medium'>
                  {side(swing)}
                </h3>
                {offsets.map((d) => (
                  <FramePlayer
                    key={d}
                    still
                    frame={9 / 16}
                    videoId={swing.video_id}
                    fps={swing.fps}
                    start={swing.hit + d}
                    maxHeight='17rem'
                    box={swing.box}
                  />
                ))}
              </div>
            )
        )}
      </div>
    </div>
  )
}

/** What the coach does that I do not, each with the coach explaining it. */
function Diagnosis({ coach, me }: { coach: Comparable; me: Comparable }) {
  const { data, error, isPending } = useDiagnosis(me.id, coach.id)
  const found = data?.checks?.filter((c) => c.short) ?? []
  const close = data?.checks?.filter((c) => !c.short) ?? []
  return (
    <section className='flex flex-col gap-4 border-t pt-5'>
      <h2 className='text-xl font-semibold tracking-tight'>差在哪</h2>
      {isPending && <Skeleton className='h-48' />}
      {error && (
        <Alert variant='destructive'>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}
      {data && !data.checks && (
        <p className='text-muted-foreground'>
          这两拍里有一拍的姿态读不准，没法量。换一拍试试。
        </p>
      )}
      {data?.checks && found.length === 0 && (
        <p className='text-muted-foreground'>
          量过的几项都和教练接近，这一拍没有找到明显的差别。
        </p>
      )}
      {found.map((check) => (
        <Finding key={check.key} check={check} coach={coach} me={me} />
      ))}
      {close.length > 0 && (
        <p className='text-sm text-muted-foreground'>
          和教练接近的：{close.map((c) => c.name).join('、')}。
        </p>
      )}
    </section>
  )
}

function Finding({
  check,
  coach,
  me,
}: {
  check: Check
  coach: Comparable
  me: Comparable
}) {
  const [often, total] = check.habit
  const most = Math.max(check.coach.value, check.me.value, 0.01)
  return (
    <article className='grid gap-6 rounded-lg border p-4 md:grid-cols-[auto_1fr]'>
      <div className='flex justify-center gap-3'>
        {([coach, me] as const).map((swing) => {
          const shown = check[swing.role === 'coach' ? 'coach' : 'me']
          return (
            <figure key={swing.id} className='flex w-36 flex-col gap-1.5'>
              <FramePlayer
                still
                frame={9 / 16}
                videoId={swing.video_id}
                fps={swing.fps}
                start={swing.hit + shown.at}
                maxHeight='16rem'
                box={swing.box}
                spot={shown.spot}
              />
              <figcaption className='flex items-center gap-2 text-sm'>
                <span className='w-8 shrink-0 font-medium'>{side(swing)}</span>
                <span className='h-1.5 flex-1 rounded-full bg-muted'>
                  <span
                    className={cn(
                      'block h-full rounded-full',
                      swing === coach ? 'bg-primary' : 'bg-yellow-500'
                    )}
                    style={{
                      width: `${(Math.max(shown.value, 0) / most) * 100}%`,
                    }}
                  />
                </span>
              </figcaption>
            </figure>
          )
        })}
      </div>
      <div className='flex min-w-0 flex-col gap-4'>
        <div className='flex flex-col gap-1'>
          <h3 className='text-lg font-semibold'>{check.fault}</h3>
          <p className='text-sm text-muted-foreground'>
            看圈出来的位置。{check.name}的幅度，我是教练的{' '}
            {Math.round((Math.max(check.me.value, 0) / most) * 100)}%。
            {total > 1 && `同一个视频的 ${total} 拍里，${often} 拍是这样。`}
          </p>
        </div>
        {check.lessons.length > 0 && (
          <div className='flex flex-col gap-3'>
            <h4 className='text-sm font-medium'>教练怎么讲</h4>
            <ul className='flex flex-col gap-4'>
              {check.lessons.map((lesson) => (
                <li
                  key={`${lesson.video_id} ${lesson.t0}`}
                  className='flex flex-col gap-3 sm:flex-row'
                >
                  <video
                    src={lessonUrl(lesson)}
                    controls
                    playsInline
                    preload='metadata'
                    className='aspect-video w-full shrink-0 rounded-md bg-black sm:w-56'
                  />
                  <div className='flex flex-col gap-1'>
                    <span className='text-xs text-muted-foreground'>
                      {lesson.name} · {clock(lesson.t0).replace(/\.\d+$/, '')}
                    </span>
                    <p className='max-w-[60ch] text-sm leading-relaxed'>
                      {lesson.text}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
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
            <h3 className='text-sm font-medium'>
              {swing === coach ? '教练' : '我'}
            </h3>
            <div className='flex justify-center'>
              <FramePlayer
                ref={swing === coach ? a : b}
                still
                frame={9 / 16}
                videoId={swing.video_id}
                fps={swing.fps}
                start={swing.hit + from}
                maxHeight='26rem'
                box={swing.box}
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
