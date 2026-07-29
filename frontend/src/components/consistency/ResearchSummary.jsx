import { useState } from 'react'
import { Button } from '../shared/Button.jsx'
import { Expander } from '../shared/Expander.jsx'

/**
 * Concise summary for a research record (§30), plus the provenance needed to
 * reproduce the analysis (§25).
 */
export function ResearchSummary({ report }) {
  const [copied, setCopied] = useState(false)
  const settings = report.settings

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report.narrative)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section className="consistency-section">
      <h3>10. Research summary</h3>
      <p>{report.narrative}</p>

      <Button size="sm" onClick={copy}>
        {copied ? 'Copied' : 'Copy summary'}
      </Button>

      <Expander title="Analysis settings and definitions" className="mt-2">
        <table className="consistency-table">
          <tbody>
            <tr>
              <td>Normalization profile</td>
              <td style={{ textAlign: 'left' }}>
                {settings.normalization.label} (v{settings.normalization.version})
              </td>
            </tr>
            <tr>
              <td>Normalization steps</td>
              <td style={{ textAlign: 'left' }}>{settings.normalization.steps.join(' → ')}</td>
            </tr>
            <tr>
              <td>Word tokenization</td>
              <td style={{ textAlign: 'left' }}>{settings.tokenizer.id}</td>
            </tr>
            <tr>
              <td>CER</td>
              <td style={{ textAlign: 'left' }}>{settings.cer_definition}</td>
            </tr>
            <tr>
              <td>WER</td>
              <td style={{ textAlign: 'left' }}>{settings.wer_definition}</td>
            </tr>
            <tr>
              <td>Symmetric disagreement</td>
              <td style={{ textAlign: 'left' }}>{settings.symmetric_definition}</td>
            </tr>
            <tr>
              <td>Uncertainty</td>
              <td style={{ textAlign: 'left' }}>{settings.uncertainty_method}</td>
            </tr>
            <tr>
              <td>Edit-distance backend</td>
              <td style={{ textAlign: 'left' }}>{settings.backend}</td>
            </tr>
            <tr>
              <td>Analysis version</td>
              <td style={{ textAlign: 'left' }}>{report.analysis_version}</td>
            </tr>
          </tbody>
        </table>
      </Expander>
    </section>
  )
}
