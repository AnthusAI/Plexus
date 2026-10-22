import {
  CONSENT_STORAGE_KEY,
  GA_MEASUREMENT_ID,
  ctaClickFor,
  installGoogleTag,
  readStoredConsent,
  reportCtaClick,
  saveConsent,
} from '../google-tag'

type Call = unknown[]

function calls(): Call[] {
  return ((window as any).dataLayer as IArguments[]).map((entry) => Array.from(entry))
}

beforeEach(() => {
  delete (window as any).gtag
  delete (window as any).dataLayer
  document.head.innerHTML = ''
  window.localStorage.clear()
  window.history.replaceState({}, '', '/')
})

describe('installGoogleTag', () => {
  it('sets consent defaults before the loader and the config call', () => {
    installGoogleTag()
    const seen = calls()
    const kinds = seen.map((c) => `${c[0]}${c[1] === 'default' ? ':default' : ''}`)
    expect(kinds.slice(0, 2)).toEqual(['consent:default', 'consent:default'])
    expect(kinds.indexOf('config')).toBeGreaterThan(kinds.lastIndexOf('consent:default'))
    expect(document.getElementById('google-tag-loader')?.getAttribute('src')).toBe(
      `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`,
    )
    expect(GA_MEASUREMENT_ID).toBe('G-31SC26SDGX')
  })

  it('denies all four signals for EEA, GB and CH and grants only analytics elsewhere', () => {
    installGoogleTag()
    const [regional, general] = calls().filter((c) => c[0] === 'consent' && c[1] === 'default').map((c) => c[2] as any)
    expect(regional).toMatchObject({
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      analytics_storage: 'denied',
    })
    expect(regional.region).toEqual(expect.arrayContaining(['DE', 'FR', 'IS', 'LI', 'NO', 'GB', 'CH']))
    expect(general).toMatchObject({
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      analytics_storage: 'granted',
    })
    expect(general.region).toBeUndefined()
    expect(calls()).toContainEqual(['set', 'ads_data_redaction', true])
  })

  it('is idempotent across page mounts', () => {
    installGoogleTag()
    installGoogleTag()
    expect(document.querySelectorAll('#google-tag-loader')).toHaveLength(1)
    expect(calls().filter((c) => c[0] === 'config')).toHaveLength(1)
  })

  it('re-applies a stored choice and ignores an expired or other-version choice', () => {
    saveConsent(true)
    installGoogleTag()
    expect(calls()).toContainEqual(['consent', 'update', expect.objectContaining({ analytics_storage: 'granted', ad_storage: 'granted' })])
    expect(readStoredConsent(Date.now() + 184 * 86_400_000)).toBeNull()
    window.localStorage.setItem(CONSENT_STORAGE_KEY, JSON.stringify({ version: 99, savedAt: Date.now(), granted: true }))
    expect(readStoredConsent()).toBeNull()
  })

  it('honours the ?notrack=1 owner opt-out', () => {
    window.history.replaceState({}, '', '/?notrack=1')
    installGoogleTag()
    expect((window as any)[`ga-disable-${GA_MEASUREMENT_ID}`]).toBe(true)
  })
})

describe('cta_click', () => {
  function anchor(html: string): HTMLAnchorElement {
    document.body.innerHTML = html
    return document.querySelector('a') as HTMLAnchorElement
  }

  it('reports label, location and host+path without the query', () => {
    const a = anchor('<a href="https://anth.us/engage/?solution=Primus&cta=early-access" data-cta-location="band">  Request\n Early Access </a>')
    expect(ctaClickFor(a)).toEqual({
      cta_text: 'Request Early Access',
      cta_location: 'band',
      link_url: 'anth.us/engage/',
      transport_type: 'beacon',
    })
  })

  it('trims the label to 100 characters and ignores links that are not marked as CTAs', () => {
    const long = 'x'.repeat(150)
    expect(ctaClickFor(anchor(`<a href="/a" data-cta-location="hero">${long}</a>`))!.cta_text).toHaveLength(100)
    expect(ctaClickFor(anchor('<a href="/a">Docs</a>'))).toBeNull()
  })

  it('sends the event through gtag on click and never prevents navigation', () => {
    installGoogleTag()
    const a = anchor('<a href="/solutions/platform" data-cta-location="hero"><span>Learn More</span></a>')
    const event = new MouseEvent('click', { bubbles: true, cancelable: true })
    window.addEventListener('click', reportCtaClick, true)
    a.querySelector('span')!.dispatchEvent(event)
    window.removeEventListener('click', reportCtaClick, true)
    expect(event.defaultPrevented).toBe(false)
    expect(calls()).toContainEqual([
      'event',
      'cta_click',
      { cta_text: 'Learn More', cta_location: 'hero', link_url: 'localhost/solutions/platform', transport_type: 'beacon' },
    ])
  })

  it('does nothing when gtag is not loaded', () => {
    const a = anchor('<a href="/a" data-cta-location="hero">Go</a>')
    expect(() => reportCtaClick({ target: a } as unknown as MouseEvent)).not.toThrow()
  })
})
