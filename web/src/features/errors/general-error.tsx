import { type ErrorComponentProps, useRouter } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'

export function GeneralError({ error }: ErrorComponentProps) {
  const router = useRouter()
  return (
    <div className='flex h-svh flex-col items-center justify-center gap-2 p-4'>
      <span className='font-medium'>出错了</span>
      <p className='text-center text-muted-foreground'>
        {error.message}
        <br />
        数据来自本机的 API，请确认 <code>python3 proto/api.py</code> 正在运行。
      </p>
      <Button className='mt-4' onClick={() => router.invalidate()}>
        重试
      </Button>
    </div>
  )
}
