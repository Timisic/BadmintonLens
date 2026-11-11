import { Fragment } from 'react'
import { Link, Outlet, getRouteApi, useNavigate } from '@tanstack/react-router'
import { UserCheck } from 'lucide-react'
import { clock, useLibrary } from '@/lib/library'
import { cn } from '@/lib/utils'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Choice } from '@/components/choice'
import { Main } from '@/components/layout/main'
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

  return (
    <Main fixed fluid className='gap-6 pt-2 lg:flex-row'>
      <aside className='flex max-h-[32svh] min-h-0 shrink-0 flex-col gap-3 lg:max-h-none lg:w-60'>
        <Choice
          aria-label='按视频筛选'
          none='全部视频'
          value={search.video}
          options={Object.fromEntries(lib.videos.map((v) => [v.id, v.name]))}
          onChange={(video) => filter({ video })}
        />
        <ToggleGroup
          type='single'
          variant='outline'
          size='sm'
          className='w-full'
          aria-label='筛选挥拍'
          value={search.show ?? 'all'}
          onValueChange={(v) =>
            filter({ show: v === 'usable' || v === 'todo' ? v : undefined })
          }
        >
          <ToggleGroupItem value='all' className='flex-1'>
            全部
          </ToggleGroupItem>
          <ToggleGroupItem value='usable' className='flex-1'>
            可用
          </ToggleGroupItem>
          <ToggleGroupItem value='todo' className='flex-1'>
            未审
          </ToggleGroupItem>
        </ToggleGroup>
        <nav className='flex min-h-0 flex-col overflow-y-auto rounded-lg border'>
          {shown.map(({ video, swing }, i) => (
            <Fragment key={swing.id}>
              {video !== shown[i - 1]?.video && (
                <h2 className='sticky top-0 shrink-0 truncate border-b bg-muted px-3 py-1.5 text-sm font-medium'>
                  {video.name}
                </h2>
              )}
              <Link
                to='/review/$swingId'
                params={{ swingId: swing.id }}
                search
                className={cn(
                  'flex h-9 shrink-0 items-center justify-between border-b px-3 text-sm last:border-b-0 hover:bg-accent',
                  !swing.label.usable && 'text-muted-foreground'
                )}
                activeProps={{ className: 'bg-accent' }}
              >
                <span className='font-mono tabular-nums'>
                  {clock(swing.t0)}
                </span>
                {swing.label.source === 'human' ? (
                  <UserCheck className='size-4' aria-label='已审' />
                ) : (
                  swing.label.usable && (
                    <span
                      className='size-2 rounded-full bg-primary'
                      aria-label='可用'
                    />
                  )
                )}
              </Link>
            </Fragment>
          ))}
          {shown.length === 0 && (
            <p className='p-3 text-sm text-muted-foreground'>
              没有符合条件的挥拍。
            </p>
          )}
        </nav>
      </aside>
      <div className='min-h-0 min-w-0 flex-1 overflow-y-auto'>
        <Outlet />
      </div>
    </Main>
  )
}
