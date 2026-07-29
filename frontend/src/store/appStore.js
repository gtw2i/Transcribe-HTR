import { create } from 'zustand'

export const useAppStore = create((set, get) => ({
  // ── Session ──
  sessionId: null,
  sessionReady: false,
  setSessionId: (id) => set({ sessionId: id, sessionReady: true }),
  setSessionExpired: () => set({
    sessionReady: false,
    errorBanner: { message: 'Your session has expired. Refresh the page to continue.', context: 'Session' },
  }),

  // ── Navigation ──
  activeTab: 'start',
  setActiveTab: (tab) => set({ activeTab: tab }),

  // ── File management ──
  activeRoot: '',
  setActiveRoot: (root) => set({
    activeRoot: root,
    // Clear transcription state when switching files
    outputs: [],
    tokensUsage: null,
    lastCompletionSummary: null,
    selIdx: 0,
    nerResult: null,
    nerError: null,
    summaryResult: null,
    harmonizationSelected: [],
    harmonizationResult: null,
    selHarmonized: false,
    analysisEditMode: false,
    analysisEditText: '',
    transcriptionBatch: null,
  }),
  setActiveRootOnly: (root) => set({ activeRoot: root }),

  // ── Image (loaded reactively by useImage hook) ──
  imageB64: null,
  imageMime: 'image/png',
  setImage: (b64, mime = 'image/png') => set({ imageB64: b64, imageMime: mime }),

  // ── Transcription results ──
  outputs: [],
  tokensUsage: null,
  lastCompletionSummary: null,
  transcriptionFallbackNotices: [],
  selIdx: 0,
  colorMode: 'Word-level',
  textFontSize: 100,
  analysisEditMode: false,
  analysisEditText: '',

  setTranscriptionResults: (outputs, tokensUsage, summary, fallbackNotices = []) => set({
    outputs,
    tokensUsage,
    lastCompletionSummary: summary,
    transcriptionFallbackNotices: fallbackNotices,
    selIdx: 0,
    nerResult: null,
    nerError: null,
    selHarmonized: false,
  }),
  setSelIdx: (idx) => set({ selIdx: idx }),
  setColorMode: (mode) => set({ colorMode: mode }),
  setTextFontSize: (size) => set({ textFontSize: size }),
  setAnalysisEditMode: (mode, text) => set({ analysisEditMode: mode, analysisEditText: text ?? '' }),
  updateOutputText: (idx, text) => set((state) => {
    const outputs = [...state.outputs]
    outputs[idx] = { ...outputs[idx], text }
    return { outputs, analysisEditMode: false }
  }),

  // ── Settings ──
  selectedProvider: 'Gemini',
  selectedModel: 'gemini-3.1-pro-preview',
  openaiApiKey: '',
  geminiApiKey: '',
  anthropicApiKey: '',
  nResponses: 2,
  nerEnabled: true,
  domainKnowledge: '',
  activeProfile: 'default_htr',
  modelLists: {},

  setProvider: (provider) => set({ selectedProvider: provider, selectedModel: '' }),
  setModel: (model) => set({ selectedModel: model }),
  setOpenaiApiKey: (key) => set({ openaiApiKey: key }),
  setGeminiApiKey: (key) => set({ geminiApiKey: key }),
  setAnthropicApiKey: (key) => set({ anthropicApiKey: key }),
  setNResponses: (n) => set({ nResponses: n }),
  setNerEnabled: (enabled) => set({ nerEnabled: enabled }),
  setDomainKnowledge: (text) => set({ domainKnowledge: text }),
  setActiveProfile: (profile) => set({ activeProfile: profile }),
  setModelList: (provider, models) => set((state) => ({
    modelLists: { ...state.modelLists, [provider]: models },
  })),

  // ── Harmonization ──
  harmonizationSelected: [],
  harmonizationResult: null,
  harmonizationProcessing: false,
  harmonizationProvider: 'Gemini',
  harmonizationModel: '',
  harmonizationApiKey: '',
  selHarmonized: false,
  autoHarmonize: true,

  setHarmonizationSelected: (selected) => set({ harmonizationSelected: selected }),
  setHarmonizationResult: (result) => set({ harmonizationResult: result, selHarmonized: true }),
  setAutoHarmonize: (v) => set({ autoHarmonize: v }),
  clearHarmonizationResult: () => set({ harmonizationResult: null, selHarmonized: false }),
  setHarmonizationProvider: (p) => set({ harmonizationProvider: p, harmonizationModel: '' }),
  setHarmonizationModel: (m) => set({ harmonizationModel: m }),
  setHarmonizationApiKey: (k) => set({ harmonizationApiKey: k }),
  setSelHarmonized: (v) => set({ selHarmonized: v }),

  // ── NER ──
  nerResult: null,
  nerError: null,
  nerEntityTypes: ['person', 'organization', 'place', 'date', 'other'],
  setNerResult: (result) => set({ nerResult: result, nerError: null }),
  setNerError: (err) => set({ nerError: err }),
  setNerEntityTypes: (types) => set({ nerEntityTypes: types }),

  // ── Summarization ──
  summaryResult: null,
  autoSummarize: true,
  setSummaryResult: (result) => set({ summaryResult: result }),
  setAutoSummarize: (v) => set({ autoSummarize: v }),

  // ── Transcription batch progress (global → persists across tab switches) ──
  // null = idle; { targets, currentRoot, completed, errors, nerRunning } = active or done
  transcriptionBatch: null,
  setTranscriptionBatch: (patchOrFn) => set((state) => ({
    transcriptionBatch: typeof patchOrFn === 'function'
      ? patchOrFn(state.transcriptionBatch)
      : patchOrFn,
  })),
  clearTranscriptionBatch: () => set({ transcriptionBatch: null }),

  // ── TTS (verbalize) ──
  verbalize: {
    ttsModel: 'tts-1',
    voice: 'onyx',
    openaiApiKey: '',
    editedTranscript: '',
    audioCacheB64: null,
    audioMetadata: null,
    fromCache: false,
    generationStatus: 'ready',
    errorMessage: '',
  },
  setVerbalize: (patch) => set((state) => ({
    verbalize: { ...state.verbalize, ...patch },
  })),

  // ── Consistency analysis ──
  // User intent only. The reports themselves are React Query cache entries
  // (D8), keyed by the request that produced them.
  consistency: {
    selectedIds: null,          // null = "not yet touched", use the server default
    normProfile: 'standard_historical',
    tokenizer: 'word_simple',
    consensusKind: 'deterministic',
    focusAttemptId: null,       // drives linked highlighting across views (§19)
    sortKey: 'medianCer',
    scaleMode: 'robust',        // 'robust' | 'linear' heat-map colour domain
    matrixMode: 'symmetric',    // 'symmetric' | 'directional'
    diffA: null,
    diffB: null,
    hasRun: false,              // the analysis is explicit, not automatic
    inspectId: null,            // attempt whose full text is open
  },
  setConsistency: (patch) => set((state) => ({
    consistency: { ...state.consistency, ...patch },
  })),
  resetConsistency: () => set((state) => ({
    consistency: {
      ...state.consistency,
      selectedIds: null,
      focusAttemptId: null,
      diffA: null,
      diffB: null,
      hasRun: false,
      inspectId: null,
    },
  })),
  toggleConsistencyAttempt: (attemptId, allDefault) => set((state) => {
    const current = state.consistency.selectedIds ?? allDefault ?? []
    const next = current.includes(attemptId)
      ? current.filter((id) => id !== attemptId)
      : [...current, attemptId]
    return { consistency: { ...state.consistency, selectedIds: next } }
  }),

  // ── UI state ──
  errorBanner: null,
  profileEditorOpen: false,
  profileEditorMode: 'clone',
  profileEditorSource: 'default_htr',
  gettingStartedOpen: false,

  setError: (message, context = '') => set({ errorBanner: { message, context } }),
  clearError: () => set({ errorBanner: null }),
  openProfileEditor: (mode, source) => set({
    profileEditorOpen: true,
    profileEditorMode: mode,
    profileEditorSource: source,
  }),
  closeProfileEditor: () => set({ profileEditorOpen: false }),
  setGettingStartedOpen: (open) => set({ gettingStartedOpen: open }),

  // ── Derived helpers ──
  getActiveApiKey: () => {
    const { selectedProvider, openaiApiKey, geminiApiKey, anthropicApiKey } = get()
    if (selectedProvider === 'OpenAI') return openaiApiKey
    if (selectedProvider === 'Anthropic') return anthropicApiKey
    return geminiApiKey
  },
  getHarmonizationApiKey: () => {
    const { harmonizationProvider, openaiApiKey, geminiApiKey, anthropicApiKey, harmonizationApiKey } = get()
    if (harmonizationApiKey) return harmonizationApiKey
    if (harmonizationProvider === 'OpenAI') return openaiApiKey
    if (harmonizationProvider === 'Anthropic') return anthropicApiKey
    return geminiApiKey
  },
}))
