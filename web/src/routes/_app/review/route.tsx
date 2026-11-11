import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { ReviewLayout } from '@/features/review'

export const Route = createFileRoute('/_app/review')({
  validateSearch: z.object({
    video: z.string().optional(),
    show: z.enum(['usable', 'todo']).optional(),
  }),
  component: ReviewLayout,
})
