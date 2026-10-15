import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { rotateImage } from '../../api/files.js'
import { DEFAULT_IMAGE_VIEW, useAppStore } from '../../store/appStore.js'
import { Button } from './Button.jsx'

// Zoom is stored relative to "fit the whole page in the frame" (zoom 1), so a
// view survives window resizes and still means the same thing.
const MIN_ZOOM = 0.25
const MAX_ZOOM = 16
const STEP = 1.25
const PAN_STEP = 60

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

// Zoom to `zoom`, keeping the point (cx, cy) -- measured from the frame
// centre -- fixed on screen.
function zoomAt(view, zoom, cx = 0, cy = 0) {
  const next = clamp(zoom, MIN_ZOOM, MAX_ZOOM)
  const ratio = next / view.zoom
  return { ...view, zoom: next, panX: cx - (cx - view.panX) * ratio, panY: cy - (cy - view.panY) * ratio }
}

/**
 * Page image with rotate / zoom / pan, for reading the page next to its
 * transcription. Scroll or +/- to zoom (toward the cursor), drag or arrow keys
 * to move, double-click to zoom in on a spot. Rotation is a view setting
 * until "Save rotation" makes it the page's stored orientation.
 */
export function ImageViewer({ root, src, height }) {
  const view = useAppStore((s) => s.imageViews[root]) ?? DEFAULT_IMAGE_VIEW
  const updateImageView = useAppStore((s) => s.updateImageView)
  const resetImageView = useAppStore((s) => s.resetImageView)
  const setError = useAppStore((s) => s.setError)
  const queryClient = useQueryClient()

  const frameRef = useRef(null)
  const drag = useRef(null)
  const [frame, setFrame] = useState({ w: 0, h: 0 })
  const [natural, setNatural] = useState(null)
  const [dragging, setDragging] = useState(false)

  const update = (fn) => updateImageView(root, fn)

  // Frame size, for computing "fit".
  useEffect(() => {
    const el = frameRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const { width, height: h } = entry.contentRect
      setFrame({ w: width, h })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const sideways = view.rotation % 180 !== 0
  const imgW = natural ? (sideways ? natural.h : natural.w) : 1
  const imgH = natural ? (sideways ? natural.w : natural.h) : 1
  const fit = natural && frame.w ? Math.min(frame.w / imgW, frame.h / imgH) * 0.98 : 1
  const scale = fit * view.zoom

  // Wheel zoom needs a non-passive listener so the page does not scroll too.
  useEffect(() => {
    const el = frameRef.current
    if (!el) return
    const onWheel = (e) => {
      e.preventDefault()
      const rect = el.getBoundingClientRect()
      const cx = e.clientX - rect.left - rect.width / 2
      const cy = e.clientY - rect.top - rect.height / 2
      const factor = Math.exp(-e.deltaY * 0.0015)
      updateImageView(root, (v) => zoomAt(v, v.zoom * factor, cx, cy))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [root, updateImageView])

  const pointFromEvent = (e) => {
    const rect = frameRef.current.getBoundingClientRect()
    return [e.clientX - rect.left - rect.width / 2, e.clientY - rect.top - rect.height / 2]
  }

  const onPointerDown = (e) => {
    if (e.button !== 0) return
    frameRef.current.setPointerCapture(e.pointerId)
    drag.current = { x: e.clientX, y: e.clientY, panX: view.panX, panY: view.panY }
    setDragging(true)
  }
  const onPointerMove = (e) => {
    if (!drag.current) return
    const d = drag.current
    update((v) => ({ ...v, panX: d.panX + e.clientX - d.x, panY: d.panY + e.clientY - d.y }))
  }
  const endDrag = () => { drag.current = null; setDragging(false) }

  const rotate = (deg) => update((v) => ({ ...v, rotation: (v.rotation + deg + 360) % 360, panX: 0, panY: 0 }))
  const zoomBy = (f) => update((v) => zoomAt(v, v.zoom * f))
  const fitPage = () => update((v) => ({ ...v, zoom: 1, panX: 0, panY: 0 }))
  const fitWidth = () => update((v) => ({ ...v, zoom: clamp((frame.w * 0.98) / imgW / fit, MIN_ZOOM, MAX_ZOOM), panX: 0, panY: 0 }))
  const actualSize = () => update((v) => zoomAt(v, 1 / fit))

  const onKeyDown = (e) => {
    const keys = {
      '+': () => zoomBy(STEP), '=': () => zoomBy(STEP), '-': () => zoomBy(1 / STEP), '0': fitPage,
      r: () => rotate(90), R: () => rotate(-90),
      ArrowLeft: () => update((v) => ({ ...v, panX: v.panX + PAN_STEP })),
      ArrowRight: () => update((v) => ({ ...v, panX: v.panX - PAN_STEP })),
      ArrowUp: () => update((v) => ({ ...v, panY: v.panY + PAN_STEP })),
      ArrowDown: () => update((v) => ({ ...v, panY: v.panY - PAN_STEP })),
    }
    if (keys[e.key]) { e.preventDefault(); keys[e.key]() }
  }

  const saveRotation = useMutation({
    mutationFn: () => rotateImage(root, view.rotation),
    onSuccess: () => {
      // The stored page is now upright: drop the view rotation and reload it
      // (here and in the Upload tab thumbnail).
      update((v) => ({ ...v, rotation: 0, panX: 0, panY: 0 }))
      setNatural(null)
      queryClient.invalidateQueries({ queryKey: ['image', root] })
    },
    onError: (err) => setError(err.message, 'Save rotation'),
  })

  const transform =
    `translate(calc(-50% + ${view.panX}px), calc(-50% + ${view.panY}px)) ` +
    `rotate(${view.rotation}deg) scale(${scale})`

  return (
    <div className="image-viewer">
      <div className="image-viewer__toolbar" role="toolbar" aria-label="Image controls">
        <Button variant="ghost" size="sm" onClick={() => rotate(-90)} title="Rotate left (Shift+R)">⟲</Button>
        <Button variant="ghost" size="sm" onClick={() => rotate(90)} title="Rotate right (R)">⟳</Button>
        <span className="image-viewer__sep" />
        <Button variant="ghost" size="sm" onClick={() => zoomBy(1 / STEP)} title="Zoom out (−)">−</Button>
        <span className="image-viewer__zoom" title="Size relative to the image's actual pixels">{Math.round(scale * 100)}%</span>
        <Button variant="ghost" size="sm" onClick={() => zoomBy(STEP)} title="Zoom in (+)">+</Button>
        <span className="image-viewer__sep" />
        <Button variant="ghost" size="sm" onClick={fitPage} title="Show the whole page (0)">Fit</Button>
        <Button variant="ghost" size="sm" onClick={fitWidth} title="Fill the frame's width">Width</Button>
        <Button variant="ghost" size="sm" onClick={actualSize} title="Actual pixels">100%</Button>
        <Button variant="ghost" size="sm" onClick={() => resetImageView(root)} title="Undo rotation and zoom">Reset</Button>
        {view.rotation !== 0 && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => saveRotation.mutate()}
            disabled={saveRotation.isPending}
            title="Store the page this way up. Thumbnails and future transcriptions use it; existing transcriptions are kept."
          >
            {saveRotation.isPending ? 'Saving…' : 'Save rotation'}
          </Button>
        )}
      </div>

      <div
        ref={frameRef}
        className={`image-viewer__frame${dragging ? ' is-dragging' : ''}`}
        style={{ height }}
        tabIndex={0}
        aria-label={`Page image ${root}. Arrow keys move, plus and minus zoom, R rotates, 0 fits.`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onDoubleClick={(e) => { const [cx, cy] = pointFromEvent(e); update((v) => zoomAt(v, v.zoom * 2, cx, cy)) }}
        onKeyDown={onKeyDown}
      >
        <img
          src={src}
          alt={root}
          draggable={false}
          onLoad={(e) => setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })}
          style={{
            width: natural?.w ?? 'auto',
            height: natural?.h ?? 'auto',
            transform,
            visibility: natural ? 'visible' : 'hidden',
          }}
        />
      </div>
      <div className="image-viewer__hint">Scroll to zoom · drag to move · double-click to zoom in</div>
    </div>
  )
}
