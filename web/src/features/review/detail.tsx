import { useEffect, useRef, useState } from 'react'
import { Link, getRouteApi, notFound } from '@tanstack/react-router'
import {
  ChevronDown,
  ChevronUp,
  Columns2,
  Crosshair,
  Undo2,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  type LabelDraft,
  clock,
  storeUrl,
  useDeleteLabel,
  useLibrary,
  useSaveLabel,
} from '@/lib/library'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Kbd } from '@/components/ui/kbd'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { FramePlayer, type FramePlayerHandle } from '@/components/frame-player'
import { IconButton } from '@/components/icon-button'
import { SwingBadges } from '@/components/swing-badges'
import { type Entry, useReviewList } from './list'

const route = getRouteApi('/_app/review/$swingId')

export function ReviewDetail() {
  const { swingId } = route.useParams()
  const { all, matches } = useReviewList()
  const at = all.findIndex((e) => e.swing.id === swingId)
  if (at < 0) throw notFound()
  // Neighbours come from library order, not the filtered list: saving a label
  // can drop this swing out of the filter, and "next" must still mean next.
  const before = all.slice(0, at).filter(matches)
  return (
    <Workspace
      key={swingId}
      entry={all[at]}
      prev={before[before.length - 1]}
      next={all.slice(at + 1).find(matches)}
    />
  )
}

function Workspace({
  entry: { video, swing },
  prev,
  next,
}: {
  entry: Entry
  prev?: Entry
  next?: Entry
}) {
  const lib = useLibrary()
  const navigate = route.useNavigate()
  const save = useSaveLabel()
  const revert = useDeleteLabel()
  const player = useRef<FramePlayerHandle>(null)
  const [time, setTime] = useState(swing.t0)
  const effective = (): LabelDraft => {
    const { source: _, ...rest } = swing.label
    return rest
  }
  const [draft, setDraft] = useState(effective)
  // A save or a revert changes the label under the form. Follow it without
  // remounting, so the player keeps its frame.
  const [source, setSource] = useState(swing.label.source)
  if (source !== swing.label.source) {
    setSource(swing.label.source)
    setDraft(effective())
  }
  const set = (patch: LabelDraft) => setDraft({ ...draft, ...patch })
  const capture = (key: (typeof lib.phases)[number]) =>
    set({ [key]: Math.round(time * 1000) / 1000 })
  const go = (to?: Entry) =>
    to &&
    navigate({
      to: '/review/$swingId',
      params: { swingId: to.swing.id },
      search: true,
    })
  const submit = () => {
    revert.reset()
    save.mutate(
      { id: swing.id, label: draft },
      { onSuccess: () => toast.success('已保存为人工标签') }
    )
  }
  const error = save.error ?? revert.error
  const comparable = video.role === 'user' && swing.label.usable

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        return submit()
      }
      const typing =
        e.target instanceof Element &&
        e.target.closest('input, textarea, [role=combobox], [role=listbox]')
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return
      const phase = lib.phases[Number(e.key) - 1]
      const action = {
        ArrowLeft: () => player.current?.step(-1),
        ArrowRight: () => player.current?.step(1),
        ArrowUp: () => go(prev),
        ArrowDown: () => go(next),
        ' ': () => player.current?.toggle(),
      }[e.key]
      if (!phase && !action) return
      e.preventDefault()
      if (phase) capture(phase)
      else action!()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  return (
    <div className='grid items-start gap-6 xl:grid-cols-[1fr_20rem]'>
      <section className='flex min-w-0 flex-col gap-3'>
        <div className='flex min-h-9 flex-wrap items-center gap-x-3 gap-y-2'>
          <h1 className='truncate text-lg font-semibold'>{video.name}</h1>
          <span className='font-mono text-sm text-muted-foreground tabular-nums'>
            {clock(swing.t0)}
          </span>
          <SwingBadges label={swing.label} />
          <span className='ms-auto flex gap-1.5'>
            {comparable && (
              <Button variant='outline' size='sm' asChild>
                <Link to='/compare' search={{ swing: swing.id }}>
                  <Columns2 /> 对比
                </Link>
              </Button>
            )}
            <IconButton
              label='上一拍 ↑'
              className='size-8'
              disabled={!prev}
              onClick={() => go(prev)}
            >
              <ChevronUp />
            </IconButton>
            <IconButton
              label='下一拍 ↓'
              className='size-8'
              disabled={!next}
              onClick={() => go(next)}
            >
              <ChevronDown />
            </IconButton>
          </span>
        </div>
        <Tabs defaultValue='video'>
          <TabsList>
            <TabsTrigger value='video'>视频</TabsTrigger>
            <TabsTrigger value='player'>只看球员</TabsTrigger>
            {swing.sheet && <TabsTrigger value='sheet'>连拍图</TabsTrigger>}
          </TabsList>
          {(['video', 'player'] as const).map((view) => (
            <TabsContent
              key={view}
              value={view}
              className='flex flex-col items-center gap-2'
            >
              <FramePlayer
                ref={player}
                videoId={video.id}
                fps={video.fps}
                start={swing.t0}
                maxHeight='calc(100svh - 19rem)'
                box={view === 'player' ? swing.box : null}
                range={[Math.max(0, swing.t0 - 0.5), swing.t1 + 0.5]}
                marks={lib.phases.flatMap((key) =>
                  draft[key] === undefined
                    ? []
                    : [{ t: draft[key], name: lib.vocab.phase[key] }]
                )}
                onFrame={setTime}
              />
            </TabsContent>
          ))}
          {swing.sheet && (
            <TabsContent value='sheet'>
              <img
                src={storeUrl(swing.sheet)}
                alt='这一拍的连续帧缩略图'
                className='max-h-[calc(100svh-12rem)] rounded-lg border'
              />
            </TabsContent>
          )}
        </Tabs>
      </section>

      <form
        className='flex flex-col gap-4'
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <div className='flex min-h-9 items-center'>
          <Pick
            title='这一拍可用'
            options={YES_NO}
            value={draft.usable === undefined ? undefined : `${draft.usable}`}
            onChange={(v) => set({ usable: v && v === 'true' })}
          />
        </div>

        <ul className='divide-y rounded-lg border'>
          {lib.phases.map((key, i) => (
            <li key={key} className='flex h-11 items-center gap-3 ps-3 pe-1.5'>
              <Kbd>{i + 1}</Kbd>
              <span className='flex-1 text-sm'>{lib.vocab.phase[key]}</span>
              <Button
                type='button'
                variant='ghost'
                size='sm'
                className='font-mono tabular-nums'
                disabled={draft[key] === undefined}
                aria-label={`跳到${lib.vocab.phase[key]}`}
                onClick={() => player.current?.seek(draft[key]!)}
              >
                {draft[key] === undefined ? '未标' : clock(draft[key])}
              </Button>
              <IconButton
                type='button'
                label='设为当前帧'
                variant='ghost'
                className='size-8'
                onClick={() => capture(key)}
              >
                <Crosshair />
              </IconButton>
            </li>
          ))}
        </ul>

        <Collapsible className='rounded-lg border'>
          <CollapsibleTrigger className='group flex h-11 w-full items-center justify-between gap-3 px-3 text-sm'>
            <span className='truncate'>
              {[
                draft.camera && lib.vocab.camera[draft.camera],
                draft.racket_side && lib.vocab.racket_side[draft.racket_side],
                draft.face_visible !== undefined &&
                  (draft.face_visible ? '看得到脸' : '看不到脸'),
              ]
                .filter(Boolean)
                .join('，') || '机位未标'}
            </span>
            <ChevronDown className='size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180' />
          </CollapsibleTrigger>
          <CollapsibleContent className='flex flex-col gap-3 border-t p-3'>
            <Pick
              title='机位'
              options={lib.vocab.camera}
              value={draft.camera}
              onChange={(camera) => set({ camera })}
            />
            <Pick
              title='持拍侧'
              options={lib.vocab.racket_side}
              value={draft.racket_side}
              onChange={(racket_side) => set({ racket_side })}
            />
            <Pick
              title='看得到脸'
              options={YES_NO}
              value={
                draft.face_visible === undefined
                  ? undefined
                  : `${draft.face_visible}`
              }
              onChange={(v) => set({ face_visible: v && v === 'true' })}
            />
            <Textarea
              aria-label='备注'
              placeholder='备注'
              rows={2}
              value={draft.note ?? ''}
              onChange={(e) => set({ note: e.target.value || undefined })}
            />
          </CollapsibleContent>
        </Collapsible>

        {error && (
          <Alert variant='destructive'>
            <AlertDescription>{error.message}</AlertDescription>
          </Alert>
        )}
        <div className='flex gap-2'>
          <Button type='submit' className='flex-1' disabled={save.isPending}>
            保存 <Kbd className='bg-primary-foreground/20 text-inherit'>⌘S</Kbd>
          </Button>
          {swing.label.source === 'human' && (
            <Button
              type='button'
              variant='outline'
              disabled={revert.isPending}
              onClick={() => {
                save.reset()
                revert.mutate(swing.id, {
                  onSuccess: () => toast.success('已撤销人工标签'),
                })
              }}
            >
              <Undo2 /> 撤销
            </Button>
          )}
        </div>
      </form>
    </div>
  )
}

const YES_NO = { true: '是', false: '否' }

function Pick<K extends string>({
  title,
  options,
  value,
  onChange,
}: {
  title: string
  options: Record<K, string>
  value: K | undefined
  onChange: (value: K | undefined) => void
}) {
  return (
    <div className='flex w-full flex-wrap items-center justify-between gap-x-3 gap-y-2'>
      <Label asChild className='shrink-0'>
        <span>{title}</span>
      </Label>
      <ToggleGroup
        type='single'
        variant='outline'
        size='sm'
        aria-label={title}
        value={value ?? ''}
        onValueChange={(v) => onChange((v || undefined) as K | undefined)}
      >
        {Object.entries<string>(options).map(([key, name]) => (
          <ToggleGroupItem
            key={key}
            value={key}
            className='data-[state=on]:bg-primary data-[state=on]:text-primary-foreground'
          >
            {name}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}
