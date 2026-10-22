import React from 'react'
import AnthusFooter from 'anthus-footer'
import { CookieSettingsLink } from './MarketingAnalytics'

export const Footer = () => {
  return (
    <>
      <AnthusFooter
        siteId="primus"
        subtitle="Part of the Anthus Platform"
        description="Primus is the Anthus MLOps platform and agent incubator for evaluating, deploying, and continuously improving AI agents."
        additionalColumns={[
          {
            title: 'Resources',
            links: [
              { label: 'Documentation', href: '/documentation', external: false },
              { label: 'Python SDK', href: 'https://anthusai.github.io/Primus/' },
              { label: 'Change Log', href: 'https://github.com/AnthusAI/Primus/blob/main/CHANGELOG.md' },
            ],
          },
        ]}
      />
      <div className="flex justify-center gap-6 bg-card px-4 pb-6 text-sm text-muted-foreground">
        <a href="/privacy" className="underline hover:text-foreground">
          Privacy
        </a>
        <CookieSettingsLink />
      </div>
    </>
  )
}
