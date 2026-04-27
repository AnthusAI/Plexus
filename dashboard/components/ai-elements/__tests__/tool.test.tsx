import * as React from 'react'
import { render, screen } from '@testing-library/react'

import { Tool, ToolHeader, ToolContent, ToolInput, ToolOutput } from '../tool'

describe('ai-elements Tool styling', () => {
  test('tool container and content use flat-shaded surfaces without border classes', () => {
    const { container } = render(
      <Tool defaultOpen>
        <ToolHeader toolType="tool-plexus_evaluation_run" state="output-available" toolName="plexus_evaluation_run" />
        <ToolContent>
          <ToolInput input={{ evaluation_id: 'eval-123' }} />
          <ToolOutput output={<div>ok</div>} />
        </ToolContent>
      </Tool>
    )

    const root = container.firstElementChild as HTMLElement
    expect(root).toBeTruthy()
    expect(root.className).not.toContain('border')

    const outputLabel = screen.getByText('Output')
    expect(outputLabel).toBeInTheDocument()
    const outputRegion = outputLabel.parentElement as HTMLElement
    expect(outputRegion.className).not.toContain('border')
  })

  test('error output styling does not rely on border outlines', () => {
    render(
      <ToolOutput errorText="Failed" output={null} />
    )

    const failed = screen.getByText('Failed')
    expect(failed.className).not.toContain('border')
  })
})
