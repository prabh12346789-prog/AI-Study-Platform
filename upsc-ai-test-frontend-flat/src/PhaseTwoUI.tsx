import type { ReactNode } from 'react'
import { AlertCircle, Inbox, LoaderCircle, RefreshCcw } from 'lucide-react'
import type { ContentBlock } from './api'

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: string; title: string; subtitle: string; actions?: ReactNode }) {
  return <header className="p2-page-header"><div>{eyebrow && <span>{eyebrow}</span>}<h1>{title}</h1><p>{subtitle}</p></div>{actions && <div className="p2-header-actions">{actions}</div>}</header>
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="p2-state"><Inbox size={26} /><strong>{title}</strong><p>{description}</p>{action}</div>
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return <div className="p2-state" role="status"><LoaderCircle className="p2-spin" size={24} /><strong>{label}</strong></div>
}

export function ErrorState({ description, retry }: { description: string; retry?: () => void }) {
  return <div className="p2-state p2-error" role="alert"><AlertCircle size={24} /><strong>Unable to load this section</strong><p>{description}</p>{retry && <button onClick={retry}><RefreshCcw size={14} /> Retry</button>}</div>
}

export function StatusBadge({ children, tone = 'blue' }: { children: ReactNode; tone?: 'blue' | 'green' | 'amber' | 'red' | 'violet' }) {
  return <span className={`p2-badge ${tone}`}>{children}</span>
}

export function ContentBlocks({ blocks }: { blocks: ContentBlock[] }) {
  return <div className="p2-content-blocks">{blocks.map((block, index) => {
    const key = `${block.type}-${index}`
    if (block.type === 'heading' || block.type === 'subheading') return <h3 key={key}>{block.title ?? block.text}</h3>
    if (block.type === 'bullet_list' || block.type === 'numbered_list') {
      const Tag = block.type === 'numbered_list' ? 'ol' : 'ul'
      return <Tag key={key}>{block.items?.map((item, i) => <li key={`${key}-${i}`}>{item}</li>)}</Tag>
    }
    if (block.type === 'table') return <div className="p2-table-wrap" key={key}><table><thead><tr>{block.headers?.map(header => <th key={header}>{header}</th>)}</tr></thead><tbody>{block.rows?.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table></div>
    return <p key={key} className={['important_fact', 'key_fact', 'prelims_point', 'mains_point'].includes(block.type) ? 'highlight' : ''}>{block.title && <strong>{block.title}: </strong>}{block.text}{block.page_ref ? <small> Page {block.page_ref}</small> : null}</p>
  })}</div>
}
