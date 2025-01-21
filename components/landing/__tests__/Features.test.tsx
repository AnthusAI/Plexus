import React from 'react'
import { render, screen } from '@testing-library/react'
import { Features } from '../Features'

describe('Features Component', () => {
  it('renders the main heading', () => {
    render(<Features />)
    expect(screen.getByText('Powerful Features for Agent Orchestration')).toBeInTheDocument()
  })

  it('renders all feature cards', () => {
    render(<Features />)
    
    // Check titles
    expect(screen.getByText('Multi-model')).toBeInTheDocument()
    expect(screen.getByText('Lab workflow')).toBeInTheDocument()
    expect(screen.getByText('Serverless')).toBeInTheDocument()
    expect(screen.getByText('Task dispatch')).toBeInTheDocument()
    
    // Check descriptions
    expect(screen.getByText(/Use any AI\/ML model/)).toBeInTheDocument()
    expect(screen.getByText(/Create and align your own custom classifiers/)).toBeInTheDocument()
    expect(screen.getByText(/Plexus is a lightning-fast/)).toBeInTheDocument()
    expect(screen.getByText(/Connect any node as a worker/)).toBeInTheDocument()
  })

  it('renders feature icons', () => {
    render(<Features />)
    const icons = document.querySelectorAll('.text-accent')
    expect(icons).toHaveLength(4)
  })
}) 