import { FormEvent, useEffect, useRef, useState } from 'react'
import { ArrowLeftRight, Download, Expand, GitBranch, ListOrdered, Network, RefreshCcw, Route, Save, Sparkles, Timer, Trash2 } from 'lucide-react'
import { API_BASE_URL, createVisualRoadmap, deleteVisualRoadmap, listVisualRoadmaps, saveVisualRoadmap, VisualRoadmap, VisualRoadmapApiError, VisualType } from './api'
import { RoadmapQuizPanel } from './RoadmapQuizPanel'
import { EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from './PhaseTwoUI'
import { VISUAL_PREVIEW_STEPS } from './phaseTwoFallback'

const TYPES: Array<{ value: VisualType; label: string; hint: string; icon: typeof Timer }> = [
  { value: 'timeline', label: 'Timeline', hint: 'Chronological events', icon: Timer }, { value: 'flowchart', label: 'Flowchart', hint: 'Step-by-step flow', icon: GitBranch },
  { value: 'concept_map', label: 'Concept Map', hint: 'Connected ideas', icon: Network }, { value: 'comparison', label: 'Comparison', hint: 'Side-by-side analysis', icon: ArrowLeftRight },
  { value: 'process', label: 'Process', hint: 'Sequential stages', icon: ListOrdered }, { value: 'cause_effect', label: 'Cause & Effect', hint: 'Drivers and outcomes', icon: Route },
]
const STAGES = ['Retrieving grounded material', 'Structuring the visual', 'Validating facts and sources', 'Rendering the SVG artifact']

function DemoVisualPreview() {
  return <section className="demo-visual-preview p2-card"><header><div><StatusBadge tone="violet">Layout preview</StatusBadge><h2>Timeline visual structure</h2><p>An illustrative layout preview. Generate a topic to create a real UPSC visual.</p></div></header><div className="demo-timeline">{VISUAL_PREVIEW_STEPS.map((step, index) => <article className={step.tone} key={step.year}><strong>{step.year}</strong><span>{step.title}</span><i>{index + 1}</i></article>)}</div><footer>Preview only · Generated visuals include source disclosure, SVG/PNG export, save, fullscreen and quiz actions.</footer></section>
}

export function VisualLearningPage({ onAsk }: { onAsk: (question: string) => void }) {
  const [topic, setTopic] = useState('')
  const [source, setSource] = useState<'general' | 'book' | 'pdf' | 'current_affairs'>('general')
  const [subject, setSubject] = useState('')
  const [detail, setDetail] = useState<'concise' | 'standard' | 'detailed'>('standard')
  const [visualType, setVisualType] = useState<VisualType>('timeline')
  const [language, setLanguage] = useState<'english' | 'hindi' | 'punjabi'>('english')
  const [roadmap, setRoadmap] = useState<VisualRoadmap | null>(null)
  const [history, setHistory] = useState<VisualRoadmap[]>([])
  const [loading, setLoading] = useState(false)
  const [stage, setStage] = useState(0)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [showQuiz, setShowQuiz] = useState(false)
  const previewRef = useRef<HTMLDivElement>(null)

  async function loadHistory() { try { setHistory(await listVisualRoadmaps()) } catch { setHistory([]) } }
  useEffect(() => { void loadHistory() }, [])
  useEffect(() => { if (!loading) return; const timer = window.setInterval(() => setStage(value => Math.min(STAGES.length - 1, value + 1)), 1600); return () => clearInterval(timer) }, [loading])

  async function generate(event?: FormEvent) {
    event?.preventDefault(); if (!topic.trim() || loading) return
    setLoading(true); setStage(0); setError(''); setSaved(false); setShowQuiz(false)
    if (source !== 'general') {
      setError(`${source === 'book' ? 'UPSC Book' : source === 'pdf' ? 'Uploaded PDF' : 'Current Affairs'} generation requires selecting an eligible source. Source selection is not available until matching records exist.`)
      setLoading(false); return
    }
    const groundedTopic = `${topic.trim()}${subject.trim() ? ` — ${subject.trim()}` : ''}`
    try { const result = await createVisualRoadmap({ topic: groundedTopic, visual_type: visualType, language, detail_level: detail, source_type: 'general', conversation_id: null }); setRoadmap(result); await loadHistory() }
    catch (reason) { setError(reason instanceof VisualRoadmapApiError && reason.action ? `${reason.message} Developer action: ${reason.action}` : reason instanceof Error ? reason.message : 'Visual generation failed. Retry when the local AI service is available.') }
    finally { setLoading(false) }
  }

  async function save() { if (!roadmap) return; await saveVisualRoadmap(roadmap.id); setSaved(true) }
  async function remove(item: VisualRoadmap) { if (!window.confirm(`Delete “${item.title}”?`)) return; await deleteVisualRoadmap(item.id); if (roadmap?.id === item.id) setRoadmap(null); await loadHistory() }
  async function fullscreen() { await previewRef.current?.requestFullscreen?.() }
  async function exportPng() {
    if (!roadmap) return
    try {
      const response = await fetch(`${API_BASE_URL}${roadmap.svg_url}`)
      if (!response.ok) throw new Error('SVG unavailable')
      const objectUrl = URL.createObjectURL(await response.blob())
      const image = new Image()
      image.onload = () => {
        const canvas = document.createElement('canvas')
        canvas.width = Math.max(image.naturalWidth, 1200)
        canvas.height = Math.round(canvas.width * image.naturalHeight / Math.max(image.naturalWidth, 1))
        const context = canvas.getContext('2d')
        if (!context) { URL.revokeObjectURL(objectUrl); setError('PNG export is unavailable in this browser.'); return }
        context.fillStyle = '#06132a'; context.fillRect(0, 0, canvas.width, canvas.height)
        context.drawImage(image, 0, 0, canvas.width, canvas.height)
        canvas.toBlob(blob => {
          URL.revokeObjectURL(objectUrl)
          if (!blob) { setError('PNG export could not be created.'); return }
          const link = document.createElement('a'); const pngUrl = URL.createObjectURL(blob)
          link.href = pngUrl; link.download = `${roadmap.id}.png`; link.click()
          window.setTimeout(() => URL.revokeObjectURL(pngUrl), 1000)
        }, 'image/png')
      }
      image.onerror = () => { URL.revokeObjectURL(objectUrl); setError('PNG export could not load the rendered visual.') }
      image.src = objectUrl
    } catch { setError('PNG export is unavailable because the rendered SVG could not be loaded.') }
  }

  return <div className="p2-page visual-redesign">
    <PageHeader eyebrow="Grounded visual study" title="Visual Learning" subtitle="Transform difficult UPSC topics into clear, source-backed visual artifacts." />
    <div className="visual-layout"><main>
      <form className="visual-config p2-card" onSubmit={generate}>
        <label className="visual-topic"><span>What do you want to visualize?</span><input value={topic} maxLength={300} onChange={event => setTopic(event.target.value)} placeholder="Enter a UPSC topic" /><small>{topic.length} / 300</small></label>
        <div className="visual-config-row"><label><span>Source focus</span><select value={source} onChange={event => setSource(event.target.value as typeof source)}><option value="general">General</option><option value="book">UPSC Book</option><option value="pdf">Uploaded PDF</option><option value="current_affairs">Current Affairs</option></select></label><label><span>Subject</span><input value={subject} onChange={event => setSubject(event.target.value)} placeholder="Optional subject" /></label><label><span>Language</span><select value={language} onChange={event => setLanguage(event.target.value as typeof language)}><option value="english">English</option><option value="hindi">Hindi</option><option value="punjabi">Punjabi</option></select></label><label><span>Detail level</span><select value={detail} onChange={event => setDetail(event.target.value as typeof detail)}><option value="concise">Concise</option><option value="standard">Standard</option><option value="detailed">Detailed</option></select></label></div>
        <fieldset><legend>Choose layout style</legend><div className="visual-type-selector">{TYPES.map(type => { const Icon = type.icon; return <button type="button" key={type.value} className={visualType === type.value ? 'active' : ''} aria-pressed={visualType === type.value} onClick={() => setVisualType(type.value)}><Icon /><strong>{type.label}</strong><small>{type.hint}</small></button> })}</div></fieldset>
        <button className="p2-primary visual-generate" disabled={!topic.trim() || loading}><Sparkles size={16} />{loading ? 'Generating visual…' : 'Generate visual'}</button>
      </form>

      {loading && <section className="visual-progress p2-card"><LoadingState label={STAGES[stage]} /><div>{STAGES.map((item, index) => <span className={index <= stage ? 'active' : ''} key={item}>{index < stage ? '✓' : index + 1} {item}</span>)}</div><small>Generation time depends on local retrieval and the model. Cancellation is not supported by the current API.</small></section>}
      {error && <ErrorState description={error} retry={() => void generate()} />}
      {!loading && !roadmap && <DemoVisualPreview />}
      {roadmap && showQuiz && <RoadmapQuizPanel roadmap={roadmap} onClose={() => setShowQuiz(false)} />}
      {roadmap && !showQuiz && <section className="visual-preview p2-card"><header><div><StatusBadge tone="green">Structured roadmap SVG</StatusBadge><h2>{roadmap.title}</h2><p>{roadmap.structure.summary}</p></div><div><button onClick={() => void save()}><Save size={14} />{saved ? 'Saved' : 'Save'}</button><a href={`${API_BASE_URL}${roadmap.svg_url}`} download><Download size={14} />Download SVG</a><button onClick={() => void exportPng()}><Download size={14} />Export PNG</button><button onClick={() => void fullscreen()}><Expand size={14} />Fullscreen</button></div></header><div className="visual-canvas" ref={previewRef}><img src={`${API_BASE_URL}${roadmap.svg_url}`} alt={`${roadmap.title} generated visual roadmap`} onError={() => setError('The roadmap record exists, but its rendered SVG is unavailable.')} /></div><footer><button className="p2-primary" onClick={() => void generate()}><RefreshCcw size={14} />Regenerate</button><button onClick={() => onAsk(`Explain the key ideas in my visual roadmap: ${roadmap.title}`)}>Ask AI</button><button onClick={() => setShowQuiz(true)}>Take roadmap quiz</button></footer><div className="visual-grounding"><h3>Source grounding</h3>{roadmap.sources.length ? roadmap.sources.map(item => <p key={item.id}><strong>{item.title || item.document || 'Grounded source'}</strong>{item.publisher ? ` · ${item.publisher}` : ''}{item.page_start ? ` · page ${item.page_start}` : ''}{item.url ? <> · <a href={item.url} target="_blank" rel="noreferrer">Open source</a></> : null}</p>) : <p>No separate source list was returned. Review the visual before high-stakes use.</p>}</div></section>}
    </main>
      <aside className="visual-history p2-card"><div className="p2-section-head"><div><h2>Visual History</h2><p>{history.length} generated</p></div></div>{history.length ? history.map(item => <article key={item.id}><button onClick={() => { setRoadmap(item); setError(''); setShowQuiz(false) }}><img src={`${API_BASE_URL}${item.svg_url}`} alt="" /><span><strong>{item.title}</strong><small>{item.visual_type.replaceAll('_', ' ')} · {new Date(item.created_at).toLocaleDateString()}</small></span></button><button aria-label={`Delete ${item.title}`} onClick={() => void remove(item)}><Trash2 size={14} /></button></article>) : <EmptyState title="No visual history" description="Only real generated visual roadmaps will appear here." />}</aside>
    </div>
  </div>
}
