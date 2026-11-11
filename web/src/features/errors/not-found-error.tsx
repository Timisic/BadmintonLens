import { Link } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'

export function NotFoundError() {
  return (
    <div className='flex h-svh flex-col items-center justify-center gap-2'>
      <h1 className='text-[7rem] leading-tight font-bold'>404</h1>
      <span className='font-medium'>没有这个页面</span>
      <Button className='mt-4' asChild>
        <Link to='/'>回到素材库</Link>
      </Button>
    </div>
  )
}
