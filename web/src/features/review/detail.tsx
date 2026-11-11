import { useEffect, useRef, useState } from 'react'
import { Link, getRouteApi, notFound } from '@tanstack/react-router'
import { toast } from 'sonner'
import {
  type LabelDraft,
  type Swing,
  clock,
  phases,
  storeUrl,
  useDeleteLabel,
  useLibrary,
  useSaveLabel,
} from '@/lib/library'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Choice } from '@/components/choice'
import { FramePlayer, type FramePlayerHandle } from '@/components/frame-player'
import { SwingBadges } from '@/components/swing-badges'
import { type Entry, useReviewList } from './list'

const route = getRouteApi('/_app/review/$swingId')

export function ReviewDetail() {
  const { swingId } = route.useParams()
  const lib = useLibrary()
  const { all, matches } = useReviewList()
  const player = useRef<FramePlayerHandle>(null)
  const [time, setTime] = useState(0)
  const [cropped, setCropped] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const step = { ArrowLeft: -1, ArrowRight: 1 }[e.key]
      const typing =
        e.target instanceof Element &&
        e.target.closest('input, textarea, [role=combobox], [role=listbox]')
      if (!step || typing) return
      e.preventDefault()
      player.current?.step(step)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const at = all.findIndex((e) => e.swing.id === swingId)
  if (at < 0) throw notFound()
  const { video, swing } = all[at]
  // Neighbours come from library order, not the filtered list: saving a label
  // can drop this swing out of the filter, and "next" must still mean next.
  const before = all.slice(0, at).filter(matches)
  const prev: Entry | undefined = before[before.length - 1]
  const next = all.slice(at + 1).find(matches)

  return (
    <div className='flex flex-col gap-4'>
      <div className='flex flex-wrap items-center gap-3'>
        <h1 className='text-lg font-semibold'>
          {lib.vocab.role[video.role]} · {video.name}
        </h1>
        <span className='font-mono text-sm tabular-nums'>
          {clock(swing.t0)} – {clock(swing.t1)}
        </span>
        <SwingBadges label={swing.label} />
        <span className='ms-auto flex gap-2'>
          <Neighbour entry={prev}>上一拍</Neighbour>
          <Neighbour entry={next}>下一拍</Neighbour>
        </span>
      </div>
      <div className='grid items-start gap-6 xl:grid-cols-[3fr_2fr]'>
        <div className='flex flex-col gap-3'>
          <FramePlayer
            ref={player}
            videoId={video.id}
            fps={video.fps}
            start={swing.t0}
            range={[Math.max(0, swing.t0 - 0.5), swing.t1 + 0.5]}
            box={cropped ? swing.box : null}
            onFrame={setTime}
            className={cropped ? 'h-[60vh]' : 'w-full'}
          />
          <div className='flex items-center gap-3 text-sm text-muted-foreground'>
            {swing.box && (
              <Button
                variant='outline'
                size='sm'
                onClick={() => setCropped(!cropped)}
              >
                {cropped ? '看整个画面' : '只看球员'}
              </Button>
            )}
            键盘 ← → 前后一帧
          </div>
          {swing.sheet && (
            <img
              src={storeUrl(swing.sheet)}
              alt='这一拍的连续帧缩略图'
              className='w-full rounded-md border'
            />
          )}
        </div>
        <LabelForm
          // a save or a revert changes the effective label under the form
          key={`${swing.id} ${swing.label.source}`}
          swing={swing}
          time={time}
          seek={(t) => player.current?.seek(t)}
        />
      </div>
    </div>
  )
}

function Neighbour({
  entry,
  children,
}: {
  entry: Entry | undefined
  children: string
}) {
  if (!entry)
    return (
      <Button variant='outline' size='sm' disabled>
        {children}
      </Button>
    )
  return (
    <Button variant='outline' size='sm' asChild>
      <Link to='/review/$swingId' params={{ swingId: entry.swing.id }} search>
        {children}
      </Link>
    </Button>
  )
}

const YES_NO = { true: '是', false: '否' }
const FLAGS = [
  ['usable', '可用'],
  ['face_visible', '看得到脸'],
] as const
const ENUMS = [
  ['camera', '机位'],
  ['racket_side', '持拍侧'],
  ['confidence', '把握'],
] as const

function LabelForm({
  swing,
  time,
  seek,
}: {
  swing: Swing
  time: number
  seek: (t: number) => void
}) {
  const lib = useLibrary()
  const save = useSaveLabel()
  const revert = useDeleteLabel()
  const [draft, setDraft] = useState<LabelDraft>(() => {
    const { source: _, ...rest } = swing.label
    return rest
  })
  const set = (patch: LabelDraft) => setDraft({ ...draft, ...patch })
  const error = save.error ?? revert.error

  return (
    <form
      className='grid grid-cols-2 gap-4'
      onSubmit={(e) => {
        e.preventDefault()
        revert.reset()
        save.mutate(
          { id: swing.id, label: draft },
          { onSuccess: () => toast.success('已保存为人工标签') }
        )
      }}
    >
      {FLAGS.map(([key, title]) => (
        <Field key={key} id={key} title={title}>
          <Choice
            id={key}
            none='未标'
            options={YES_NO}
            value={draft[key]?.toString()}
            onChange={(v) =>
              set({ [key]: v === undefined ? undefined : v === 'true' })
            }
          />
        </Field>
      ))}
      {ENUMS.map(([key, title]) => (
        <Field key={key} id={key} title={title}>
          <Choice
            id={key}
            none='未标'
            options={lib.vocab[key]}
            value={draft[key]}
            onChange={(v) => set({ [key]: v })}
          />
        </Field>
      ))}
      {phases(lib).map((key) => (
        <Field
          key={key}
          id={key}
          title={`${lib.vocab.phase[key]}（秒）`}
          className='col-span-2'
        >
          <div className='flex gap-2'>
            <Input
              id={key}
              type='number'
              step='any'
              value={draft[key] ?? ''}
              onChange={(e) =>
                set({
                  [key]: e.target.value ? e.target.valueAsNumber : undefined,
                })
              }
            />
            <Button
              type='button'
              variant='outline'
              onClick={() => set({ [key]: Math.round(time * 1000) / 1000 })}
            >
              取当前帧
            </Button>
            <Button
              type='button'
              variant='outline'
              disabled={draft[key] === undefined}
              onClick={() => seek(draft[key]!)}
            >
              跳到
            </Button>
          </div>
        </Field>
      ))}
      <Field id='note' title='备注' className='col-span-2'>
        <Textarea
          id='note'
          value={draft.note ?? ''}
          onChange={(e) => set({ note: e.target.value || undefined })}
        />
      </Field>
      {error && (
        <Alert variant='destructive' className='col-span-2'>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}
      <div className='col-span-2 flex gap-2'>
        <Button type='submit' disabled={save.isPending}>
          保存
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
            撤销人工标签
          </Button>
        )}
      </div>
      <p className='col-span-2 text-sm text-muted-foreground'>
        保存写入人工层，不动下面的层。清空一个阶段时间只对人工层生效，下层标过的值仍会显示出来。
      </p>
    </form>
  )
}

function Field({
  id,
  title,
  className,
  children,
}: {
  id: string
  title: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <div className={`grid gap-1.5 ${className ?? ''}`}>
      <Label htmlFor={id}>{title}</Label>
      {children}
    </div>
  )
}
