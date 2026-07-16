import type { CurrentAffairsQuizCreate, CurrentAffairsQuizPeriod } from './api'

function addUtcDays(date: string, days: number) {
  const value = new Date(`${date}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

export function buildCurrentAffairsQuizRequest(
  periodType: CurrentAffairsQuizPeriod,
  selectedDate: string,
  customFrom = selectedDate,
  customTo = selectedDate,
): CurrentAffairsQuizCreate {
  const dateFrom = periodType === 'custom' ? customFrom : periodType === 'weekly' ? addUtcDays(selectedDate, -6) : selectedDate
  const dateTo = periodType === 'custom' ? customTo : selectedDate
  return {
    period_type: periodType,
    date_from: dateFrom,
    date_to: dateTo,
    question_count: 5,
    difficulty: 'standard',
  }
}
