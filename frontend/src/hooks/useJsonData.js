import { useQuery } from '@tanstack/react-query'
import { getJson } from '../api/files.js'
import { useAppStore } from '../store/appStore.js'

export function useJsonData(root) {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['json', root],
    queryFn: () => getJson(root),
    enabled: sessionReady && !!root,
    staleTime: 10_000,
  })
}
