import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useSession } from './hooks/useSession.js'
import { useAppStore } from './store/appStore.js'
import { AppHeader } from './components/layout/AppHeader.jsx'
import { TabBar } from './components/layout/TabBar.jsx'
import { ErrorBanner } from './components/layout/ErrorBanner.jsx'
import { UploadTab } from './components/upload/UploadTab.jsx'
import { TranscriptionTab } from './components/transcription/TranscriptionTab.jsx'
import { AnalysisTab } from './components/analysis/AnalysisTab.jsx'
import { ConsistencyTab } from './components/consistency/ConsistencyTab.jsx'
import { ExportTab } from './components/export/ExportTab.jsx'
import { StartTab } from './components/help/StartTab.jsx'
import { GettingStartedModal } from './components/modals/GettingStartedModal.jsx'
import { ProfileEditorModal } from './components/modals/ProfileEditorModal.jsx'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function AppContent() {
  useSession()

  const activeTab = useAppStore((s) => s.activeTab)
  const gettingStartedOpen = useAppStore((s) => s.gettingStartedOpen)
  const profileEditorOpen = useAppStore((s) => s.profileEditorOpen)

  return (
    <div id="app">
      <div className="top-nav">
        <AppHeader />
      </div>
      <ErrorBanner />
      <div className="app-body">
        <TabBar />
        <main className="tab-content">
          {activeTab === 'upload' && <UploadTab />}
          {activeTab === 'transcription' && <TranscriptionTab />}
          {activeTab === 'analysis' && <AnalysisTab />}
          {activeTab === 'consistency' && <ConsistencyTab />}
          {activeTab === 'export' && <ExportTab />}
          {activeTab === 'start' && <StartTab />}
        </main>
      </div>
      {gettingStartedOpen && <GettingStartedModal />}
      {profileEditorOpen && <ProfileEditorModal />}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  )
}
