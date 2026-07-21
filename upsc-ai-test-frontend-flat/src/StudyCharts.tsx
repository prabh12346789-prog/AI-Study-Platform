import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Area, AreaChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ActivityBreakdown, ActivitySummary, TopicMastery } from './api'

const COLORS = ['#7c6ee6', '#38bdf8', '#fbbf24', '#4ade80', '#fb7185', '#a78bfa']
const RISK_COLORS: Record<'low' | 'medium' | 'high', string> = {
  low: '#4ade80',
  medium: '#fbbf24',
  high: '#ec7180',
}

export function formatStudyDuration(seconds: number) {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.round(seconds / 60)
  return `${minutes}m`
}

export function formatStudyHours(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`
}

export interface DailyStudyPoint {
  date: string
  label: string
  study_seconds: number
}

function formatDayLabel(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' })
}

export function extractDailyTrend(summary: ActivitySummary): DailyStudyPoint[] {
  const raw = (summary as any).daily_breakdown ?? (summary as any).daily_activity ?? (summary as any).history ?? null
  const last7Days: DailyStudyPoint[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    const dateStr = d.toISOString().slice(0, 10)
    last7Days.push({
      date: dateStr,
      label: formatDayLabel(dateStr),
      study_seconds: 0,
    })
  }
  if (Array.isArray(raw) && raw.length > 0) {
    const map = new Map<string, number>()
    for (const item of raw) {
      const dateKey = String(item.date ?? item.day ?? item.label ?? '').slice(0, 10)
      const secs = Number(item.study_seconds ?? item.duration_seconds ?? item.total ?? 0)
      if (dateKey) map.set(dateKey, secs)
    }
    return last7Days.map((pt) => ({
      ...pt,
      study_seconds: map.get(pt.date) ?? pt.study_seconds,
    }))
  }
  return last7Days
}

export function prepareSubjectDonut(items: ActivityBreakdown[]) {
  const subjects = items.filter((item) => item.study_seconds > 0).sort((a, b) => b.study_seconds - a.study_seconds)
  const total = subjects.reduce((sum, item) => sum + item.study_seconds, 0)
  if (!subjects.length) return { total: 0, slices: [] as Array<ActivityBreakdown & { color: string }> }
  if (subjects.length <= 5) {
    return { total, slices: subjects.map((item, index) => ({ ...item, color: COLORS[index % COLORS.length] })) }
  }
  const visible = subjects.slice(0, 4).map((item, index) => ({ ...item, color: COLORS[index % COLORS.length] }))
  const otherTotal = subjects.slice(4).reduce((sum, item) => sum + item.study_seconds, 0)
  return { total, slices: [...visible, { name: 'Other', study_seconds: otherTotal, event_count: 0, color: COLORS[4] }] }
}

export function buildRiskDistribution(topics: TopicMastery[]) {
  const counts = { low: 0, medium: 0, high: 0 }
  for (const topic of topics) {
    counts[topic.risk_level] += 1
  }
  return [
    { label: 'High risk', value: counts.high, color: RISK_COLORS.high },
    { label: 'Medium risk', value: counts.medium, color: RISK_COLORS.medium },
    { label: 'Low risk', value: counts.low, color: RISK_COLORS.low },
  ]
}

export function StudyTrendChart({ data }: { data: DailyStudyPoint[] }) {
  const allZero = data.every((point) => point.study_seconds === 0)
  return (
    <div className="chart-card study-trend-card">
      <div className="chart-header"><h2>Study Progress</h2><p>{allZero ? 'No study minutes were recorded on these days.' : 'Your study time across the most recent days.'}</p></div>
      {data.length === 0 ? (
        <div className="chart-empty">No daily study trend is available.</div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <AreaChart data={data} margin={{ top: 8, right: 10, left: -10, bottom: 10 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={(value) => `${Math.round(value / 60)}m`} tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip formatter={(value: any) => formatStudyDuration(Number(value || 0))} labelFormatter={(label: any) => `Day: ${String(label)}`} contentStyle={{ background: 'rgba(8, 13, 23, 0.92)', border: '1px solid rgba(157, 174, 207, .12)', color: '#eef3fb' }} />
            <Area type="monotone" dataKey="study_seconds" stroke="#7c6ee6" fill="rgba(124, 110, 230, 0.22)" fillOpacity={1} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
          </AreaChart>
        </ResponsiveContainer>
      )}
      <p className="sr-only">Study progress chart showing study duration for each day. Exact values are available in the tooltip.</p>
    </div>
  )
}

function donutTooltip(value: any, name: any): [string, string] {
  return [formatStudyDuration(Number(value || 0)), String(name)]
}

export function SubjectDonutChart({ breakdown }: { breakdown: ActivityBreakdown[] }) {
  const { total, slices } = prepareSubjectDonut(breakdown)
  return (
    <div className="chart-card donut-card">
      <div className="chart-header"><h2>Subject time distribution</h2><p>Total weekly study: {formatStudyDuration(total)}</p></div>
      {slices.length === 0 ? (
        <div className="chart-empty">No subject study time is available for the last seven days.</div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <PieChart>
            <Pie data={slices} dataKey="study_seconds" nameKey="name" innerRadius={70} outerRadius={110} paddingAngle={3} cornerRadius={8}>
              {slices.map((entry, index) => (
                <Cell key={entry.name} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip formatter={donutTooltip as any} contentStyle={{ background: 'rgba(8, 13, 23, 0.92)', border: '1px solid rgba(157, 174, 207, .12)', color: '#eef3fb' }} />
            <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ paddingLeft: 12, fontSize: 12, color: 'var(--text-secondary)' }} />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

export function RiskDonutChart({ topics }: { topics: TopicMastery[] }) {
  const slices = buildRiskDistribution(topics).filter((item) => item.value > 0)
  return (
    <div className="chart-card donut-card">
      <div className="chart-header"><h2>Forgetting risk</h2><p>Risk distribution across current mastery topics.</p></div>
      {slices.length === 0 ? (
        <div className="chart-empty">No risk distribution is available.</div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <PieChart>
            <Pie data={slices} dataKey="value" nameKey="label" innerRadius={54} outerRadius={90} paddingAngle={3} cornerRadius={8}>
              {slices.map((entry) => (<Cell key={entry.label} fill={entry.color} />))}
            </Pie>
            <Tooltip formatter={(value: any) => [String(value), 'Topics'] as [string, string]} contentStyle={{ background: 'rgba(8, 13, 23, 0.92)', border: '1px solid rgba(157, 174, 207, .12)', color: '#eef3fb' }} />
            <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ paddingLeft: 12, fontSize: 12, color: 'var(--text-secondary)' }} />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

export function RevealSection({ className, children }: { className?: string; children: ReactNode }) {
  const ref = useRef<HTMLElement | null>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setVisible(true)
      return
    }
    const node = ref.current
    if (!node) {
      setVisible(true)
      return
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true)
        observer.disconnect()
      }
    }, { threshold: 0.12 })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <section ref={ref} className={`reveal-section ${className ?? ''} ${visible ? 'visible' : 'hidden'}`}>
      {children}
    </section>
  )
}
