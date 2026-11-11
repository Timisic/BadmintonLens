import { Outlet } from '@tanstack/react-router'
import { getCookie } from '@/lib/cookies'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { AppSidebar } from '@/components/layout/app-sidebar'
import { Header } from '@/components/layout/header'
import { SkipToMain } from '@/components/skip-to-main'
import { ThemeSwitch } from '@/components/theme-switch'

export function AppLayout() {
  return (
    <SidebarProvider defaultOpen={getCookie('sidebar_state') !== 'false'}>
      <SkipToMain />
      <AppSidebar />
      <SidebarInset className='@container/content'>
        <Header>
          <div className='ms-auto'>
            <ThemeSwitch />
          </div>
        </Header>
        <Outlet />
      </SidebarInset>
    </SidebarProvider>
  )
}
