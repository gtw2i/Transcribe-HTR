import { useQuery } from '@tanstack/react-query'
import { analyze, diff, getAttemptText, getOptions, listAttempts } from '../api/consistency.js'
import { useAppStore } from '../store/appStore.js'

/**
 * React Query is the client half of the two-layer cache (D8). Because the
 * analysis is a pure function of its request, a query key built from the
 * request is exact: re-selecting a previous combination is instant and nothing
 * can go stale except when the document itself changes.
 */

export function useConsistencyOptions() {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['consistency', 'options'],
    queryFn: getOptions,
    enabled: sessionReady,
    staleTime: Infinity,
  })
}

export function useAttempts(root) {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['consistency', 'attempts', root],
    queryFn: () => listAttempts(root),
    enabled: sessionReady && !!root,
    staleTime: 5_000,
  })
}

export function useAttemptText(root, attemptId, normalizationProfile, tokenizer) {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['consistency', 'attemptText', root, attemptId, normalizationProfile, tokenizer],
    queryFn: () => getAttemptText(root, attemptId, normalizationProfile, tokenizer),
    enabled: sessionReady && !!root && !!attemptId,
    staleTime: 60_000,
  })
}

/**
 * @param {object} params  root, attemptIds, normalizationProfile, tokenizer
 * @param {boolean} enabled  false until the user has asked for an analysis
 */
export function useAnalysis({ root, attemptIds, normalizationProfile, tokenizer }, enabled) {
  const sessionReady = useAppStore((s) => s.sessionReady)
  const sortedIds = [...(attemptIds || [])].sort()

  return useQuery({
    queryKey: ['consistency', 'analysis', root, sortedIds, normalizationProfile, tokenizer],
    queryFn: () =>
      analyze({
        root,
        attempt_ids: sortedIds,
        normalization_profile: normalizationProfile,
        tokenizer,
      }),
    enabled: !!enabled && sessionReady && !!root && sortedIds.length >= 2,
    staleTime: Infinity,
    retry: false,
  })
}

/**
 * The full-set baseline (§21), kept alongside the filtered analysis so the two
 * can be compared. It is just a second cache entry, so keeping it costs nothing.
 */
export function useBaselineAnalysis({ root, allIds, normalizationProfile, tokenizer }, enabled) {
  return useAnalysis(
    { root, attemptIds: allIds, normalizationProfile, tokenizer },
    enabled && (allIds || []).length >= 2,
  )
}

export function useDiff({ root, aId, bId, texts, normalizationProfile, tokenizer }, enabled) {
  const sessionReady = useAppStore((s) => s.sessionReady)

  return useQuery({
    queryKey: ['consistency', 'diff', root, aId, bId, normalizationProfile, tokenizer],
    queryFn: () =>
      diff({
        root,
        a_id: aId,
        b_id: bId,
        texts: texts || {},
        normalization_profile: normalizationProfile,
        tokenizer,
      }),
    enabled: !!enabled && sessionReady && !!root && !!aId && !!bId && aId !== bId,
    staleTime: 60_000,
    retry: false,
  })
}
