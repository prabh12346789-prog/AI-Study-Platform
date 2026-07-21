import { ReactNode, useMemo, useState } from 'react'
import { Bell, BookOpen, BrainCircuit, ChevronRight, Gauge, Library, Menu, Newspaper, RefreshCcw, Search, Settings, Sparkles, UserRound, X } from 'lucide-react'

export type AppPage = 'dashboard' | 'chat' | 'library' | 'current_affairs' | 'upsc_notes' | 'visual' | 'revision' | 'quizzes' | 'progress' | 'profile' | 'settings'

const NAVIGATION: Array<{ page: AppPage; label: string; icon: typeof Gauge }> = [
  { page: 'dashboard', label: 'Dashboard', icon: Gauge },
  { page: 'chat', label: 'AI Study Coach', icon: Sparkles },
  { page: 'library', label: 'My Library', icon: Library },
  { page: 'current_affairs', label: 'Current Affairs', icon: Newspaper },
  { page: 'upsc_notes', label: 'UPSC Notes', icon: BookOpen },
  { page: 'visual', label: 'Visual Learning', icon: BrainCircuit },
  { page: 'revision', label: 'Revision Center', icon: RefreshCcw },
  { page: 'quizzes', label: 'Quizzes', icon: BookOpen },
  { page: 'progress', label: 'Progress', icon: Gauge },
  { page: 'profile', label: 'Profile', icon: UserRound },
  { page: 'settings', label: 'Settings', icon: Settings },
]

export function AppShell({ page, onNavigate, onNewChat, sidebarContent, workspaceRef, onScroll, children }: {
  page: AppPage
  onNavigate: (page: AppPage) => void
  onNewChat: () => void
  sidebarContent: ReactNode
  workspaceRef: React.RefObject<HTMLElement | null>
  onScroll: () => void
  children: ReactNode
}) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [search, setSearch] = useState('')
  const pageLabel = NAVIGATION.find(item => item.page === page)?.label ?? 'UPSC AI Mentor'
  const matches = useMemo(() => search.trim() ? NAVIGATION.filter(item => item.label.toLowerCase().includes(search.trim().toLowerCase())).slice(0, 5) : [], [search])
  function navigate(next: AppPage) { onNavigate(next); setDrawerOpen(false); setSearch('') }
  return <main className="app-shell premium-shell">
    <button className="mobile-menu" aria-label="Open navigation" aria-expanded={drawerOpen} onClick={() => setDrawerOpen(true)}><Menu size={19} /></button>
    {drawerOpen && <button className="drawer-backdrop" aria-label="Close navigation" onClick={() => setDrawerOpen(false)} />}
    <aside className={`sidebar premium-sidebar ${drawerOpen ? 'open' : ''}`}>
      <div className="brand-row"><div className="brand-mark"><BrainCircuit size={21} /></div><div><strong>UPSC AI Mentor</strong><span>Focused exam preparation</span></div><button className="drawer-close" aria-label="Close navigation" onClick={() => setDrawerOpen(false)}><X size={18} /></button></div>
      <button className="new-chat" onClick={() => { onNewChat(); setDrawerOpen(false) }}><Sparkles size={17} /> Ask AI Mentor</button>
      <nav className="app-navigation" aria-label="Main navigation">{NAVIGATION.map(item => { const Icon = item.icon; return <button key={item.page} className={page === item.page ? 'active' : ''} onClick={() => navigate(item.page)}><Icon size={17} /><span>{item.label}</span>{page === item.page && <ChevronRight className="nav-chevron" size={15} />}</button> })}</nav>
      {sidebarContent}
      <div className="sidebar-footer"><span className="status-dot online" /> Local-first mentor online</div>
    </aside>
    <section className={`workspace ${page}`} ref={workspaceRef} onScroll={onScroll}>
      <header className="global-header">
        <div><span className="header-kicker">Workspace</span><strong>{pageLabel}</strong></div>
        <div className="global-search"><Search size={16} /><input aria-label="Search pages" value={search} onChange={event => setSearch(event.target.value)} placeholder="Find a study area…" />{matches.length > 0 && <div className="search-results">{matches.map(item => <button key={item.page} onClick={() => navigate(item.page)}>{item.label}<ChevronRight size={14} /></button>)}</div>}</div>
        <button className="header-icon" aria-label="Notifications" title="No new notifications"><Bell size={18} /><span /></button>
        <button className="profile-avatar" onClick={() => navigate('profile')} aria-label="Open learner profile">PS</button>
      </header>
      {children}
    </section>
  </main>
}
