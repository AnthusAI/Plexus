import React from 'react'
import '@testing-library/jest-dom'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { CTASection } from '../CTASection'

describe('CTASection', () => {
  beforeEach(() => {
    // Mock window.open since we can't actually open windows in tests
    window.open = jest.fn().mockReturnValue(window)
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it('renders the main heading and description', () => {
    render(<CTASection />)
    expect(screen.getByText('Ready to get started?')).toBeInTheDocument()
    expect(screen.getByText(/Join the growing community/)).toBeInTheDocument()
  })

  it('shows loading state when clicking early access button', async () => {
    render(<CTASection />)
    const button = screen.getByRole('button', { name: /request early access/i })
    
    await act(async () => {
      fireEvent.click(button)
    })
    
    await waitFor(() => {
      expect(button).toBeDisabled()
      expect(screen.getByRole('img', { name: 'loading' })).toBeInTheDocument()
    })
  })

  it('opens Google Forms in new window when clicking early access button', async () => {
    render(<CTASection />)
    const button = screen.getByRole('button', { name: /request early access/i })
    
    await act(async () => {
      fireEvent.click(button)
    })
    
    await waitFor(() => {
      expect(window.open).toHaveBeenCalledWith(
        'https://docs.google.com/forms/d/e/1FAIpQLSdWlt4KpwPSBHzg3o8fikHcfrzxo5rCcV-0-zDt815NZ1tcyg/viewform?usp=sf_link',
        '_blank'
      )
    })
  })

  it('shows error message when popup is blocked', async () => {
    // Mock window.open to return null, simulating blocked popup
    (window.open as jest.Mock).mockReturnValue(null)
    
    render(<CTASection />)
    const button = screen.getByRole('button', { name: /request early access/i })
    
    await act(async () => {
      fireEvent.click(button)
    })
    
    await waitFor(() => {
      expect(screen.getByText('Failed to open form. Please disable popup blocker and try again.')).toBeInTheDocument()
    })
    expect(button).not.toBeDisabled()
  })
}) 