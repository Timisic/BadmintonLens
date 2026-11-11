import { getRouteApi } from '@tanstack/react-router'
import { type Match, clock, useLibrary, useMatch } from '@/lib/library'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Choice } from '@/components/choice'
import { FramePlayer } from '@/components/frame-player'
import { Main } from '@/components/layout/main'

const route = getRouteApi('/_app/compare')

export function Compare() {
  const search = route.useSearch()
  const navigate = route.useNavigate()
  const { videos } = useLibrary()

  // the same rule as compare.ready in the backend, which answers 400 otherwise
  const ready = videos
    .filter((v) => v.role === 'user')
    .flatMap((v) =>
      v.swings.flatMap(({ id, label }) =>
        label.usable &&
        label.backswing !== undefined &&
        label.racket_low !== undefined &&
        label.hit !== undefined
          ? [[id, `${v.name} ${clock(label.hit)}`]]
          : []
      )
    )
  const swing = search.swing ?? ready[0]?.[0]
  const match = useMatch(swing)

  return (
    <Main fluid className='flex flex-col gap-4 pt-2'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <h1 className='text-2xl font-bold tracking-tight'>对比</h1>
        {ready.length > 0 && (
          <div className='w-72'>
            <Choice
              aria-label='选择我的一拍'
              none='选我的一拍'
              value={swing}
              options={Object.fromEntries(ready)}
              onChange={(id) => navigate({ search: { swing: id } })}
            />
          </div>
        )}
      </div>
      {ready.length === 0 && (
        <p className='rounded-lg border border-dashed p-8 text-center text-muted-foreground'>
          还没有可以对比的挥拍。先在审核里把我的一拍标为可用，并标好引拍、最低点和击球点。
        </p>
      )}
      {match.isPending && swing && <Skeleton className='h-[70svh]' />}
      {match.error && (
        <Alert variant='destructive'>
          <AlertDescription>{match.error.message}</AlertDescription>
        </Alert>
      )}
      {match.data && <Aligned key={swing} match={match.data} />}
    </Main>
  )
}

function Aligned({ match }: { match: Match }) {
  return (
    <>
      {match.note && (
        <Alert>
          <AlertDescription>{match.note}</AlertDescription>
        </Alert>
      )}
      {/* nine pictures need room: a narrow screen scrolls sideways */}
      <div className='overflow-x-auto'>
        <div
          className='grid min-w-3xl items-center gap-x-2 gap-y-3'
          style={{
            gridTemplateColumns: `5rem repeat(${match.cols.length * 2 - 1}, minmax(0, 1fr))`,
          }}
        >
          <span />
          {match.cols.flatMap((name, i) => [
            ...(i ? [<span key={`${name}-before`} />] : []),
            <h2
              key={name}
              className='text-center text-sm font-medium whitespace-nowrap'
            >
              {name}
            </h2>,
          ])}
          {match.coach ? (
            <Row side={match.coach} step={match.step} />
          ) : (
            <p className='col-span-full rounded-lg border border-dashed p-8 text-center text-muted-foreground'>
              库里没有同侧机位的教练示范，只显示我的这一拍。
            </p>
          )}
          <Row side={match.user} step={match.step} />
        </div>
      </div>
    </>
  )
}

function Row({
  side: { swing, times, box },
  step,
}: {
  side: Match['user']
  step: number
}) {
  const { vocab } = useLibrary()
  const fromHit = (t: number) => {
    const d = t - swing.label.hit
    const s = Math.abs(d).toFixed(2)
    return `${+s === 0 ? '' : d < 0 ? '−' : '+'}${s}s`
  }
  return (
    <>
      <div className='flex flex-col items-start gap-1 text-sm'>
        <Badge variant={swing.role === 'coach' ? 'default' : 'outline'}>
          {vocab.role[swing.role]}
        </Badge>
        <span className='w-full truncate text-muted-foreground'>
          {swing.name}
        </span>
      </div>
      {times
        .filter((_, i) => i % step === 0)
        // each phase, and the moment halfway to the next one
        .flatMap((t, i, keys) => (i ? [(keys[i - 1] + t) / 2, t] : [t]))
        .map((t) => (
          <FramePlayer
            key={t}
            still
            frame={9 / 16}
            videoId={swing.video_id}
            fps={swing.fps}
            start={t}
            maxHeight='calc(50svh - 7.5rem)'
            box={box}
            format={fromHit}
          />
        ))}
    </>
  )
}
