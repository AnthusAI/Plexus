'use client'

import React from 'react'
import { Layout } from '@/components/landing/Layout'
import { Footer } from '@/components/landing/Footer'
import { CookieSettingsLink } from '@/components/landing/MarketingAnalytics'
import { GA_MEASUREMENT_ID } from '@/lib/analytics/google-tag'

export default function PrivacyPage() {
  return (
    <Layout>
      <article className="mx-auto max-w-3xl px-4 py-12 md:px-8 space-y-4">
        <h1 className="text-3xl font-bold">Privacy, analytics and cookies</h1>
        <p>
          This site, primus.anth.us, is operated by Endymion Corporation, PO Box 398795, Miami Beach, FL 33139.
          Questions about privacy can go to <a className="underline" href="mailto:info@anth.us">info@anth.us</a>.
        </p>
        <h2 className="text-xl font-semibold pt-4">What we measure</h2>
        <p>
          On the public pages of this site we use Google Analytics 4 (measurement ID {GA_MEASUREMENT_ID}) to count
          visits and see which pages and links are used. It is the same property Anthus uses for its other sites,
          so reports can show visits across anth.us sites, and the hostname tells them apart. We record page views
          and clicks on calls to action: the visible label of the link, where on the page it was, and the
          destination host and path without any query string. We do not send names, email addresses or message
          text to analytics. The signed-in application is not measured.
        </p>
        <h2 className="text-xl font-semibold pt-4">Cookies and your choice</h2>
        <p>
          Analytics sets cookies in your browser. We use Google Consent Mode v2. If you are in the European
          Economic Area, the United Kingdom or Switzerland, analytics and advertising storage are off until you
          choose Accept all. Everywhere else analytics storage is on by default, and the advertising signals (ad
          storage, ad user data and ad personalization) are off until you accept. Reject all turns all four
          signals off. Google&apos;s ads data redaction is always on.
        </p>
        <p>
          The banner offers Accept all and Reject all with equal prominence. Your choice is saved in this
          browser&apos;s local storage for about six months, after which we ask again. You can change it at any
          time: <CookieSettingsLink className="underline" />.
        </p>
        <h2 className="text-xl font-semibold pt-4">Opting out of analytics entirely</h2>
        <p>
          Visit any page with <code>?notrack=1</code> added to its address to stop counting that browser, and{' '}
          <code>?notrack=0</code> to turn counting back on.
        </p>
        <h2 className="text-xl font-semibold pt-4">Changes</h2>
        <p>If we change what we measure we will update this page and ask for your choice again.</p>
      </article>
      <Footer />
    </Layout>
  )
}
