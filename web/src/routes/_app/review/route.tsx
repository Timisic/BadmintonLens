import { z } from 'zod'
import { Outlet, createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/review')({
  validateSearch: z.object({
    who: z.enum(['coach']).optional(),
    deleted: z.boolean().optional(),
  }),
  component: Outlet,
})
