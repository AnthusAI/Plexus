/**
 * Anthus analytics conventions for the Primus marketing landing: one GA4 property, Consent Mode v2,
 * a banner with equal Accept all / Reject all, and cta_click events. Nothing here runs in the
 * authenticated app, and no event carries personal data.
 */

export const GA_MEASUREMENT_ID = 'G-31SC26SDGX'

/** EU, Iceland, Liechtenstein, Norway, United Kingdom and Switzerland start with every signal denied. */
export const CONSENT_DENIED_BY_DEFAULT_REGIONS = [
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR',
  'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK',
  'SI', 'ES', 'SE', 'IS', 'LI', 'NO', 'GB', 'CH',
] as const

export const CONSENT_STORAGE_KEY = 'primus-consent'
export const CONSENT_POLICY_VERSION = 1
export const CONSENT_RETENTION_DAYS = 183
export const CONSENT_WAIT_FOR_UPDATE_MS = 500
export const OWNER_OPT_OUT_KEY = 'primus-no-analytics'
export const OPEN_CONSENT_EVENT = 'primus:open-consent-choices'

export const CONSENT_HEADING = 'Cookies and analytics'
export const CONSENT_MESSAGE =
  'We use cookies to measure how this site is used and, if you agree, for advertising. ' +
  'You can accept all, reject all, and change your choice at any time.'

type GtagWindow = Window & {
  dataLayer?: unknown[]
  gtag?: (...args: unknown[]) => void
  [key: `ga-disable-${string}`]: boolean | undefined
}

export interface StoredConsent {
  version: number
  savedAt: number
  granted: boolean
}

export function readStoredConsent(now: number = Date.now()): StoredConsent | null {
  try {
    const raw = JSON.parse(window.localStorage.getItem(CONSENT_STORAGE_KEY) || 'null')
    const retention = CONSENT_RETENTION_DAYS * 86_400_000
    if (
      raw &&
      raw.version === CONSENT_POLICY_VERSION &&
      typeof raw.savedAt === 'number' &&
      typeof raw.granted === 'boolean' &&
      raw.savedAt <= now &&
      now - raw.savedAt < retention
    ) {
      return raw as StoredConsent
    }
  } catch {
    // Storage can be unavailable or hold garbage; either way the visitor is asked again.
  }
  return null
}

export function saveConsent(granted: boolean, now: number = Date.now()): void {
  try {
    window.localStorage.setItem(
      CONSENT_STORAGE_KEY,
      JSON.stringify({ version: CONSENT_POLICY_VERSION, savedAt: now, granted }),
    )
  } catch {
    // The choice still applies for this page view.
  }
}

/** Applies Accept all (true) or Reject all (false) to all four consent signals. */
export function applyConsent(granted: boolean): void {
  const w = window as unknown as GtagWindow
  if (typeof w.gtag !== 'function') return
  const value = granted ? 'granted' : 'denied'
  w.gtag('consent', 'update', {
    ad_storage: value,
    ad_user_data: value,
    ad_personalization: value,
    analytics_storage: value,
  })
}

export function ownerOptedOut(): boolean {
  try {
    return window.localStorage.getItem(OWNER_OPT_OUT_KEY) === '1'
  } catch {
    return false
  }
}

/** ?notrack=1 stops counting this browser and ?notrack=0 starts again, as on the Papyrus-built sites. */
function syncOwnerOptOut(): void {
  try {
    const match = window.location.search.match(/[?&]notrack=(\w+)/)
    if (match) {
      if (match[1] === '1') window.localStorage.setItem(OWNER_OPT_OUT_KEY, '1')
      else window.localStorage.removeItem(OWNER_OPT_OUT_KEY)
    }
  } catch {
    // Without storage the flag simply does not persist.
  }
}

export function setTrackingEnabled(enabled: boolean): void {
  ;(window as unknown as GtagWindow)[`ga-disable-${GA_MEASUREMENT_ID}`] = !enabled || ownerOptedOut()
}

/**
 * Installs the Google tag once per page load: consent defaults first, then the loader, then config.
 * Safe to call repeatedly (every marketing page mounts the component).
 */
export function installGoogleTag(doc: Document = document): void {
  const w = window as unknown as GtagWindow
  if (typeof w.gtag === 'function' && doc.getElementById('google-tag-loader')) return
  syncOwnerOptOut()
  w.dataLayer = w.dataLayer || []
  w.gtag = function gtag() {
    // gtag.js requires the Arguments object, not an array.
    // eslint-disable-next-line prefer-rest-params
    w.dataLayer!.push(arguments)
  }
  const gtag = w.gtag
  gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    analytics_storage: 'denied',
    wait_for_update: CONSENT_WAIT_FOR_UPDATE_MS,
    region: [...CONSENT_DENIED_BY_DEFAULT_REGIONS],
  })
  gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    analytics_storage: 'granted',
    wait_for_update: CONSENT_WAIT_FOR_UPDATE_MS,
  })
  gtag('set', 'ads_data_redaction', true)
  gtag('set', 'url_passthrough', false)
  const stored = readStoredConsent()
  if (stored) applyConsent(stored.granted)
  setTrackingEnabled(true)
  const loader = doc.createElement('script')
  loader.id = 'google-tag-loader'
  loader.async = true
  loader.src = `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`
  doc.head.appendChild(loader)
  gtag('js', new Date())
  gtag('config', GA_MEASUREMENT_ID)
}

export interface CtaClick {
  cta_text: string
  cta_location: string
  link_url: string
  transport_type: 'beacon'
}

/** The cta_click parameters for an anchor marked data-cta-location, or null for any other link. */
export function ctaClickFor(anchor: HTMLAnchorElement, base: string = window.location.href): CtaClick | null {
  const location = anchor.getAttribute('data-cta-location')
  if (!location) return null
  let linkUrl = ''
  try {
    const url = new URL(anchor.getAttribute('href') || '', base)
    linkUrl = url.host + url.pathname
  } catch {
    return null
  }
  return {
    cta_text: (anchor.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 100),
    cta_location: location,
    link_url: linkUrl,
    transport_type: 'beacon',
  }
}

/** Reports a CTA click; never prevents or delays navigation. */
export function reportCtaClick(event: MouseEvent): void {
  try {
    const target = event.target as Element | null
    const anchor = target?.closest?.('a[href][data-cta-location]') as HTMLAnchorElement | null
    const gtag = (window as unknown as GtagWindow).gtag
    if (!anchor || typeof gtag !== 'function') return
    const click = ctaClickFor(anchor)
    if (click) gtag('event', 'cta_click', click)
  } catch {
    // Analytics must never break the page.
  }
}
