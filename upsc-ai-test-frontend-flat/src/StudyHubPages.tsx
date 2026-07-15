import { BookOpen, BrainCircuit, FileText, Newspaper, RefreshCcw, Settings } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ActivityOverview } from './ActivityOverview'
import { CurrentAffairsRetentionOverview, getCurrentAffairsRetentionOverview } from './api'
import { MasteryOverview } from './MasteryOverview'
import { MentorPlan } from './MentorPlan'
import { ProfilePanel } from './ProfilePanel'
import type { AppPage } from './AppShell'

function PageIntro({ eyebrow, title, copy }: { eyebrow: string; title: string; copy: string }) {
  return <header className="page-intro"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{copy}</p></header>
}

function RetentionSnapshot() {
  const [data, setData] = useState<CurrentAffairsRetentionOverview | null>(null)
  useEffect(() => { void getCurrentAffairsRetentionOverview().then(setData).catch(() => setData(null)) }, [])
  return <section className="hub-card retention-snapshot"><div><span>Current Affairs retention</span><strong>{data ? `${Math.round(data.average_retention * 100)}%` : 'No evidence'}</strong></div><div><span>High risk</span><strong>{data?.high_risk_articles.length ?? 0}</strong></div><div><span>Due for revision</span><strong>{data?.due_for_revision.length ?? 0}</strong></div><p>{data?.high_risk_articles[0] ? `Review ${data.high_risk_articles[0].topic} before your next quiz.` : 'Take a grounded Current Affairs quiz to begin retention tracking.'}</p></section>
}

export function LibraryPage({ onUpload, uploadState }: { onUpload: () => void; uploadState: string }) {
  return <div className="hub-page"><PageIntro eyebrow="Grounded study material" title="My Library" copy="Upload your UPSC PDFs for source-grounded chat and visual roadmaps." /><section className="hub-card library-drop"><FileText size={30} /><h2>Add study material</h2><p>PDF files are processed by the existing local retrieval pipeline. Uploaded material remains the first grounding source.</p><button className="send-button" onClick={onUpload}>Upload PDF</button><small>{uploadState}</small></section><section className="compact-note"><strong>Use your library</strong><p>After processing, open AI Study Coach to ask cited questions or Visual Learning to generate a grounded roadmap.</p></section></div>
}

export function RevisionPage({ trackingActive }: { trackingActive: boolean }) {
  return <div className="hub-page"><PageIntro eyebrow="Focused recovery" title="Revision Center" copy="Review weak mastery, forgetting risk, and mentor actions calculated from reliable evidence." /><MentorPlan /><RetentionSnapshot /><MasteryOverview /><ActivityOverview trackingActive={trackingActive} /></div>
}

export function ProgressPage({ trackingActive }: { trackingActive: boolean }) {
  return <div className="hub-page"><PageIntro eyebrow="Evidence, not vanity metrics" title="Progress" copy="Seven-day activity, mastery estimates, and revision risk from your real platform usage." /><ActivityOverview trackingActive={trackingActive} period="7d" /><RetentionSnapshot /><MasteryOverview /></div>
}

export function ProfilePage({ settings = false }: { settings?: boolean }) {
  return <div className="hub-page"><PageIntro eyebrow={settings ? 'Workspace preferences' : 'Personalisation'} title={settings ? 'Settings' : 'Learner Profile'} copy={settings ? 'Control the same saved learning preferences used by chat and recommendations.' : 'Set language, depth, answer format, daily target, and preferred content type.'} />{settings && <section className="compact-note"><Settings size={18} /><strong>Local-first settings</strong><p>Your preferences apply only inside this study platform.</p></section>}<ProfilePanel /></div>
}

export function QuizzesPage({ onNavigate }: { onNavigate: (page: AppPage) => void }) {
  return <div className="hub-page"><PageIntro eyebrow="Active recall" title="Quizzes" copy="Open a quiz only where grounded content is already available." /><div className="route-card-grid"><button className="route-card" onClick={() => onNavigate('current_affairs')}><Newspaper /><span><strong>Current Affairs Quiz</strong><small>Daily, weekly, and custom quizzes from accepted articles.</small></span></button><button className="route-card" onClick={() => onNavigate('visual')}><BrainCircuit /><span><strong>Roadmap Quiz</strong><small>Recall questions generated from a saved grounded roadmap.</small></span></button><button className="route-card" onClick={() => onNavigate('revision')}><RefreshCcw /><span><strong>Review weak areas</strong><small>Use mastery and forgetting risk before choosing a quiz.</small></span></button></div><section className="compact-note"><BookOpen size={18} /><strong>Reliable evidence only</strong><p>Completed quiz results can update mastery; simply opening or reading content does not.</p></section></div>
}
