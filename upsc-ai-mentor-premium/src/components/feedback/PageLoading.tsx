import { LoadingSkeleton } from './LoadingSkeleton'
export function PageLoading({ label = 'Loading page' }: { label?: string }) { return <section className="page" aria-label={label}><LoadingSkeleton lines={5} /></section> }
