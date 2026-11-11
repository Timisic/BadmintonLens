import { getRouteApi } from '@tanstack/react-router'
import { type Label, type Swing, type Video, useLibrary } from '@/lib/library'

const route = getRouteApi('/_app/review')

export type Entry = { video: Video; swing: Swing }

const usableState = (label: Label) =>
  label.usable === undefined ? 'unset' : label.usable ? 'yes' : 'no'

/** Every swing in library order, and whether one passes the filters in the URL. */
export function useReviewList() {
  const lib = useLibrary()
  const search = route.useSearch()
  const all: Entry[] = lib.videos.flatMap((video) =>
    video.swings.map((swing) => ({ video, swing }))
  )
  const matches = ({ video, swing }: Entry) =>
    (!search.video || video.id === search.video) &&
    (!search.usable || usableState(swing.label) === search.usable) &&
    (!search.source || (swing.label.source ?? 'none') === search.source)
  return { all, matches }
}
