export function StartTab() {
  return (
    <div className="section">
      <div className="card section">
        <h2 style={{ marginBottom: 'var(--space-2)' }}>📝 Transkrybe.ai</h2>
        <p style={{ color: 'var(--color-text-muted)', lineHeight: 1.7 }}>
          Transcribe handwritten documents using AI vision models (OpenAI, Google Gemini, and Anthropic Claude).
          Run multiple transcriptions, compare them with colorized difference highlighting, and merge
          them into a consensus transcription.
        </p>
      </div>

      <div className="section-title">Workflow</div>

      <div className="section">
        <details className="expander" open>
          <summary>🔑 API Key Setup</summary>
          <div className="expander-content">
            <p><strong>Google Gemini (recommended)</strong> — Get a free API key at <strong>aistudio.google.com</strong>. Gemini supports transcription, harmonization, and Named Entity Recognition (NER).</p>
            <p><strong>OpenAI</strong> — Get an API key at <strong>platform.openai.com</strong>. Supports transcription and harmonization.</p>
            <p>Enter keys in the <strong>Transcription</strong> tab. They are stored in your browser session only and never sent anywhere except the respective AI APIs.</p>
          </div>
        </details>

        <details className="expander">
          <summary>📤 1. Upload</summary>
          <div className="expander-content">
            <p>Drag and drop image files (JPG, PNG, TIFF, etc.) onto the upload zone, or click to browse. You can also upload JSON transcription files from previous sessions to resume work.</p>
            <p>After uploading, the thumbnails appear in the grid. Click any thumbnail to make it the active document — the image preview and all transcription results update to match.</p>
          </div>
        </details>

        <details className="expander">
          <summary>📝 2. Transcription</summary>
          <div className="expander-content">
            <p>The Transcription tab handles both running transcriptions and harmonizing them:</p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.8 }}>
              <li>Select a <strong>transcription profile</strong> (or clone a template to customize prompts for your document type)</li>
              <li>Enter your <strong>API key</strong> and choose a <strong>model</strong></li>
              <li>Optionally add <strong>domain knowledge</strong> — context about the document that improves accuracy (e.g. names, dates, subject matter)</li>
              <li>Set the number of runs and click <strong>⚡ Transcribe</strong></li>
              <li>Running <strong>3–5 transcriptions</strong> gives significantly better harmonization results</li>
            </ul>
            <p style={{ marginTop: 'var(--space-2)' }}>
              Once you have multiple transcriptions, select 2 or more and click <strong>🤝 Harmonize</strong>.
              The AI merges them into a single consensus transcription, resolving disagreements intelligently.
            </p>
          </div>
        </details>

        <details className="expander">
          <summary>🔬 3. Analysis</summary>
          <div className="expander-content">
            <p>The Analysis tab shows the image alongside any transcription with color-coded disagreement highlighting:</p>
            <ul style={{ paddingLeft: 20, lineHeight: 1.8 }}>
              <li><strong>Word-level:</strong> Colors words by how much transcriptions disagree — green = full agreement, red = no agreement</li>
              <li><strong>Char-level:</strong> Same highlighting at the character level for fine-grained analysis</li>
              <li><strong>Named Entities:</strong> Highlights people, places, organizations, and dates (requires NER to be enabled)</li>
            </ul>
            <p>Click <strong>✏️ Edit</strong> to manually correct any transcription before harmonizing.</p>
          </div>
        </details>

        <details className="expander">
          <summary>📦 4. Export</summary>
          <div className="expander-content">
            <p>Download your transcription data as <strong>JSON</strong> (full session data, re-importable) or a <strong>ZIP archive</strong> of plain text files.</p>
          </div>
        </details>
      </div>

      <div className="section-title">Reference</div>

      <div className="two-col">
        <div className="card">
          <div className="section-title">🗂️ Transcription Profiles</div>
          <p style={{ lineHeight: 1.7 }}>
            Profiles control the AI prompts used for transcription and harmonization.
            <strong> Template profiles</strong> (marked read-only) provide curated starting points —
            clone them to create customized versions for your specific documents.
          </p>
          <p style={{ lineHeight: 1.7, marginTop: 'var(--space-2)' }}>
            Available templates: <strong>Civil War HTR</strong> (historical letters and documents)
            and <strong>Scientific Tables HTR</strong> (structured tabular data).
          </p>
        </div>

        <div className="card">
          <div className="section-title">💡 Tips for Better Results</div>
          <ul style={{ paddingLeft: 20, lineHeight: 1.9 }}>
            <li>Use <strong>Gemini 3.1 Pro</strong> or <strong>GPT-5</strong> for best accuracy</li>
            <li>Run <strong>3–5 transcriptions</strong> before harmonizing</li>
            <li>Add domain knowledge — names, dates, subject matter</li>
            <li>Use NER to identify and verify proper nouns</li>
            <li>Manually edit obvious errors before harmonizing</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
