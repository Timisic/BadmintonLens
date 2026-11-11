import { getRouteApi } from '@tanstack/react-router'
import { type Swing, type Video, useLibrary } from '@/lib/library'

const route = getRouteApi('/_app/review')

export type Entry = { video: Video; swing: Swing }

/** Every swing in library order, and whether one passes the filters in the URL. */
export function useReviewList() {
  const lib = useLibrary()
  const search = route.useSearch()
  const all: Entry[] = lib.videos.flatMap((video) =>
    video.swings.map((swing) => ({ video, swing }))
  )
  const matches = ({ video, swing }: Entry) =>
    (!search.video || video.id === search.video) &&
    (search.show !== 'usable' || !!swing.label.usable) &&
    (search.show !== 'todo' || swing.label.source !== 'human')
  return { all, matches }
}
