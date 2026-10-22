import React from 'react'
import '@testing-library/jest-dom'
import { render, screen } from '@testing-library/react'
import PrivacyPage from '../page'

jest.mock('next/navigation', () => ({
  useRouter: jest.fn().mockReturnValue({ push: jest.fn() }),
  usePathname: jest.fn().mockReturnValue('/privacy'),
}))

describe('Privacy page', () => {
  it('names the operator and describes analytics, consent and the choice link', () => {
    render(<PrivacyPage />)
    expect(screen.getByText(/Endymion Corporation, PO Box 398795, Miami Beach, FL 33139/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'info@anth.us' })).toHaveAttribute('href', 'mailto:info@anth.us')
    expect(screen.getByText(/Google Analytics 4 \(measurement ID G-31SC26SDGX\)/)).toBeInTheDocument()
    expect(screen.getByText(/Consent Mode v2/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Cookie settings' }).length).toBeGreaterThan(0)
  })
})
