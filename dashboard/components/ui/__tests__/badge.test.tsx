import React from 'react'
import { render, screen } from '@testing-library/react'
import { Badge } from '@/components/ui/badge'

describe('Badge', () => {
  test('pill variant is borderless and uses theme-correct neutral base', () => {
    render(<Badge variant="pill">Pill</Badge>)
    const el = screen.getByText('Pill')
    expect(el.className).toContain('border-0')
    expect(el.className).toContain('bg-muted/50')
    expect(el.className).toContain('text-muted-foreground')
  })
})

