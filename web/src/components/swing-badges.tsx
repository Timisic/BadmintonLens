import { type Label, useLibrary } from '@/lib/library'
import { Badge } from '@/components/ui/badge'

export function SwingBadges({ label }: { label: Label }) {
  const { vocab } = useLibrary()
  return label.usable ? (
    <Badge variant='outline'>
      {(label.camera && vocab.camera[label.camera]) ?? '可用'}
    </Badge>
  ) : (
    <Badge variant='secondary'>已删除</Badge>
  )
}
