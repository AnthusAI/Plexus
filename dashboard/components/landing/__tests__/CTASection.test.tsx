import React from 'react'
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import { CTASection, EARLY_ACCESS_URL } from '../CTASection'

describe('CTASection', () => {
  it('renders the main heading and description', () => {
    render(<CTASection />)
    expect(screen.getByText('Ready to get started?')).toBeInTheDocument()
    expect(screen.getByText(/Join the growing community/)).toBeInTheDocument()
  })

  it('labels the section as early access', () => {
    render(<CTASection />)
    expect(screen.getByText('Early access')).toBeInTheDocument()
  })

  it('offers Request Early Access as a plain link to the Anth.us engage page', () => {
    render(<CTASection />)
    const link = screen.getByRole('link', { name: /request early access/i })
    expect(link).toHaveAttribute('href', 'https://anth.us/engage/?solution=Primus&cta=early-access')
    expect(EARLY_ACCESS_URL).toBe('https://anth.us/engage/?solution=Primus&cta=early-access')
  })

  it('does not open a window or need a popup, so a popup blocker cannot break it', () => {
    window.open = jest.fn()
    render(<CTASection />)
    const link = screen.getByRole('link', { name: /request early access/i })
    link.addEventListener('click', (event) => event.preventDefault())
    link.click()
    expect(window.open).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: /request early access/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/popup/i)).not.toBeInTheDocument()
  })
})
