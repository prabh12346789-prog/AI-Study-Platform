import { RotateCw } from 'lucide-react'
export function RetryButton({ onRetry, busy = false }: { onRetry: () => void; busy?: boolean }) { return <button className="retry-button" type="button" onClick={onRetry} disabled={busy}><RotateCw />{busy ? 'Retrying…' : 'Try again'}</button> }
