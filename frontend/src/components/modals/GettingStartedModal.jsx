import { useAppStore } from '../../store/appStore.js'
import { Modal } from '../shared/Modal.jsx'
import { Button } from '../shared/Button.jsx'

export function GettingStartedModal() {
  const setGettingStartedOpen = useAppStore((s) => s.setGettingStartedOpen)
  const close = () => setGettingStartedOpen(false)

  return (
    <Modal
      title="❓ Getting Started"
      onClose={close}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={() => window.print()}>🖨️ Print</Button>
          <Button variant="primary" onClick={close}>Close</Button>
        </>
      }
    >
      <div style={{ lineHeight: 1.7 }}>
        <h3 style={{ marginBottom: 'var(--space-2)' }}>Overview</h3>
        <p>
          This app transcribes handwritten documents using AI vision models (OpenAI GPT-5 and Google Gemini).
          Run multiple transcriptions, compare them with colorized difference highlighting, and merge them
          into a consensus transcription.
        </p>

        <details className="expander" style={{ marginTop: 'var(--space-3)' }}>
          <summary>🔑 API Key Setup</summary>
          <div className="expander-content">
            <h4>Google Gemini (recommended)</h4>
            <p>Get a free API key at <strong>aistudio.google.com</strong>. Gemini also supports Named Entity Recognition (NER).</p>
            <h4>OpenAI</h4>
            <p>Get an API key at <strong>platform.openai.com</strong>. Supports transcription with GPT-5 models.</p>
            <p>Enter keys in the Transcription tab — they are stored in your browser session only and never sent anywhere except the AI APIs.</p>
          </div>
        </details>

        <details className="expander">
          <summary>📤 1. Upload</summary>
          <div className="expander-content">
            <p>Drag and drop image files (JPG, PNG) onto the upload zone, or click to browse. You can also upload JSON transcription files from previous sessions or audio files (WAV, MP3) to pair with images.</p>
            <p>After uploading, select the active document from the dropdown. The image preview will appear below.</p>
          </div>
        </details>

        <details className="expander">
          <summary>📝 2. Transcribe</summary>
          <div className="expander-content">
            <p>Select a transcription profile (or clone one to customize), enter your API key, choose a model, and click <strong>⚡ Transcribe</strong>. Running 3–5 transcriptions gives better harmonization results.</p>
            <p>Domain knowledge (optional) lets you provide context about the document to improve accuracy.</p>
          </div>
        </details>

        <details className="expander">
          <summary>🔬 3. Analyze</summary>
          <div className="expander-content">
            <p>The Analysis tab shows the image alongside any transcription with color-coded disagreement highlighting:</p>
            <ul style={{ paddingLeft: 20 }}>
              <li><strong>Word-level:</strong> Colors words by how much transcriptions disagree (green = full agreement, red = no agreement)</li>
              <li><strong>Char-level:</strong> Same but at the character level for fine-grained analysis</li>
              <li><strong>Named Entities:</strong> Highlights people, places, organizations, and dates (requires NER)</li>
            </ul>
            <p>Click <strong>✏️ Edit</strong> to manually correct a transcription.</p>
          </div>
        </details>

        <details className="expander">
          <summary>🎯 4. Harmonize</summary>
          <div className="expander-content">
            <p>Select 2 or more transcriptions and click <strong>🤝 Harmonize</strong>. The AI will combine them into a single consensus transcription, resolving disagreements intelligently.</p>
          </div>
        </details>

        <details className="expander">
          <summary>📦 5. Export</summary>
          <div className="expander-content">
            <p>Download the transcription data as JSON or a ZIP archive containing text files.</p>
          </div>
        </details>

        <details className="expander">
          <summary>🗂️ Transcription Profiles</summary>
          <div className="expander-content">
            <p>Profiles control the AI prompts used for transcription and harmonization. Template profiles (marked read-only) provide starting points — clone them to create customized versions for your specific documents.</p>
            <p>Available templates: <strong>Civil War HTR</strong> (historical letters/documents) and <strong>Scientific Tables HTR</strong> (structured data).</p>
          </div>
        </details>

        <details className="expander">
          <summary>💡 Tips for Better Results</summary>
          <div className="expander-content">
            <ul style={{ paddingLeft: 20 }}>
              <li>Use <strong>Gemini 3.1 Pro</strong> or <strong>GPT-5</strong> for best accuracy</li>
              <li>Run 3–5 transcriptions before harmonizing</li>
              <li>Add domain knowledge (e.g., "19th century military correspondence, names include Col. Smith and Sgt. Jones")</li>
              <li>Use NER to identify and verify proper nouns</li>
              <li>Manually edit any obvious errors before harmonizing</li>
            </ul>
          </div>
        </details>
      </div>
    </Modal>
  )
}
