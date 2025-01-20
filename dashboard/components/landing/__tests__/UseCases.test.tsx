import React from 'react'
import { render, screen } from '@testing-library/react'
import { UseCases } from '../UseCases'

describe('UseCases Component', () => {
  it('renders the main heading', () => {
    render(<UseCases />)
    expect(screen.getByText('Real-World Applications')).toBeInTheDocument()
  })

  it('renders all use case cards', () => {
    render(<UseCases />)
    
    expect(screen.getByText('Email Processing')).toBeInTheDocument()
    expect(screen.getByText('Document Analysis')).toBeInTheDocument()
    expect(screen.getByText('Customer Support')).toBeInTheDocument()
    expect(screen.getByText('Content Moderation')).toBeInTheDocument()
    
    expect(screen.getByText(/Automate email workflows/)).toBeInTheDocument()
    expect(screen.getByText(/Extract insights from contracts/)).toBeInTheDocument()
    expect(screen.getByText(/Enhance support operations/)).toBeInTheDocument()
    expect(screen.getByText(/Deploy real-time content filtering/)).toBeInTheDocument()
  })

  it('renders use case icons', () => {
    render(<UseCases />)
    const icons = document.querySelectorAll('.text-accent')
    expect(icons).toHaveLength(4)
  })
}) 