import { useRef, useState } from 'react'
import { getRouteApi } from '@tanstack/react-router'
import { type Match, clock, useLibrary, useMatch } from '@/lib/library'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Choice } from '@/components/choice'
import { FramePlayer, type FramePlayerHandle } from '@/components/frame-player'
import { Main } from '@/components/layout/main'

const route = getRouteApi('/_app/compare')

export function Compare() {
  const { swing } = route.useSearch()
  const navigate = route.useNavigate()
  const { videos } = useLibrary()
  const match = useMatch(swing)

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

  return (
    <Main fluid className='flex flex-col gap-4'>
      <div className='flex flex-wrap items-center gap-3'>
        <h1 className='text-2xl font-bold tracking-tight'>对比</h1>
        <div className='w-80'>
          <Choice
            aria-label='选择我的一拍'
            none='选我的一拍'
            value={swing}
            options={Object.fromEntries(ready)}
            onChange={(id) => navigate({ search: { swing: id } })}
          />
        </div>
      </div>
      {ready.length === 0 && (
        <p className='text-muted-foreground'>
          还没有可以对比的挥拍。先在挥拍审核里把你的一拍标为可用，并标好阶段时间。
        </p>
      )}
      {match.isPending && swing && (
        <p className='text-muted-foreground'>正在找匹配的教练示范…</p>
      )}
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
  const [at, setAt] = useState(0)
  const coach = useRef<FramePlayerHandle>(null)
  const user = useRef<FramePlayerHandle>(null)
  const last = match.user.times.length - 1

  const go = (i: number) => {
    setAt(i)
    coach.current?.seek(match.coach?.times[i] ?? 0)
    user.current?.seek(match.user.times[i])
  }

  return (
    <>
      {match.note && (
        <Alert>
          <AlertDescription>{match.note}</AlertDescription>
        </Alert>
      )}
      <div className='flex flex-wrap items-center gap-2'>
        <Button
          variant='outline'
          size='sm'
          disabled={at === 0}
          onClick={() => go(at - 1)}
        >
          上一格
        </Button>
        {match.cols.map((name, k) => (
          <Button
            key={name}
            size='sm'
            variant={at === k * match.step ? 'default' : 'outline'}
            onClick={() => go(k * match.step)}
          >
            {name}
          </Button>
        ))}
        <Button
          variant='outline'
          size='sm'
          disabled={at === last}
          onClick={() => go(at + 1)}
        >
          下一格
        </Button>
        <span className='text-sm text-muted-foreground tabular-nums'>
          第 {at + 1} / {last + 1} 格，两行各自跳到自己对齐的时间
        </span>
      </div>
      {match.coach ? (
        <Row ref={coach} side={match.coach} />
      ) : (
        <div className='rounded-md border border-dashed p-8 text-center text-muted-foreground'>
          没有可以放在上面的教练示范。下面只显示你的这一拍。
        </div>
      )}
      <Row ref={user} side={match.user} />
    </>
  )
}

function Row({
  ref,
  side: { swing, times },
}: {
  ref: React.Ref<FramePlayerHandle>
  side: Match['user']
}) {
  const { vocab } = useLibrary()
  const [time, setTime] = useState(times[0])
  const offset = time - swing.label.hit

  return (
    <section className='flex flex-col gap-2'>
      <h2 className='flex items-baseline gap-3 font-semibold'>
        {vocab.role[swing.role]} · {swing.name}
        <span className='font-mono text-sm font-normal tabular-nums'>
          距击球 {offset < 0 ? '-' : '+'}
          {Math.abs(offset).toFixed(2)}s
        </span>
      </h2>
      <FramePlayer
        ref={ref}
        videoId={swing.video_id}
        fps={swing.fps}
        start={times[0]}
        box={swing.box}
        onFrame={setTime}
        className='h-[34vh]'
      />
    </section>
  )
}
