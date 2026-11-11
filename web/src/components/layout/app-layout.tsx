import { Fragment } from 'react'
import { Link, Outlet, useLocation } from '@tanstack/react-router'
import { getCookie } from '@/lib/cookies'
import { useLibrary } from '@/lib/library'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { AppSidebar } from '@/components/layout/app-sidebar'
import { Header } from '@/components/layout/header'
import { SkipToMain } from '@/components/skip-to-main'
import { ThemeSwitch } from '@/components/theme-switch'
import { navGroups } from './data/sidebar-data'

function useCrumbs() {
  const { videos } = useLibrary()
  const path = useLocation({ select: (l) => l.pathname })
  const [, section, id] = path.split('/')
  if (section === 'videos')
    return [
      navGroups[0].items[2],
      { title: videos.find((v) => v.id === id)?.name ?? id },
    ]
  return []
}

export function AppLayout() {
  const crumbs = useCrumbs()
  return (
    <SidebarProvider defaultOpen={getCookie('sidebar_state') !== 'false'}>
      <SkipToMain />
      <AppSidebar />
      <SidebarInset className='@container/content has-data-[layout=fixed]:h-svh peer-data-[variant=inset]:has-data-[layout=fixed]:h-[calc(100svh-(var(--spacing)*4))]'>
        <Header>
          <Breadcrumb>
            <BreadcrumbList>
              {crumbs.map((crumb, i) => (
                <Fragment key={crumb.title}>
                  {i > 0 && <BreadcrumbSeparator />}
                  <BreadcrumbItem>
                    {i < crumbs.length - 1 && 'url' in crumb ? (
                      <BreadcrumbLink asChild>
                        <Link to={crumb.url}>{crumb.title}</Link>
                      </BreadcrumbLink>
                    ) : (
                      <BreadcrumbPage>{crumb.title}</BreadcrumbPage>
                    )}
                  </BreadcrumbItem>
                </Fragment>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
          <div className='ms-auto'>
            <ThemeSwitch />
          </div>
        </Header>
        <Outlet />
      </SidebarInset>
    </SidebarProvider>
  )
}
