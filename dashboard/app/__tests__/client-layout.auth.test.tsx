import React from 'react'
import { render, screen } from '@testing-library/react'

const mockUseAuthenticator = jest.fn()

jest.mock('@aws-amplify/ui-react/styles.css', () => ({}))

jest.mock('next/navigation', () => ({
  usePathname: () => '/lab/console',
  useRouter: () => ({ push: jest.fn() }),
}))

jest.mock('@aws-amplify/ui-react', () => {
  const Authenticator = ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="authenticator">{children || 'Sign in to continue'}</div>
  )
  Authenticator.Provider = ({ children }: { children: React.ReactNode }) => <>{children}</>

  return {
    Authenticator,
    useAuthenticator: () => mockUseAuthenticator(),
  }
})

jest.mock('@/app/contexts/SidebarContext', () => ({
  SidebarProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

jest.mock('@/app/contexts/AccountContext', () => ({
  AccountProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

jest.mock('@/components/theme-provider', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

jest.mock('../amplify-config', () => ({ resolveAmplifyOutputs: () => null }))

import ClientLayout from '../client-layout'

describe('ClientLayout authentication boundary', () => {
  beforeEach(() => {
    mockUseAuthenticator.mockReturnValue({ authStatus: 'unauthenticated' })
  })

  it('shows a sign-in interface instead of a blank protected page', async () => {
    render(
      <ClientLayout>
        <div>Protected Console</div>
      </ClientLayout>,
    )

    expect(await screen.findByTestId('authenticator')).toHaveTextContent('Sign in to continue')
    expect(screen.queryByText('Protected Console')).not.toBeInTheDocument()
  })
})
