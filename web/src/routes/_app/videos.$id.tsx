import { createFileRoute } from '@tanstack/react-router'
import { VideoDetail } from '@/features/library/video-detail'

export const Route = createFileRoute('/_app/videos/$id')({
  component: VideoDetail,
})
