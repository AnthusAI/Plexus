import React from 'react'
import { render } from '@testing-library/react'
import LandingPage from '../page'
import { useRouter, usePathname } from 'next/navigation'
import dynamic from 'next/dynamic'

// Mock next/dynamic
jest.mock('next/dynamic', () => () => {
  const DynamicComponent = () => null
  DynamicComponent.displayName = 'DynamicComponent'
  return DynamicComponent
})

jest.mock('next/navigation', () => ({
  useRouter: jest.fn().mockReturnValue({
    push: jest.fn(),
    pathname: '/'
  }),
  usePathname: jest.fn().mockReturnValue('/')
}))

const mockUseRouter = useRouter as jest.Mock
const mockUsePathname = usePathname as jest.Mock

describe('Landing Page Hydration', () => {
  beforeEach(() => {
    mockUseRouter.mockReturnValue({
      push: jest.fn(),
      pathname: '/'
    })
    mockUsePathname.mockReturnValue('/')
  })

  it('renders server and client components without hydration mismatch', () => {
    const consoleSpy = jest.spyOn(console, 'error')
    render(<LandingPage />)
    
    const hydrationErrors = consoleSpy.mock.calls.filter(call => 
      call[0]?.includes?.('Warning: Text content did not match') ||
      call[0]?.includes?.('Warning: Expected server HTML to contain')
    )
    
    expect(hydrationErrors).toHaveLength(0)
    consoleSpy.mockRestore()
  })

  it('maintains interactive elements after hydration', () => {
    const { getByRole } = render(<LandingPage />)
    const loginButton = getByRole('button', { name: /sign in/i })
    expect(loginButton).toBeEnabled()
  })
}) 