import { z } from 'zod'
import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
  useSuspenseQuery,
} from '@tanstack/react-query'

// Every time is seconds of the source video. Enum values are English; their
// display names, and the order of the phases, come from `vocab`.
const names = z.record(z.string(), z.string())
const phase = z.enum(['backswing', 'racket_low', 'hit', 'follow'])

const Label = z
  .object({
    usable: z.boolean(),
    face_visible: z.boolean(),
    camera: z.string(),
    racket_side: z.string(),
    confidence: z.string(),
    backswing: z.number(),
    racket_low: z.number(),
    hit: z.number(),
    follow: z.number(),
    note: z.string(),
    source: z.enum(['model', 'pose', 'claude', 'human']),
  })
  .partial()

const Box = z.tuple([z.number(), z.number(), z.number(), z.number()])

const Swing = z.object({
  id: z.string(),
  t0: z.number(),
  t1: z.number(),
  box: Box.nullable(),
  sheet: z.string().nullable(),
  label: Label,
})

const Segment = z.object({
  id: z.string(),
  t0: z.number(),
  t1: z.number(),
  kind: z.string(),
  text: z.string().nullable(),
  clip: z.string().nullable(),
})

const Video = z.object({
  id: z.string(),
  role: z.enum(['coach', 'user']),
  name: z.string(),
  fps: z.number(),
  duration: z.number(),
  segments: z.array(Segment),
  swings: z.array(Swing),
})

const Library = z
  .object({
    vocab: z.object({
      kind: names,
      camera: names,
      racket_side: names,
      confidence: names,
      role: names,
      phase: names,
      source: names,
    }),
    videos: z.array(Video),
  })
  .transform((lib) => ({
    ...lib,
    // the label fields that hold phase times, in the backend's order
    phases: z.array(phase).parse(Object.keys(lib.vocab.phase)),
  }))

const Comparable = z.object({
  id: z.string(),
  role: Video.shape.role,
  name: z.string(),
  video_id: z.string(),
  fps: z.number(),
  hit: z.number(),
  camera: z.string().nullable(),
  box: Box.nullable(),
})

const Compare = z.object({
  /** Seconds from the hit of each still, the same for both rows. */
  offsets: z.array(z.number()),
  /** Seconds from the hit that synced playback loops over. */
  span: z.tuple([z.number(), z.number()]),
  /** For each of my swings, the coach demos filmed from the same side, best first. */
  pairs: z.record(z.string(), z.array(z.string())),
  swings: z.array(Comparable),
})

export type Label = z.infer<typeof Label>
export type Box = z.infer<typeof Box>
export type Swing = z.infer<typeof Swing>
export type Segment = z.infer<typeof Segment>
export type Video = z.infer<typeof Video>
export type Library = z.infer<typeof Library>
export type Comparable = z.infer<typeof Comparable>
export type Compare = z.infer<typeof Compare>
export type LabelDraft = Omit<Label, 'source'>

async function api(path: string, init?: RequestInit) {
  const res = await fetch(path, init).catch(() => {
    throw new Error('连不上本机的 API')
  })
  const body = await res.json().catch(() => null)
  if (!res.ok)
    throw new Error(
      typeof body?.detail === 'string'
        ? body.detail
        : `${res.status} ${res.statusText}`
    )
  return body
}

export const libraryQuery = queryOptions({
  queryKey: ['library'],
  queryFn: async () => Library.parse(await api('/api/library')),
})

export const useLibrary = () => useSuspenseQuery(libraryQuery).data

export const useCompare = () =>
  useQuery({
    // under the library key, so a label change refetches it too
    queryKey: ['library', 'compare'],
    queryFn: async () => Compare.parse(await api('/api/compare')),
  })

function useLabelMutation<T>(request: (arg: T) => Promise<unknown>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: request,
    onSuccess: () => client.invalidateQueries({ queryKey: ['library'] }),
  })
}

export const useSaveLabel = () =>
  useLabelMutation(({ id, label }: { id: string; label: LabelDraft }) =>
    api(`/api/swings/${id}/label`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(label),
    })
  )

export const useDeleteLabel = () =>
  useLabelMutation((id: string) =>
    api(`/api/swings/${id}/label`, { method: 'DELETE' })
  )

export const storeUrl = (key: string) =>
  '/store/' + key.split('/').map(encodeURIComponent).join('/')

export const sourceUrl = (videoId: string) => `/api/videos/${videoId}/source`

export function clock(t: number) {
  const m = Math.floor(t / 60)
  return `${m}:${(t - m * 60).toFixed(2).padStart(5, '0')}`
}
