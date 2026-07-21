import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../api/health'
export const healthQueryKey = ['health'] as const
export function useHealth() { return useQuery({ queryKey: healthQueryKey, queryFn: ({ signal }) => getHealth(signal), staleTime: 20_000, refetchInterval: 30_000, refetchIntervalInBackground: false }) }
