import { createFileRoute } from '@tanstack/react-router'
import { VideoTable } from '@/features/library'

export const Route = createFileRoute('/_app/')({
  component: VideoTable,
})
