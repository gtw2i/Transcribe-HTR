import { useState, useEffect, useRef } from 'react'
import { colorize } from '../api/colorize.js'
import { useAppStore } from '../store/appStore.js'

export function useColorize() {
  const [colorizedHtml, setColorizedHtml] = useState('')
  const [colorReason, setColorReason] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const debounceRef = useRef(null)

  const outputs = useAppStore((s) => s.outputs)
  const selIdx = useAppStore((s) => s.selIdx)
  const colorMode = useAppStore((s) => s.colorMode)
  const nerResult = useAppStore((s) => s.nerResult)
  const selHarmonized = useAppStore((s) => s.selHarmonized)
  const harmonizationResult = useAppStore((s) => s.harmonizationResult)

  useEffect(() => {
    if (!outputs || outputs.length === 0) {
      setColorizedHtml('')
      setColorReason(null)
      return
    }

    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setIsLoading(true)
      try {
        const params = {
          outputs,
          sel_idx: selIdx,
          mode: colorMode,
          ner_result: nerResult,
          sel_harmonized: selHarmonized,
          harmonization_result: harmonizationResult,
        }
        const data = await colorize(params)
        setColorizedHtml(data.html || '')
        setColorReason(data.reason || null)
      } catch {
        setColorizedHtml('')
        setColorReason(null)
      } finally {
        setIsLoading(false)
      }
    }, 150)

    return () => clearTimeout(debounceRef.current)
  }, [outputs, selIdx, colorMode, nerResult, selHarmonized, harmonizationResult])

  return { colorizedHtml, colorReason, isLoading }
}
