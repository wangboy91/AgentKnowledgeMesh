import { useState, useEffect, useCallback } from 'react'

interface Props {
  onResize: (width: number) => void
  minWidth?: number
  maxWidth?: number
}

export default function ResizeHandle({ onResize, minWidth = 200, maxWidth = 500 }: Props) {
  const [isDragging, setIsDragging] = useState(false)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  // Touch support for mobile/tablet
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  useEffect(() => {
    if (!isDragging) return

    function handleMouseMove(e: MouseEvent) {
      const width = Math.min(maxWidth, Math.max(minWidth, e.clientX))
      onResize(width)
    }

    function handleTouchMove(e: TouchEvent) {
      if (e.touches.length === 0) return
      const touch = e.touches[0]
      const width = Math.min(maxWidth, Math.max(minWidth, touch.clientX))
      onResize(width)
    }

    function handleMouseUp() {
      setIsDragging(false)
    }

    function handleTouchEnd() {
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('touchmove', handleTouchMove, { passive: false })
    document.addEventListener('touchend', handleTouchEnd)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('touchmove', handleTouchMove)
      document.removeEventListener('touchend', handleTouchEnd)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
  }, [isDragging, minWidth, maxWidth, onResize])

  return (
    <div
      className={`resize-handle ${isDragging ? 'is-dragging' : ''}`}
      onMouseDown={handleMouseDown}
      onTouchStart={handleTouchStart}
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize sidebar"
    />
  )
}
