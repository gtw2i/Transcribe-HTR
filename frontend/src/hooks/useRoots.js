import { useQuery } from '@tanstack/react-query'
import { listRoots } from '../api/files.js'
import { useAppStore } from '../store/appStore.js'

export function useRoots() {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['roots'],
    queryFn: listRoots,
    enabled: sessionReady,
    staleTime: 5_000,
  })
}
