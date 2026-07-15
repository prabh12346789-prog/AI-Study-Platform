import { FormEvent, useEffect, useState } from 'react'
import { API_BASE_URL, createVisualRoadmap, deleteVisualRoadmap, listVisualRoadmaps, saveVisualRoadmap, VisualRoadmap, VisualType } from './api'
import { RoadmapQuizPanel } from './RoadmapQuizPanel'

const TYPES: Array<{ value: VisualType; label: string; hint: string }> = [
  { value: 'timeline', label: 'Timeline', hint: 'Events across time' }, { value: 'flowchart', label: 'Flowchart', hint: 'Linked decisions' },
  { value: 'concept_map', label: 'Concept Map', hint: 'Ideas and branches' }, { value: 'comparison', label: 'Comparison', hint: 'Side-by-side dimensions' },
  { value: 'process', label: 'Process', hint: 'Ordered steps' }, { value: 'cause_effect', label: 'Cause and Effect', hint: 'Drivers and outcomes' },
]
const STAGES = ['Retrieving verified information', 'Structuring the roadmap', 'Validating facts and sources', 'Rendering visual']

export function VisualLearningPage({ onAsk }: { onAsk: (question: string) => void }) {
  const [topic, setTopic] = useState(''); const [visualType, setVisualType] = useState<VisualType>('timeline')
  const [language, setLanguage] = useState<'english' | 'hindi' | 'punjabi'>('english')
  const [roadmap, setRoadmap] = useState<VisualRoadmap | null>(null); const [history, setHistory] = useState<VisualRoadmap[]>([])
  const [loading, setLoading] = useState(false); const [stage, setStage] = useState(0); const [error, setError] = useState('')
  const [zoom, setZoom] = useState(1); const [saved, setSaved] = useState(false)
  const [showQuiz, setShowQuiz] = useState(false)
  useEffect(() => { void listVisualRoadmaps().then(setHistory).catch(() => undefined) }, [])
  useEffect(() => { if (!loading) return; const timer = window.setInterval(() => setStage(value => Math.min(3, value + 1)), 1500); return () => clearInterval(timer) }, [loading])
  async function generate(event?: FormEvent) { event?.preventDefault(); if (!topic.trim() || loading) return; setLoading(true); setStage(0); setError(''); setSaved(false)
    try { const result = await createVisualRoadmap({ topic: topic.trim(), visual_type: visualType, language }); setRoadmap(result); setZoom(1); setHistory(await listVisualRoadmaps()) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Roadmap generation failed.') } finally { setLoading(false) } }
  async function remove() { if (!roadmap || !window.confirm('Delete this roadmap and its generated files?')) return; await deleteVisualRoadmap(roadmap.id); setRoadmap(null); setHistory(await listVisualRoadmaps()) }
  async function save() { if (!roadmap) return; await saveVisualRoadmap(roadmap.id); setSaved(true) }
  return <div className="visual-page"><header className="topbar"><div><p className="eyebrow">Visual Learning</p><h1>Turn retrieved study material into a roadmap</h1></div></header>
    <form className="visual-generator" onSubmit={generate}><label>Topic<input value={topic} onChange={e => setTopic(e.target.value)} placeholder="e.g. Historical Background of the Indian Constitution" /></label>
      <div className="visual-type-grid">{TYPES.map(type => <button type="button" key={type.value} className={visualType === type.value ? 'active' : ''} onClick={() => setVisualType(type.value)}><strong>{type.label}</strong><small>{type.hint}</small></button>)}</div>
      <div className="visual-form-actions"><label>Language<select value={language} onChange={e => setLanguage(e.target.value as typeof language)}><option value="english">English</option><option value="hindi">Hindi</option><option value="punjabi">Punjabi</option></select></label><button className="send-button" disabled={loading || !topic.trim()}>Generate Roadmap</button></div></form>
    {loading && <section className="visual-state"><strong>{STAGES[stage]}</strong><p>No percentage is shown; generation depends on retrieval and the local model.</p></section>}
    {error && <section className="visual-state error"><strong>Roadmap unavailable</strong><p>{error}</p><small>Upload a relevant PDF or choose a topic covered by your study material.</small></section>}
    {!loading && !error && !roadmap && <section className="visual-state"><strong>No roadmap selected</strong><p>Generate one above, or open a recent roadmap.</p>{history.map(item => <button key={item.id} className="secondary-button" onClick={() => setRoadmap(item)}>{item.title} · {item.visual_type.replace('_', ' ')}</button>)}</section>}
    {roadmap && showQuiz && <RoadmapQuizPanel roadmap={roadmap} onClose={() => setShowQuiz(false)} />}
    {roadmap && !showQuiz && <section className="roadmap-viewer"><div className="roadmap-heading"><div><p className="eyebrow">{roadmap.subject} · {roadmap.topic}</p><h2>{roadmap.title}</h2><p>{roadmap.structure.summary}</p><small>Generated {new Date(roadmap.created_at).toLocaleString()}</small></div><div className="viewer-actions"><button onClick={() => setZoom(z => Math.max(.5, z - .15))}>−</button><button onClick={() => setZoom(1)}>Fit</button><button onClick={() => setZoom(z => Math.min(2, z + .15))}>＋</button></div></div>
      <div className="svg-viewport"><img style={{ transform: `scale(${zoom})` }} src={`${API_BASE_URL}${roadmap.svg_url}`} alt={`${roadmap.title} visual roadmap`} /></div>
      <div className="roadmap-actions"><button className="send-button" onClick={() => void save()}>{saved ? 'Saved' : 'Save'}</button><a className="secondary-button" href={`${API_BASE_URL}${roadmap.svg_url}`} download>Download SVG</a><button className="secondary-button" onClick={() => void generate()}>Regenerate</button><button className="secondary-button" onClick={() => onAsk(`Explain the key ideas in my visual roadmap: ${roadmap.title}`)}>Ask a question</button><button className="secondary-button" onClick={() => setShowQuiz(true)}>Take Quiz from Roadmap</button><button disabled title="Optional video generation — coming later">Animate Roadmap · coming later</button><button className="danger-button" onClick={() => void remove()}>Delete</button></div>
      <div className="roadmap-details"><article><h3>UPSC exam points</h3>{roadmap.structure.exam_points.length ? <ul>{roadmap.structure.exam_points.map(point => <li key={point}>{point}</li>)}</ul> : <p>No separate exam points were generated.</p>}</article><article><h3>Retrieved sources</h3>{roadmap.sources.map(source => <p key={source.id}><strong>{source.trust_level === 'official' ? 'Official Source' : source.source_type === 'web' ? 'Trusted Web Source' : 'Uploaded PDF'}</strong> · {source.title || source.document}{source.publisher ? ` · ${source.publisher}` : ''}{source.domain ? ` · ${source.domain}` : ''}{source.page_start ? `, p. ${source.page_start}${source.page_end && source.page_end !== source.page_start ? `–${source.page_end}` : ''}` : ''}{source.retrieved_at ? ` · retrieved ${new Date(source.retrieved_at).toLocaleDateString()}` : ''}{source.url && <> · <a href={source.url} target="_blank" rel="noopener noreferrer">Open source</a></>}</p>)}</article></div>
      <p className="source-note">This roadmap was created from retrieved study material. Web information is used only when indexed study material is insufficient. Review the listed sources before using it for high-stakes preparation.</p></section>}
  </div>
}
