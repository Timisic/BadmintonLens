import { Link } from '@tanstack/react-router'
import { Aperture } from 'lucide-react'
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'

export function AppTitle() {
  const { setOpenMobile } = useSidebar()
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size='lg' asChild>
          <Link to='/' onClick={() => setOpenMobile(false)}>
            <span className='flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground'>
              <Aperture className='size-4' />
            </span>
            <span className='grid flex-1 text-start text-sm leading-tight'>
              <span className='truncate font-semibold'>BadmintonLens</span>
              <span className='truncate text-xs text-muted-foreground'>
                杀球对比
              </span>
            </span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
