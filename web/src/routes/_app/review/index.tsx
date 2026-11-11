import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/review/')({
  component: () => (
    <p className='text-muted-foreground'>从左边选一拍开始审核。</p>
  ),
})
