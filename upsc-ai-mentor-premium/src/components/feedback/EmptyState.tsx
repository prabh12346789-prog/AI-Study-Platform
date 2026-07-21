import { Inbox } from 'lucide-react'
export function EmptyState({ title, message }: { title: string; message: string }) { return <div className="feedback-state"><Inbox /><h3>{title}</h3><p>{message}</p></div> }
