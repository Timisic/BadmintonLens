import { UserCheck } from 'lucide-react'
import { type Label, useLibrary } from '@/lib/library'
import { Badge } from '@/components/ui/badge'

export function SwingBadges({ label }: { label: Label }) {
  const { vocab } = useLibrary()
  return (
    <span className='flex items-center gap-1.5'>
      {label.source === 'human' && (
        <UserCheck
          className='size-4 text-muted-foreground'
          aria-label={vocab.source.human}
        />
      )}
      {label.usable && <Badge>可用</Badge>}
    </span>
  )
}
