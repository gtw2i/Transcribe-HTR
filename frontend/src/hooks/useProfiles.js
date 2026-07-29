import { useQuery } from '@tanstack/react-query'
import { listProfiles, getProfile } from '../api/profiles.js'
import { useAppStore } from '../store/appStore.js'

export function useProfiles() {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['profiles'],
    queryFn: listProfiles,
    enabled: sessionReady,
    staleTime: 30_000,
  })
}

export function useProfile(slug) {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['profile', slug],
    queryFn: () => getProfile(slug),
    enabled: sessionReady && !!slug,
    staleTime: 30_000,
  })
}
