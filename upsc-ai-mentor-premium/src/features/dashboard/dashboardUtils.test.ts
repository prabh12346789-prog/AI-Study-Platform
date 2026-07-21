import { describe, expect, it } from 'vitest'
import { clampPercent, formatDuration, weeklyStudy } from './dashboardUtils'
describe('dashboard calculations',()=>{
 it('safely clamps invalid percentages',()=>{expect(clampPercent(Number.NaN)).toBe(0);expect(clampPercent(Number.POSITIVE_INFINITY)).toBe(0);expect(clampPercent(120)).toBe(100)})
 it('formats study time correctly',()=>{expect(formatDuration(1800)).toBe('30 min');expect(formatDuration(5400)).toBe('1 hr 30 min')})
 it('fills the known seven-day range with zeros',()=>{expect(weeklyStudy([])).toHaveLength(7);expect(weeklyStudy([]).every(day=>day.seconds===0)).toBe(true)})
})
