import { Link, getRouteApi } from '@tanstack/react-router'
import { Trash2, Undo2 } from 'lucide-react'
import { toast } from 'sonner'
import { clock, thumbUrl, useLibrary, useSaveLabel } from '@/lib/library'
import { Toggle } from '@/components/ui/toggle'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { IconButton } from '@/components/icon-button'
import { Main } from '@/components/layout/main'

const route = getRouteApi('/_app/review')

/** Every swing as a picture. The only decision here is keep or delete. */
export function Swings() {
  const { vocab, videos } = useLibrary()
  const { who, deleted } = route.useSearch()
  const navigate = route.useNavigate()
  const save = useSaveLabel()

  const ofRole = videos.filter((v) => v.role === (who ?? 'user'))
  const gone = ofRole.flatMap((v) => v.swings).filter((s) => !s.label.usable)
  const groups = ofRole
    .map((video) => ({
      video,
      swings: video.swings.filter((s) => !s.label.usable === !!deleted),
    }))
    .filter((g) => g.swings.length > 0)

  const keep = (id: string, usable: boolean, undo = true) =>
    save.mutate(
      { id, label: { usable } },
      {
        onError: (e) => toast.error(e.message),
        onSuccess: () =>
          undo &&
          toast(usable ? '已恢复' : '已删除', {
            action: { label: '撤销', onClick: () => keep(id, !usable, false) },
          }),
      }
    )

  return (
    <Main fluid className='flex flex-col gap-6 pt-2'>
      <div className='flex flex-wrap items-center justify-between gap-3'>
        <h1 className='text-2xl font-bold tracking-tight'>挥拍</h1>
        <div className='flex items-center gap-2'>
          <Toggle
            variant='outline'
            size='sm'
            pressed={!!deleted}
            onPressedChange={(on) =>
              navigate({ search: { who, deleted: on || undefined } })
            }
          >
            <Trash2 /> 已删除 {gone.length}
          </Toggle>
          <ToggleGroup
            type='single'
            variant='outline'
            size='sm'
            aria-label='谁的挥拍'
            value={who ?? 'user'}
            onValueChange={(v) =>
              v &&
              navigate({
                search: { deleted, who: v === 'coach' ? v : undefined },
              })
            }
          >
            <ToggleGroupItem value='user'>{vocab.role.user}</ToggleGroupItem>
            <ToggleGroupItem value='coach'>{vocab.role.coach}</ToggleGroupItem>
          </ToggleGroup>
        </div>
      </div>

      {groups.map(({ video, swings }) => {
        const cameras = [
          ...new Set(swings.flatMap((s) => s.label.camera ?? [])),
        ]
        return (
          <section key={video.id} className='flex flex-col gap-3'>
            <h2 className='flex items-baseline gap-2 font-medium'>
              {video.name}
              <span className='text-sm font-normal text-muted-foreground'>
                {[
                  cameras.length === 1 && vocab.camera[cameras[0]],
                  `${swings.length} 拍`,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </span>
            </h2>
            <ul className='grid grid-cols-[repeat(auto-fill,minmax(6rem,1fr))] gap-3'>
              {swings.map((swing) => (
                <li key={swing.id} className='relative flex flex-col gap-1'>
                  <Link
                    to='/review/$swingId'
                    params={{ swingId: swing.id }}
                    search
                    aria-label={`${video.name} ${clock(swing.t0)}`}
                    className='overflow-hidden rounded-lg border bg-muted transition-opacity hover:opacity-80'
                  >
                    <img
                      src={thumbUrl(swing.id, swing.label.hit)}
                      alt=''
                      loading='lazy'
                      className='aspect-[1/2] w-full object-cover'
                    />
                  </Link>
                  <span className='flex justify-between text-xs text-muted-foreground'>
                    <span className='font-mono tabular-nums'>
                      {clock(swing.label.hit ?? swing.t0)}
                    </span>
                    {cameras.length > 1 &&
                      swing.label.camera &&
                      vocab.camera[swing.label.camera]}
                  </span>
                  <IconButton
                    label={deleted ? '恢复' : '删除'}
                    variant='secondary'
                    className='absolute top-1.5 right-1.5 size-7'
                    onClick={() => keep(swing.id, !!deleted)}
                  >
                    {deleted ? <Undo2 /> : <Trash2 />}
                  </IconButton>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
      {groups.length === 0 && (
        <p className='rounded-lg border border-dashed p-8 text-center text-muted-foreground'>
          {deleted
            ? '没有删除过的挥拍。'
            : '这里还没有挥拍。先用 clean.py 清洗一个视频。'}
        </p>
      )}
    </Main>
  )
}
