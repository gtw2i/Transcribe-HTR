import { useAppStore } from '../../store/appStore.js'

const TABS = [
  { id: 'start', label: '🚀 Start' },
  { id: 'upload', label: '📤 Upload' },
  { id: 'transcription', label: '📝 Transcription' },
  { id: 'analysis', label: '🔬 Analysis' },
  { id: 'consistency', label: '📊 Consistency' },
  { id: 'export', label: '📦 Export' },
]

export function TabBar() {
  const activeTab = useAppStore((s) => s.activeTab)
  const setActiveTab = useAppStore((s) => s.setActiveTab)

  return (
    <nav className="tab-bar">
      <div className="tab-bar-inner">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn${activeTab === tab.id ? ' active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </nav>
  )
}
