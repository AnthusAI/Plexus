import React from 'react'
import '@testing-library/jest-dom'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { Hero } from '../Hero'
import { useRouter } from 'next/navigation'

jest.mock('next/navigation', () => ({
  useRouter: jest.fn()
}))

const mockUseRouter = useRouter as jest.Mock

describe('Hero', () => {
  const mockPush = jest.fn()
  
  beforeEach(() => {
    mockUseRouter.mockReturnValue({
      push: mockPush
    })
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  it('renders the main heading', () => {
    render(<Hero />)
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.getByText(/ai agents/i)).toBeInTheDocument()
    expect(screen.getByText(/your data/i)).toBeInTheDocument()
    expect(screen.getByText(/no code/i)).toBeInTheDocument()
  })

  it('renders both CTA buttons', () => {
    render(<Hero />)
    expect(screen.getByText('Learn More')).toBeInTheDocument()
    expect(screen.getByText('Log In')).toBeInTheDocument()
  })

  it('navigates to dashboard when clicking Log In', async () => {
    render(<Hero />)
    const loginButton = screen.getByText('Log In')
    
    await act(async () => {
      fireEvent.click(loginButton)
    })
    
    expect(mockPush).toHaveBeenCalledWith('/dashboard')
  })

  it('shows loading state when clicking Log In', async () => {
    mockPush.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)))
    render(<Hero />)

    const loginButton = screen.getByRole('button', { name: /log in/i })
    await act(async () => {
      fireEvent.click(loginButton)
    })
    
    await waitFor(() => {
      expect(loginButton).toBeDisabled()
      expect(screen.queryByText('Log In')).not.toBeInTheDocument()
      expect(screen.getByRole('img', { name: 'loading' })).toBeInTheDocument()
    })
  })

  it('shows error message when navigation fails', async () => {
    mockPush.mockRejectedValueOnce(new Error('Navigation failed'))
    render(<Hero />)
    const loginButton = screen.getByText('Log In')
    
    await act(async () => {
      fireEvent.click(loginButton)
    })
    
    await waitFor(() => {
      expect(screen.getByText('Failed to navigate to dashboard. Please try again.')).toBeInTheDocument()
    })
    expect(screen.getByText('Log In')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /log in/i })).not.toBeDisabled()
  })
}) 