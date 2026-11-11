import { createFileRoute } from '@tanstack/react-router'
import { libraryQuery } from '@/lib/library'
import { AppLayout } from '@/components/layout/app-layout'

export const Route = createFileRoute('/_app')({
  loader: ({ context }) => context.queryClient.ensureQueryData(libraryQuery),
  component: AppLayout,
})
