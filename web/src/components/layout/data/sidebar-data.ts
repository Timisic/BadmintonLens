import { Columns2, Library, ScanEye } from 'lucide-react'
import { type NavGroup } from '../types'

export const navGroups: NavGroup[] = [
  {
    title: '工作台',
    items: [
      { title: '对比', url: '/compare', icon: Columns2 },
      { title: '挥拍', url: '/review', icon: ScanEye },
      { title: '素材库', url: '/', icon: Library },
    ],
  },
]
