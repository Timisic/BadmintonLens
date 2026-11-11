import { type Label } from '@/lib/library'
import { Badge } from '@/components/ui/badge'

export function SwingBadges({ label }: { label: Label }) {
  return (
    <span className='flex gap-1'>
      {label.usable !== undefined && (
        <Badge variant={label.usable ? 'default' : 'secondary'}>
          {label.usable ? '可用' : '不可用'}
        </Badge>
      )}
      <Badge variant='outline'>{label.source ?? '未标'}</Badge>
    </span>
  )
}
