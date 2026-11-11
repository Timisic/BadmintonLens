import { Link, Outlet, getRouteApi, useNavigate } from '@tanstack/react-router'
import { clock, useLibrary } from '@/lib/library'
import { Choice } from '@/components/choice'
import { Main } from '@/components/layout/main'
import { SwingBadges } from '@/components/swing-badges'
import { useReviewList } from './list'

const route = getRouteApi('/_app/review')
type Search = ReturnType<typeof route.useSearch>

export function ReviewLayout() {
  const lib = useLibrary()
  const search = route.useSearch()
  const navigate = useNavigate()
  const { all, matches } = useReviewList()
  const shown = all.filter(matches)
  const filter = (patch: Search) =>
    navigate({ to: '.', search: (prev) => ({ ...prev, ...patch }) })

  const sources: Record<string, string> = { none: '未标' }
  for (const { swing } of all)
    if (swing.label.source) sources[swing.label.source] = swing.label.source

  return (
    <Main fluid className='grid items-start gap-6 lg:grid-cols-[18rem_1fr]'>
      <aside className='flex flex-col gap-2 lg:sticky lg:top-4 lg:max-h-[calc(100svh-6rem)]'>
        <Choice
          aria-label='按视频筛选'
          none='全部视频'
          value={search.video}
          options={Object.fromEntries(lib.videos.map((v) => [v.id, v.name]))}
          onChange={(video) => filter({ video })}
        />
        <Choice
          aria-label='按是否可用筛选'
          none='可用与否都看'
          value={search.usable}
          options={{ yes: '可用', no: '不可用', unset: '没标可用与否' }}
          onChange={(usable) => filter({ usable })}
        />
        <Choice
          aria-label='按标签来源筛选'
          none='全部来源'
          value={search.source}
          options={sources}
          onChange={(source) => filter({ source })}
        />
        <p className='text-sm text-muted-foreground'>
          {shown.length} / {all.length} 拍
        </p>
        <nav className='flex flex-col overflow-y-auto rounded-md border'>
          {shown.map(({ video, swing }) => (
            <Link
              key={swing.id}
              to='/review/$swingId'
              params={{ swingId: swing.id }}
              search
              className='flex flex-col gap-1 border-b px-3 py-2 text-sm last:border-b-0 hover:bg-accent'
              activeProps={{ className: 'bg-accent' }}
            >
              <span className='truncate'>{video.name}</span>
              <span className='flex items-center justify-between gap-2'>
                <span className='font-mono tabular-nums'>
                  {clock(swing.t0)}
                </span>
                <SwingBadges label={swing.label} />
              </span>
            </Link>
          ))}
          {shown.length === 0 && (
            <p className='p-3 text-sm text-muted-foreground'>
              没有符合筛选条件的挥拍。
            </p>
          )}
        </nav>
      </aside>
      <Outlet />
    </Main>
  )
}
