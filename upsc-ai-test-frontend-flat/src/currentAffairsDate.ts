import type { CurrentAffairsArticle } from './api'

export function latestCurrentAffairsDate(articles: CurrentAffairsArticle[], fallback: string) {
  return articles.map(article => article.publication_date || article.retrieved_at.slice(0, 10)).filter(Boolean).sort().at(-1) || fallback
}

export function resolveInitialCurrentAffairsDate(articles: CurrentAffairsArticle[], fallback: string, current: string, manuallySelected: boolean) {
  return manuallySelected ? current : latestCurrentAffairsDate(articles, fallback)
}

export function articlesInRange(articles: CurrentAffairsArticle[], dateFrom: string, dateTo: string) {
  return articles.filter(article => {
    const date = article.publication_date || article.retrieved_at.slice(0, 10)
    return date >= dateFrom && date <= dateTo
  })
}
