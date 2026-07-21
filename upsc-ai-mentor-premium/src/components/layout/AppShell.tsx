import * as Dialog from '@radix-ui/react-dialog'
import { Menu, PanelLeftClose, PanelLeftOpen, Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { navigation, productIcon as ProductIcon } from '../../app/navigation'
import { ConnectionStatus } from '../feedback/ConnectionStatus'

function Sidebar({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  return <div className="sidebar-inner"><div className="brand"><span className="brand-mark"><ProductIcon /></span>{!collapsed && <span><strong>UPSC AI Mentor</strong><small>Focused preparation</small></span>}</div><nav aria-label="Primary navigation">{navigation.map(([label, to, Icon]) => <NavLink key={to} to={to} end onClick={onNavigate} title={collapsed ? label : undefined}><Icon /><span>{label}</span></NavLink>)}</nav>{!collapsed && <div className="sidebar-foot"><small>LOCAL-FIRST MENTOR</small><p>Your study data stays within your setup.</p></div>}</div>
}
export function AppShell() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar-collapsed') === 'true')
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const title = navigation.find(([, path]) => path === location.pathname)?.[0] ?? 'UPSC AI Mentor'
  useEffect(() => localStorage.setItem('sidebar-collapsed', String(collapsed)), [collapsed])
  return <div className={`app-shell ${collapsed ? 'is-collapsed' : ''}`}>
    <aside className="desktop-sidebar"><Sidebar collapsed={collapsed} /></aside>
    <div className="app-column"><header className="top-header"><div className="header-leading">
      <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}><Dialog.Trigger asChild><button className="icon-button mobile-menu" aria-label="Open navigation"><Menu /></button></Dialog.Trigger><Dialog.Portal><Dialog.Overlay className="drawer-overlay" /><Dialog.Content className="mobile-drawer" aria-describedby={undefined}><Dialog.Title className="sr-only">Navigation</Dialog.Title><Dialog.Close className="icon-button drawer-close" aria-label="Close navigation"><X /></Dialog.Close><Sidebar onNavigate={() => setMobileOpen(false)} /></Dialog.Content></Dialog.Portal></Dialog.Root>
      <button className="icon-button collapse-button" onClick={() => setCollapsed(v => !v)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>{collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}</button><div><span className="eyebrow">UPSC PREPARATION</span><h1>{title}</h1></div></div><div className="header-actions"><button className="search-button" disabled title="Search arrives with feature pages"><Search /> <span>Search your workspace</span><kbd>⌘ K</kbd></button><ConnectionStatus /></div></header>
      <main id="main-content"><Outlet /></main>
    </div>
  </div>
}
