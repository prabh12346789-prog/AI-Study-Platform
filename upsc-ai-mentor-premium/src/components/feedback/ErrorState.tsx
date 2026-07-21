import { CircleAlert } from 'lucide-react'
import { RetryButton } from './RetryButton'
export function ErrorState({ title = 'Unable to load', message, onRetry }: { title?: string; message: string; onRetry?: () => void }) { return <div className="feedback-state" role="alert"><CircleAlert /><h3>{title}</h3><p>{message}</p>{onRetry && <RetryButton onRetry={onRetry} />}</div> }
