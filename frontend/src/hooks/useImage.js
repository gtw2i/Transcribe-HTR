import { useQuery } from '@tanstack/react-query'
import { getImage } from '../api/files.js'
import { useAppStore } from '../store/appStore.js'

export function useImage(root) {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['image', root],
    queryFn: () => getImage(root),
    enabled: sessionReady && !!root,
    staleTime: Infinity,
  })
}
