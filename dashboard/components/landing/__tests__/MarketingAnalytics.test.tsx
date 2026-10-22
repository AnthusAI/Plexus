import React from 'react'
import '@testing-library/jest-dom'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { CookieSettingsLink, MarketingAnalytics } from '../MarketingAnalytics'
import { CONSENT_STORAGE_KEY } from '@/lib/analytics/google-tag'

function consentUpdates(): any[] {
  return ((window as any).dataLayer as IArguments[])
    .map((entry) => Array.from(entry))
    .filter((c) => c[0] === 'consent' && c[1] === 'update')
    .map((c) => c[2])
}

beforeEach(() => {
  delete (window as any).gtag
  delete (window as any).dataLayer
  document.head.innerHTML = ''
  window.localStorage.clear()
})

describe('MarketingAnalytics', () => {
  it('shows the approved banner with equal Accept all and Reject all choices', () => {
    render(<MarketingAnalytics />)
    const region = screen.getByRole('region', { name: 'Cookie consent' })
    expect(region).toHaveTextContent('Cookies and analytics')
    expect(region).toHaveTextContent(
      'We use cookies to measure how this site is used and, if you agree, for advertising. You can accept all, reject all, and change your choice at any time.',
    )
    const accept = screen.getByRole('button', { name: 'Accept all' })
    const reject = screen.getByRole('button', { name: 'Reject all' })
    expect(accept.className).toBe(reject.className)
    expect(screen.getByRole('link', { name: 'Privacy policy' })).toHaveAttribute('href', '/privacy')
  })

  it('Accept all grants all four signals and stores the choice', () => {
    render(<MarketingAnalytics />)
    fireEvent.click(screen.getByRole('button', { name: 'Accept all' }))
    expect(consentUpdates().pop()).toEqual({
      ad_storage: 'granted',
      ad_user_data: 'granted',
      ad_personalization: 'granted',
      analytics_storage: 'granted',
    })
    expect(JSON.parse(window.localStorage.getItem(CONSENT_STORAGE_KEY)!).granted).toBe(true)
    expect(screen.queryByRole('region', { name: 'Cookie consent' })).not.toBeInTheDocument()
  })

  it('Reject all denies all four signals', () => {
    render(<MarketingAnalytics />)
    fireEvent.click(screen.getByRole('button', { name: 'Reject all' }))
    expect(consentUpdates().pop()).toEqual({
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      analytics_storage: 'denied',
    })
  })

  it('stays hidden after a stored choice and reopens from Cookie settings', () => {
    window.localStorage.setItem(
      CONSENT_STORAGE_KEY,
      JSON.stringify({ version: 1, savedAt: Date.now(), granted: false }),
    )
    render(
      <>
        <MarketingAnalytics />
        <CookieSettingsLink />
      </>,
    )
    expect(screen.queryByRole('region', { name: 'Cookie consent' })).not.toBeInTheDocument()
    act(() => {
      fireEvent.click(screen.getByRole('button', { name: 'Cookie settings' }))
    })
    expect(screen.getByRole('region', { name: 'Cookie consent' })).toBeInTheDocument()
  })
})
