import { useQuery } from '@tanstack/react-query'
import { fetchModels } from '../api/models.js'
import { useAppStore } from '../store/appStore.js'

export function useModelList(provider, apiKey) {
  const sessionReady = useAppStore((s) => s.sessionReady)
  const hasKey = !!apiKey

  return useQuery({
    queryKey: ['models', provider, apiKey],
    queryFn: () => fetchModels(provider, apiKey),
    enabled: sessionReady && hasKey,
    staleTime: 14 * 24 * 60 * 60 * 1000, // 14 days, matches backend cache TTL
    retry: 1,
  })
}
