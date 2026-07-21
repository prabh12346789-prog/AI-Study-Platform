import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
export function NotFoundPage() { return <section className="page not-found"><span className="eyebrow">404 · NOT FOUND</span><h2>This page is outside the study plan.</h2><p>The address may be incorrect or the page may have moved.</p><Link to="/dashboard"><ArrowLeft /> Return to Dashboard</Link></section> }
