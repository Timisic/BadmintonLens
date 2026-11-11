import { createFileRoute } from '@tanstack/react-router'
import { ReviewDetail } from '@/features/review/detail'

export const Route = createFileRoute('/_app/review/$swingId')({
  component: ReviewDetail,
})
