import React from 'react'
import { render, screen } from '@testing-library/react'
import { UseCases } from '../UseCases'

describe('UseCases Component', () => {
  it('renders the main heading', () => {
    render(<UseCases />)
    expect(screen.getByText('Your team knows your business')).toBeInTheDocument()
  })

  it('renders all use case cards', () => {
    render(<UseCases />)
    
    expect(screen.getByText('Mailbox folders')).toBeInTheDocument()
    expect(screen.getByText('Use our UI')).toBeInTheDocument()
    expect(screen.getByText('Custom integrations')).toBeInTheDocument()
    expect(screen.getByText('Feedback loops')).toBeInTheDocument()
    
    expect(screen.getByText(/Train custom email classifiers/)).toBeInTheDocument()
    expect(screen.getByText(/Label items directly in the Plexus dashboard/)).toBeInTheDocument()
    expect(screen.getByText(/We can incorporate labels from any data source/)).toBeInTheDocument()
    expect(screen.getByText(/Review and correct agent decisions/)).toBeInTheDocument()
  })

  it('renders use case icons', () => {
    render(<UseCases />)
    const icons = document.querySelectorAll('.text-accent')
    expect(icons).toHaveLength(4)
  })
}) 