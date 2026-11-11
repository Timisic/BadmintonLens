import { z } from 'zod'
import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
  useSuspenseQuery,
} from '@tanstack/react-query'

// Every time is seconds of the source video. Enum values are English; their
// display names come from `vocab`.
const names = z.record(z.string(), z.string())

const Label = z
  .object({
    /** A real swing worth comparing. False is how a swing is deleted. */
    usable: z.boolean(),
    camera: z.string(),
    hit: z.number(),
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

const Library = z.object({
  vocab: z.object({ kind: names, camera: names, role: names, source: names }),
  videos: z.array(Video),
})

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
  /** For each of my swings, the coach demos filmed from the same place, best first. */
  pairs: z.record(z.string(), z.array(z.string())),
  swings: z.array(Comparable),
})

const Shown = z.object({
  /** Height difference between two joints, in torso lengths. */
  value: z.number(),
  /** Seconds from the hit of the moment that shows it. */
  at: z.number(),
  /** The joint to look at, as fractions of the picture. */
  spot: z.tuple([z.number(), z.number()]),
})

const Lesson = z.object({
  video_id: z.string(),
  name: z.string(),
  t0: z.number(),
  t1: z.number(),
  text: z.string(),
})

const Check = z.object({
  key: z.string(),
  name: z.string(),
  fault: z.string(),
  /** The coach is ahead by more than two good swings differ: a finding. */
  short: z.boolean(),
  me: Shown,
  coach: Shown,
  /** In how many of the swings from the same video the same thing shows. */
  habit: z.tuple([z.number(), z.number()]),
  lessons: z.array(Lesson),
})

/** Widest gap first. Null when either swing has no pose data. */
const Diagnosis = z.object({ checks: z.array(Check).nullable() })

export type Label = z.infer<typeof Label>
export type Box = z.infer<typeof Box>
export type Swing = z.infer<typeof Swing>
export type Segment = z.infer<typeof Segment>
export type Video = z.infer<typeof Video>
export type Library = z.infer<typeof Library>
export type Comparable = z.infer<typeof Comparable>
export type Compare = z.infer<typeof Compare>
export type Check = z.infer<typeof Check>
export type Lesson = z.infer<typeof Lesson>
/** What a person says about a swing. A field left out keeps its value, null takes it back. */
export type LabelPatch = { usable?: boolean; camera?: string; hit?: number }

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
  useLabelMutation(({ id, label }: { id: string; label: LabelPatch }) =>
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

export const useDiagnosis = (me?: string, coach?: string) =>
  useQuery({
    queryKey: ['library', 'diagnose', me, coach],
    enabled: !!me && !!coach,
    queryFn: async () =>
      Diagnosis.parse(await api(`/api/diagnose?me=${me}&coach=${coach}`)),
  })

/** The swing at its hit, cropped to the player. `hit` only keeps a moved hit from showing the old picture. */
export const thumbUrl = (swingId: string, hit?: number) =>
  `/api/swings/${swingId}/thumb?v=${hit ?? ''}`

export const storeUrl = (key: string) =>
  '/store/' + key.split('/').map(encodeURIComponent).join('/')

export const sourceUrl = (videoId: string) => `/api/videos/${videoId}/source`

/** The coach talking, from t0 to t1. The picture-only copy has no sound. */
export const lessonUrl = ({ video_id, t0, t1 }: Lesson) =>
  `/api/videos/${video_id}/source?sound=1#t=${t0},${t1}`

export function clock(t: number) {
  const m = Math.floor(t / 60)
  return `${m}:${(t - m * 60).toFixed(2).padStart(5, '0')}`
}
