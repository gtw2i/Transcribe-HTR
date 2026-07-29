import { Alert } from './Alert.jsx'

export function FallbackNotice({ fallbackInfo }) {
  if (!fallbackInfo) return null
  const { requested_model, used_model } = fallbackInfo
  return (
    <Alert type="warning">
      The requested model ({requested_model}) was unavailable — used {used_model} instead.
    </Alert>
  )
}
