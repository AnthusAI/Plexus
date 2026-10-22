'use client'

import React, { useEffect, useRef, useState } from 'react'
import {
  CONSENT_HEADING,
  CONSENT_MESSAGE,
  OPEN_CONSENT_EVENT,
  applyConsent,
  installGoogleTag,
  readStoredConsent,
  reportCtaClick,
  saveConsent,
  setTrackingEnabled,
} from '@/lib/analytics/google-tag'

/** Pages currently mounted that are part of the marketing landing. The authenticated app is never counted. */
let mountedMarketingPages = 0

const choiceClass =
  'flex-1 min-w-[9rem] min-h-11 px-4 py-2 font-semibold rounded-md border-2 border-foreground bg-background text-foreground hover:bg-foreground hover:text-background focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-2'

/** Opens the consent banner again; used by the footer's Cookie settings link. */
export function CookieSettingsLink({ className }: { className?: string }) {
  return (
    <button
      type="button"
      className={className ?? 'underline text-sm text-muted-foreground hover:text-foreground'}
      onClick={() => window.dispatchEvent(new Event(OPEN_CONSENT_EVENT))}
    >
      Cookie settings
    </button>
  )
}

/**
 * Google tag with Consent Mode v2, the consent banner and cta_click reporting for the marketing landing.
 * Render it once inside the landing Layout.
 */
export function MarketingAnalytics() {
  const [open, setOpen] = useState(false)
  const firstChoice = useRef<HTMLButtonElement>(null)
  const reopened = useRef(false)

  useEffect(() => {
    installGoogleTag()
    mountedMarketingPages += 1
    setTrackingEnabled(true)
    setOpen(readStoredConsent() === null)
    const reopen = () => {
      reopened.current = true
      setOpen(true)
    }
    window.addEventListener(OPEN_CONSENT_EVENT, reopen)
    // Capture on window so no page script that stops propagation can hide a CTA click.
    window.addEventListener('click', reportCtaClick, true)
    return () => {
      window.removeEventListener(OPEN_CONSENT_EVENT, reopen)
      window.removeEventListener('click', reportCtaClick, true)
      mountedMarketingPages -= 1
      // Moving between marketing pages remounts this component; only a move into the app turns counting off.
      window.setTimeout(() => {
        if (mountedMarketingPages === 0) setTrackingEnabled(false)
      }, 300)
    }
  }, [])

  useEffect(() => {
    if (open && reopened.current) firstChoice.current?.focus()
  }, [open])

  const choose = (granted: boolean) => {
    applyConsent(granted)
    saveConsent(granted)
    reopened.current = false
    setOpen(false)
  }

  if (!open) return null

  return (
    <div
      id="consent-banner"
      role="region"
      aria-label="Cookie consent"
      aria-describedby="consent-message"
      className="fixed inset-x-0 bottom-0 z-[2147483000] m-4 max-w-xl rounded-lg border-2 border-foreground bg-background p-5 text-foreground shadow-lg"
    >
      <h2 id="consent-heading" className="mb-2 text-lg font-semibold">
        {CONSENT_HEADING}
      </h2>
      <p id="consent-message" className="mb-4">
        {CONSENT_MESSAGE}{' '}
        <a href="/privacy" className="underline">
          Privacy policy
        </a>
      </p>
      <div className="flex flex-wrap gap-3">
        <button type="button" ref={firstChoice} className={choiceClass} onClick={() => choose(false)}>
          Reject all
        </button>
        <button type="button" className={choiceClass} onClick={() => choose(true)}>
          Accept all
        </button>
      </div>
    </div>
  )
}
