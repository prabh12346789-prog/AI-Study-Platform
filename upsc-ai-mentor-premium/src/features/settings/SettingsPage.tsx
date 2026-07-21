import { CircleAlert, CircleCheck, Database, Server, Sparkles } from 'lucide-react'
import { ErrorState } from '../../components/feedback/ErrorState'
import { LoadingSkeleton } from '../../components/feedback/LoadingSkeleton'
import { useHealth } from '../../hooks/useHealth'

export function SettingsPage() {
  const health = useHealth()
  return <section className="page"><div className="page-heading"><span className="eyebrow">LOCAL SERVICES</span><h2>Settings</h2><p>Review the local services used by your mentor. Interface preferences stay in this browser.</p></div><div className="settings-panel"><h3>Connection health</h3>{health.isPending ? <LoadingSkeleton lines={4} /> : health.isError ? <ErrorState title="Backend unavailable" message="Start the local FastAPI backend, then try again." onRetry={() => void health.refetch()} /> : health.data && <div className="health-grid">
    <HealthRow icon={Server} label="Backend" value={health.data.status === 'ok' ? 'Connected' : 'Unavailable'} good={health.data.status === 'ok'} />
    <HealthRow icon={Sparkles} label="Local AI" value={health.data.ollama === 'reachable' ? 'Available' : 'Unavailable'} good={health.data.ollama === 'reachable'} />
    <HealthRow icon={Sparkles} label="Embedding model" value={health.data.embedding_model_available ? health.data.embedding_model : 'Unavailable'} good={health.data.embedding_model_available} />
    <HealthRow icon={Database} label="Vector store" value={health.data.vector_store === 'ready' ? 'Ready' : 'Not ready'} good={health.data.vector_store === 'ready'} />
  </div>}</div></section>
}
function HealthRow({ icon: Icon, label, value, good }: { icon: typeof Server; label: string; value: string; good: boolean }) { return <div className="health-row"><Icon /><div><small>{label}</small><strong>{value}</strong></div>{good ? <CircleCheck className="good" aria-label="Ready" /> : <CircleAlert className="bad" aria-label="Needs attention" />}</div> }
