import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppProviders } from './providers'
import { appRoutes } from './router'

const healthy = { status: 'ok', database: 'ready', ollama: 'reachable', embedding_provider: 'ollama', embedding_model: 'nomic-embed-text', embedding_model_available: true, embeddings: 'available', vector_store: 'ready' }
function mockHealth(value = healthy) { return vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } })) }
function renderPath(path: string) { const router = createMemoryRouter(appRoutes, { initialEntries: [path] }); render(<AppProviders><RouterProvider router={router} /></AppProviders>); return router }
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('application routing and health', () => {
  it('configures root to redirect to dashboard', () => { const indexRoute = appRoutes[0].children[0]; expect(indexRoute).toMatchObject({ index: true }); expect(indexRoute.element).toMatchObject({ props: { to: '/dashboard' } }) })
  it('renders direct routes with stable navigation URLs', () => { mockHealth(); renderPath('/library'); expect(screen.getByRole('heading', { level: 2, name: 'My Library' })).toBeInTheDocument(); expect(screen.getByRole('link', { name: 'Quizzes' })).toHaveAttribute('href', '/quizzes') })
  it('shows a proper Not Found page and no Community route', () => { mockHealth(); renderPath('/community'); expect(screen.getByRole('heading', { name: /outside the study plan/i })).toBeInTheDocument(); expect(screen.queryByRole('link', { name: /community/i })).not.toBeInTheDocument() })
  it('opens and closes the accessible mobile drawer', async () => { mockHealth(); renderPath('/library'); fireEvent.click(screen.getByRole('button', { name: 'Open navigation' })); expect(screen.getByRole('dialog')).toBeInTheDocument(); fireEvent.keyDown(document, { key: 'Escape' }); await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument()) })
  it('shows loading and then the real connected state', async () => { let resolve!: (response: Response) => void; vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise<Response>(done => { resolve = done })); renderPath('/settings'); expect(screen.getByText('Checking services')).toBeInTheDocument(); resolve(new Response(JSON.stringify(healthy), { status: 200 })); expect((await screen.findAllByText('Connected')).length).toBeGreaterThan(0) })
  it('shows a backend-unavailable state with retry', async () => { vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('offline')); renderPath('/settings'); expect((await screen.findAllByText('Backend unavailable', {}, { timeout: 3_000 })).length).toBeGreaterThan(0); expect(screen.getByRole('button', { name: 'Retry health check' })).toBeInTheDocument() })
  it('shares one health request between Settings and the Sidebar indicator', async () => { const fetchMock = mockHealth(); renderPath('/settings'); expect(await screen.findAllByText('Connected')).toHaveLength(2); expect(fetchMock).toHaveBeenCalledTimes(1) })
})
