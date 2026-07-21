import { CircleAlert, CircleCheck, LoaderCircle } from 'lucide-react'
import { useHealth } from '../../hooks/useHealth'
export function ConnectionStatus() {
  const { data, isPending, isError, isFetching, refetch } = useHealth()
  if (isPending) return <span className="connection neutral" role="status"><LoaderCircle className="spin" /> Checking services</span>
  const ready = !isError && data?.status === 'ok' && data.ollama === 'reachable' && data.embedding_model_available && data.vector_store === 'ready'
  const label = isError ? 'Backend unavailable' : data?.ollama !== 'reachable' ? 'Local AI unavailable' : !data.embedding_model_available ? 'Embedding model unavailable' : data.vector_store !== 'ready' ? 'Vector store not ready' : 'Connected'
  return <span className={`connection ${ready ? 'success' : 'danger'}`} role="status" aria-live="polite" title={label}>{ready ? <CircleCheck /> : <CircleAlert />}<span>{label}</span>{!ready && <button type="button" onClick={() => void refetch()} disabled={isFetching} aria-label="Retry health check">Retry</button>}</span>
}
