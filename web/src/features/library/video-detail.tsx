import { Link, getRouteApi, notFound } from '@tanstack/react-router'
import { clock, storeUrl, useLibrary } from '@/lib/library'
import { Badge } from '@/components/ui/badge'
import { Main } from '@/components/layout/main'
import { SwingBadges } from '@/components/swing-badges'

const route = getRouteApi('/_app/videos/$id')

export function VideoDetail() {
  const { id } = route.useParams()
  const { vocab, videos } = useLibrary()
  const video = videos.find((v) => v.id === id)
  if (!video) throw notFound()

  return (
    <Main className='flex flex-col gap-6'>
      <div>
        <h1 className='text-2xl font-bold tracking-tight'>{video.name}</h1>
        <p className='text-muted-foreground'>
          {vocab.role[video.role]} · {clock(video.duration)} ·{' '}
          {+video.fps.toFixed(2)} 帧/秒
        </p>
      </div>

      <section className='flex flex-col gap-3'>
        <h2 className='text-lg font-semibold'>挥拍（{video.swings.length}）</h2>
        <div className='grid grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-3'>
          {video.swings.map((swing) => (
            <Link
              key={swing.id}
              to='/review/$swingId'
              params={{ swingId: swing.id }}
              className='flex flex-col gap-2 rounded-md border p-2 hover:bg-accent'
            >
              {swing.sheet && (
                <img
                  src={storeUrl(swing.sheet)}
                  alt=''
                  loading='lazy'
                  className='aspect-video w-full rounded object-cover object-top'
                />
              )}
              <span className='flex items-center justify-between gap-2 text-sm'>
                <span className='font-mono tabular-nums'>
                  {clock(swing.t0)}
                </span>
                <SwingBadges label={swing.label} />
              </span>
            </Link>
          ))}
        </div>
        {video.swings.length === 0 && (
          <p className='text-muted-foreground'>这个视频里没有找到挥拍。</p>
        )}
      </section>

      <section className='flex flex-col gap-3'>
        <h2 className='text-lg font-semibold'>
          片段（{video.segments.length}）
        </h2>
        <ul className='flex flex-col divide-y rounded-md border'>
          {video.segments.map((segment) => (
            <li key={segment.id} className='flex gap-4 p-3'>
              {segment.clip && (
                <video
                  src={storeUrl(segment.clip)}
                  controls
                  preload='none'
                  className='aspect-video w-64 shrink-0 rounded bg-black'
                />
              )}
              <div className='flex flex-col items-start gap-1 text-sm'>
                <Badge variant='secondary'>
                  {vocab.kind[segment.kind] ?? segment.kind}
                </Badge>
                <span className='font-mono tabular-nums'>
                  {clock(segment.t0)} – {clock(segment.t1)}
                </span>
                <p className='text-muted-foreground'>{segment.text}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </Main>
  )
}
