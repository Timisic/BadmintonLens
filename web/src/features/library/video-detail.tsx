import { Link, getRouteApi, notFound } from '@tanstack/react-router'
import { clock, storeUrl, useLibrary } from '@/lib/library'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Main } from '@/components/layout/main'
import { SwingBadges } from '@/components/swing-badges'

const route = getRouteApi('/_app/videos/$id')

export function VideoDetail() {
  const { id } = route.useParams()
  const { vocab, videos } = useLibrary()
  const video = videos.find((v) => v.id === id)
  if (!video) throw notFound()
  const swings = video.swings.filter((s) => s.label.usable)

  return (
    <Main fluid className='flex flex-col gap-4 pt-2'>
      <h1 className='flex items-center gap-2 text-2xl font-bold tracking-tight'>
        {video.name}
        <Badge variant={video.role === 'coach' ? 'default' : 'outline'}>
          {vocab.role[video.role]}
        </Badge>
      </h1>

      <Tabs defaultValue='swings'>
        <TabsList>
          <TabsTrigger value='swings'>挥拍 {swings.length}</TabsTrigger>
          <TabsTrigger value='segments'>
            片段 {video.segments.length}
          </TabsTrigger>
        </TabsList>

        <TabsContent value='swings'>
          <div className='grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-4'>
            {swings.map((swing) => (
              <Link
                key={swing.id}
                to='/review/$swingId'
                params={{ swingId: swing.id }}
                className='group flex flex-col gap-2 rounded-lg outline-offset-4'
              >
                {swing.sheet && (
                  <img
                    src={storeUrl(swing.sheet)}
                    alt=''
                    loading='lazy'
                    className='aspect-video w-full rounded-lg border object-cover object-top transition-opacity group-hover:opacity-80'
                  />
                )}
                <span className='flex h-6 items-center justify-between gap-2 text-sm'>
                  <span className='font-mono tabular-nums'>
                    {clock(swing.t0)}
                  </span>
                  <SwingBadges label={swing.label} />
                </span>
              </Link>
            ))}
          </div>
          {swings.length === 0 && (
            <p className='py-8 text-center text-muted-foreground'>
              这个视频里没有找到挥拍。
            </p>
          )}
        </TabsContent>

        <TabsContent value='segments'>
          <ul className='flex flex-col divide-y rounded-lg border'>
            {video.segments.map((segment) => (
              <li key={segment.id} className='flex gap-4 p-3'>
                {segment.clip && (
                  <video
                    src={storeUrl(segment.clip)}
                    controls
                    preload='none'
                    className='aspect-video w-56 shrink-0 rounded-md bg-black'
                  />
                )}
                <div className='flex flex-col items-start gap-1.5 text-sm'>
                  <span className='flex items-center gap-2'>
                    <Badge variant='secondary'>
                      {vocab.kind[segment.kind] ?? segment.kind}
                    </Badge>
                    <span className='font-mono text-muted-foreground tabular-nums'>
                      {clock(segment.t0)} – {clock(segment.t1)}
                    </span>
                  </span>
                  <p className='max-w-[70ch] leading-relaxed'>{segment.text}</p>
                </div>
              </li>
            ))}
          </ul>
          {video.segments.length === 0 && (
            <p className='py-8 text-center text-muted-foreground'>
              这个视频没有分段。
            </p>
          )}
        </TabsContent>
      </Tabs>
    </Main>
  )
}
