import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { Compare } from '@/features/compare'

export const Route = createFileRoute('/_app/compare')({
  validateSearch: z.object({
    swing: z.string().optional(),
    coach: z.string().optional(),
  }),
  component: Compare,
})
