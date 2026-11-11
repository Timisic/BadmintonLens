import { Columns2, Film, ListChecks } from 'lucide-react'
import { type NavGroup } from '../types'

export const navGroups: NavGroup[] = [
  {
    title: 'BadmintonLens',
    items: [
      { title: '素材库', url: '/', icon: Film },
      { title: '挥拍审核', url: '/review', icon: ListChecks },
      { title: '对比', url: '/compare', icon: Columns2 },
    ],
  },
]
