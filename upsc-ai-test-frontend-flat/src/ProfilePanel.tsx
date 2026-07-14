import { FormEvent, useEffect, useState } from 'react'
import {
  getProfile, getProfileInsights, LearnerProfile, ProfileInsights, ProfileInput,
  resetProfile, saveProfile,
} from './api'

function studyTime(seconds: number) { return `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m` }

export function ProfilePanel() {
  const [profile, setProfile] = useState<LearnerProfile | null>(null)
  const [insights, setInsights] = useState<ProfileInsights | null>(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  async function load() {
    setLoading(true); setError('')
    try {
      const [nextProfile, nextInsights] = await Promise.all([getProfile(), getProfileInsights()])
      setProfile(nextProfile); setInsights(nextInsights)
      if (!nextProfile.onboarding_completed) setOpen(true)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load profile.') }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  function update<K extends keyof ProfileInput>(key: K, value: ProfileInput[K]) {
    setProfile(current => current ? { ...current, [key]: value } : current)
    setSaved(false)
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!profile) return
    setError('')
    try {
      const input: ProfileInput = {
        preferred_language: profile.preferred_language, preferred_depth: profile.preferred_depth,
        preferred_format: profile.preferred_format, daily_study_target_minutes: profile.daily_study_target_minutes,
        preferred_content_type: profile.preferred_content_type,
      }
      setProfile(await saveProfile(input, !profile.onboarding_completed)); setSaved(true)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to save profile.') }
  }
  async function reset() {
    if (!window.confirm('Reset your learner profile to defaults?')) return
    try { await resetProfile(); setSaved(false); await load() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to reset profile.') }
  }

  return <section className="profile-panel">
    <button className="profile-heading" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      <span><span className="eyebrow">Learner profile</span><strong>{profile?.onboarding_completed ? 'Preferences & 7-day insights' : 'Set up your study experience'}</strong></span>
      <span>{open ? 'Close' : 'Edit'}</span>
    </button>
    {open && (loading ? <div className="profile-state">Loading profile…</div> : error && !profile ?
      <div className="profile-state error">{error}</div> : profile && <>
        {!profile.onboarding_completed && <div className="onboarding-note"><strong>Step 1 of 1</strong> · Five quick choices personalize answer presentation. You can skip and edit these later.</div>}
        <form className="profile-form" onSubmit={submit}>
          <label>Language<select value={profile.preferred_language} onChange={e => update('preferred_language', e.target.value as LearnerProfile['preferred_language'])}>
            <option value="auto">Auto</option><option value="english">English</option><option value="hindi">Hindi</option><option value="punjabi">Punjabi</option>
          </select></label>
          <label>Answer depth<select value={profile.preferred_depth} onChange={e => update('preferred_depth', e.target.value as LearnerProfile['preferred_depth'])}>
            <option value="quick">Quick</option><option value="standard">Standard</option><option value="detailed">Detailed</option>
          </select></label>
          <label>Answer format<select value={profile.preferred_format} onChange={e => update('preferred_format', e.target.value as LearnerProfile['preferred_format'])}>
            <option value="bullets">Bullets</option><option value="structured">Structured</option><option value="explanation">Explanation</option><option value="mixed">Mixed</option>
          </select></label>
          <label>Daily target<input type="number" min="1" max="1440" value={profile.daily_study_target_minutes} onChange={e => update('daily_study_target_minutes', Number(e.target.value))} /></label>
          <label>Content type<select value={profile.preferred_content_type} onChange={e => update('preferred_content_type', e.target.value as LearnerProfile['preferred_content_type'])}>
            <option value="text">Text</option><option value="quiz">Quiz</option><option value="video">Video</option><option value="mixed">Mixed</option>
          </select></label>
          <div className="profile-actions"><button className="send-button" type="submit">{profile.onboarding_completed ? 'Save profile' : 'Complete setup'}</button>
            {!profile.onboarding_completed && <button type="button" className="icon-button" onClick={() => setOpen(false)}>Skip</button>}
            <button type="button" className="icon-button" onClick={() => void reset()}>Reset</button></div>
        </form>
        {saved && <div className="saved-state">Profile saved.</div>}{error && <div className="profile-state error">{error}</div>}
        <div className="profile-insights">
          <div><span>Most studied</span><strong>{insights?.most_studied_subject ?? 'No data'}</strong></div>
          <div><span>Top topic</span><strong>{insights?.most_studied_topic ?? 'No data'}</strong></div>
          <div><span>Active days</span><strong>{insights?.active_days_7d ?? 0}</strong></div>
          <div><span>Study time</span><strong>{studyTime(insights?.total_study_seconds_7d ?? 0)}</strong></div>
          <div><span>Questions</span><strong>{insights?.questions_asked_7d ?? 0}</strong></div>
        </div>
        <p className="privacy-note">Only activity inside this study platform is used for learning insights.</p>
      </>)}
  </section>
}
