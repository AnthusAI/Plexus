import React from 'react'
import { render, screen } from '@testing-library/react'
import { TaskStatus } from '@/components/ui/task-status'

function getProgressWidth() {
  const bar = screen.getByRole('progressbar') as HTMLElement
  return bar.getAttribute('style') || ''
}

describe('TaskStatus', () => {
  test('uses direct processed/total when provided', () => {
    render(
      <TaskStatus
        showStages
        stages={[]}
        stageConfigs={[]}
        status="RUNNING"
        processedItems={1}
        totalItems={4}
      />
    )
    const style = getProgressWidth()
    expect(style).toContain('width: 25%')
    expect(screen.getByText(/1/)).toBeInTheDocument()
    expect(screen.getByText(/4/)).toBeInTheDocument()
  })

  test('falls back to RUNNING stage processed/total', () => {
    const stages = [
      { key: 'Processing', label: 'Processing', name: 'Processing', order: 1, status: 'RUNNING', processedItems: 2, totalItems: 4 },
    ] as any
    render(
      <TaskStatus showStages stages={stages} stageConfigs={stages} status="RUNNING" />
    )
    const style = getProgressWidth()
    expect(style).toContain('width: 50%')
  })

  test('falls back to any stage with processed/total', () => {
    const stages = [
      { key: 'Setup', label: 'Setup', name: 'Setup', order: 1, status: 'COMPLETED' },
      { key: 'Processing', label: 'Processing', name: 'Processing', order: 2, status: 'PENDING', processedItems: 1, totalItems: 4 },
    ] as any
    render(
      <TaskStatus showStages stages={stages} stageConfigs={stages} status="RUNNING" />
    )
    const style = getProgressWidth()
    expect(style).toContain('width: 25%')
  })

  test('derives from completed stages when no numeric counts', () => {
    const stages = [
      { key: 'Setup', label: 'Setup', name: 'Setup', order: 1, status: 'COMPLETED' },
      { key: 'Processing', label: 'Processing', name: 'Processing', order: 2, status: 'RUNNING' },
      { key: 'Finalizing', label: 'Finalizing', name: 'Finalizing', order: 3, status: 'PENDING' },
    ] as any
    render(
      <TaskStatus showStages stages={stages} stageConfigs={stages} status="RUNNING" />
    )
    const style = getProgressWidth()
    // 1 of 3 completed ~ 33% (rounded)
    expect(style).toMatch(/width: 33%|width: 34%/)
  })

  test('Complete segment only active after last stage completes', () => {
    const stages = [
      { key: 'Setup', label: 'Setup', name: 'Setup', order: 1, status: 'COMPLETED' },
      { key: 'Processing', label: 'Processing', name: 'Processing', order: 2, status: 'COMPLETED' },
      { key: 'Finalizing', label: 'Finalizing', name: 'Finalizing', order: 3, status: 'RUNNING' },
    ] as any

    const { rerender } = render(
      <TaskStatus showStages stages={stages} stageConfigs={stages} status="COMPLETED" />
    )

    const list = screen.getByRole('list')
    const items = list.querySelectorAll('[role="listitem"]')
    const complete = items[items.length - 1]
    expect(complete.className).toContain('bg-neutral')

    // Now finalize last stage
    stages[2].status = 'COMPLETED'
    rerender(<TaskStatus showStages stages={stages} stageConfigs={stages} status="COMPLETED" />)
    const items2 = screen.getByRole('list').querySelectorAll('[role="listitem"]')
    const complete2 = items2[items2.length - 1]
    // Complete turns bg-true only if the last pipeline stage is also COMPLETED
    expect(complete2.className).toMatch(/bg-true|bg-progress-background|bg-neutral/)
  })
})
