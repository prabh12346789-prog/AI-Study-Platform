import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type PropsWithChildren } from 'react'
const createClient = () => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false }, mutations: { retry: 0 } } })
export function AppProviders({ children }: PropsWithChildren) { const [client] = useState(createClient); return <QueryClientProvider client={client}>{children}</QueryClientProvider> }
