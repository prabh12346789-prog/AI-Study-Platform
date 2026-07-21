import { z } from 'zod'

const schema = z.object({
  VITE_API_BASE_URL: z.string({ error: 'VITE_API_BASE_URL is missing. Copy .env.example to .env.' }).url('VITE_API_BASE_URL must be a valid http(s) URL.').refine(value => ['http:', 'https:'].includes(new URL(value).protocol), 'VITE_API_BASE_URL must use http or https.'),
})

export function validateEnvironment(input: Record<string, unknown>) {
  const result = schema.safeParse(input)
  if (!result.success) throw new Error(result.error.issues.map(issue => issue.message).join(' '))
  return { apiBaseUrl: result.data.VITE_API_BASE_URL.replace(/\/$/, '') }
}

export const environment = validateEnvironment({
  VITE_API_BASE_URL: import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV || import.meta.env.MODE === 'test' ? 'http://127.0.0.1:8000' : undefined),
})
