import React from 'react'
import { render, screen } from '@testing-library/react'
import { SegmentedProgressBar, SegmentConfig } from './segmented-progress-bar'

describe('SegmentedProgressBar', () => {
  const mockSegments: SegmentConfig[] = [
    { key: 'setup', label: 'Setup', color: 'bg-primary' },
    { key: 'processing', label: 'Processing', color: 'bg-secondary' },
    { key: 'finalizing', label: 'Finalizing', color: 'bg-true' }
  ]

  describe('Current segment styling', () => {
    it('applies bold font and text-foreground to current segment', () => {
      render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="processing"
        />
      )

      const processingSegment = screen.getByText('Processing')
      expect(processingSegment).toHaveClass('font-bold')
      expect(processingSegment).toHaveClass('text-foreground')
    })

    it('applies font-medium and text-muted-foreground to non-current segments', () => {
      render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="processing"
        />
      )

      const setupSegment = screen.getByText('Setup')
      const finalizingSegment = screen.getByText('Finalizing')

      // Previous segment (before current)
      expect(setupSegment).toHaveClass('font-medium')
      expect(setupSegment).toHaveClass('text-muted-foreground')

      // Future segment (after current)
      expect(finalizingSegment).toHaveClass('font-medium')
      expect(finalizingSegment).toHaveClass('text-muted-foreground')
    })

    it('applies correct styling when current segment is first', () => {
      render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="setup"
        />
      )

      const setupSegment = screen.getByText('Setup')
      const processingSegment = screen.getByText('Processing')
      const finalizingSegment = screen.getByText('Finalizing')

      // Current (first)
      expect(setupSegment).toHaveClass('font-bold')
      expect(setupSegment).toHaveClass('text-foreground')

      // Future segments
      expect(processingSegment).toHaveClass('font-medium')
      expect(processingSegment).toHaveClass('text-muted-foreground')
      expect(finalizingSegment).toHaveClass('font-medium')
      expect(finalizingSegment).toHaveClass('text-muted-foreground')
    })

    it('applies correct styling when current segment is last', () => {
      render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="finalizing"
        />
      )

      const setupSegment = screen.getByText('Setup')
      const processingSegment = screen.getByText('Processing')
      const finalizingSegment = screen.getByText('Finalizing')

      // Previous segments
      expect(setupSegment).toHaveClass('font-medium')
      expect(setupSegment).toHaveClass('text-muted-foreground')
      expect(processingSegment).toHaveClass('font-medium')
      expect(processingSegment).toHaveClass('text-muted-foreground')

      // Current (last)
      expect(finalizingSegment).toHaveClass('font-bold')
      expect(finalizingSegment).toHaveClass('text-foreground')
    })
  })

  describe('Completed segments styling', () => {
    it('applies muted styling to completed segments that are not current', () => {
      const segmentsWithCompleted: SegmentConfig[] = [
        { key: 'setup', label: 'Setup', color: 'bg-primary', completed: true },
        { key: 'processing', label: 'Processing', color: 'bg-secondary' },
        { key: 'finalizing', label: 'Finalizing', color: 'bg-true' }
      ]

      render(
        <SegmentedProgressBar
          segments={segmentsWithCompleted}
          currentSegment="processing"
        />
      )

      const setupSegment = screen.getByText('Setup')
      const processingSegment = screen.getByText('Processing')

      // Completed but not current - should be muted
      expect(setupSegment).toHaveClass('font-medium')
      expect(setupSegment).toHaveClass('text-muted-foreground')

      // Current segment - should be bold
      expect(processingSegment).toHaveClass('font-bold')
      expect(processingSegment).toHaveClass('text-foreground')
    })

    it('applies bold styling to completed segment if it is current', () => {
      const segmentsWithCompleted: SegmentConfig[] = [
        { key: 'setup', label: 'Setup', color: 'bg-primary', completed: true },
        { key: 'processing', label: 'Processing', color: 'bg-secondary', completed: true },
        { key: 'finalizing', label: 'Finalizing', color: 'bg-true' }
      ]

      render(
        <SegmentedProgressBar
          segments={segmentsWithCompleted}
          currentSegment="processing"
        />
      )

      const processingSegment = screen.getByText('Processing')

      // Completed AND current - should be bold
      expect(processingSegment).toHaveClass('font-bold')
      expect(processingSegment).toHaveClass('text-foreground')
    })
  })

  describe('Error state styling', () => {
    it('applies bold and foreground styling to current segment in error state', () => {
      render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="processing"
          error={true}
          errorLabel="Failed"
        />
      )

      const errorSegment = screen.getByText('Failed')

      // Current segment in error should still be bold
      expect(errorSegment).toHaveClass('font-bold')
      expect(errorSegment).toHaveClass('text-foreground')
    })

    it('displays error label for current segment when error is true', () => {
      render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="processing"
          error={true}
          errorLabel="Error"
        />
      )

      expect(screen.getByText('Error')).toBeInTheDocument()
      expect(screen.queryByText('Processing')).not.toBeInTheDocument()
    })
  })

  describe('Status-based styling', () => {
    it('applies muted styling to RUNNING segment that is not current', () => {
      const segmentsWithStatus: SegmentConfig[] = [
        { key: 'setup', label: 'Setup', color: 'bg-primary', status: 'RUNNING' },
        { key: 'processing', label: 'Processing', color: 'bg-secondary' },
        { key: 'finalizing', label: 'Finalizing', color: 'bg-true' }
      ]

      render(
        <SegmentedProgressBar
          segments={segmentsWithStatus}
          currentSegment="processing"
        />
      )

      const setupSegment = screen.getByText('Setup')

      // RUNNING but not current - should be muted
      expect(setupSegment).toHaveClass('font-medium')
      expect(setupSegment).toHaveClass('text-muted-foreground')
    })

    it('applies bold styling to COMPLETED segment if it is current', () => {
      const segmentsWithStatus: SegmentConfig[] = [
        { key: 'setup', label: 'Setup', color: 'bg-primary', status: 'COMPLETED' },
        { key: 'processing', label: 'Processing', color: 'bg-secondary', status: 'COMPLETED' },
        { key: 'finalizing', label: 'Finalizing', color: 'bg-true' }
      ]

      render(
        <SegmentedProgressBar
          segments={segmentsWithStatus}
          currentSegment="processing"
        />
      )

      const processingSegment = screen.getByText('Processing')

      // COMPLETED AND current - should be bold
      expect(processingSegment).toHaveClass('font-bold')
      expect(processingSegment).toHaveClass('text-foreground')
    })
  })

  describe('Case insensitivity', () => {
    it('correctly identifies current segment with case-insensitive matching', () => {
      render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="PROCESSING"
        />
      )

      const processingSegment = screen.getByText('Processing')
      expect(processingSegment).toHaveClass('font-bold')
      expect(processingSegment).toHaveClass('text-foreground')
    })
  })

  describe('Rendering', () => {
    it('renders all segments', () => {
      render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="processing"
        />
      )

      expect(screen.getByText('Setup')).toBeInTheDocument()
      expect(screen.getByText('Processing')).toBeInTheDocument()
      expect(screen.getByText('Finalizing')).toBeInTheDocument()
    })

    it('applies custom className to container', () => {
      const { container } = render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="processing"
          className="custom-class"
        />
      )

      const progressBar = container.firstChild as HTMLElement
      expect(progressBar).toHaveClass('custom-class')
    })
  })

  describe('Selection state', () => {
    it('applies selected background when isSelected is true', () => {
      const { container } = render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="processing"
          isSelected={true}
        />
      )

      const progressBar = container.firstChild as HTMLElement
      expect(progressBar).toHaveClass('bg-progress-background-selected')
    })

    it('applies normal background when isSelected is false', () => {
      const { container } = render(
        <SegmentedProgressBar
          segments={mockSegments}
          currentSegment="processing"
          isSelected={false}
        />
      )

      const progressBar = container.firstChild as HTMLElement
      expect(progressBar).toHaveClass('bg-progress-background')
    })
  })
})

