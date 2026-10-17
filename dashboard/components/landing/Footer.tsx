import React from 'react'
import AnthusFooter from 'anthus-footer'

export const Footer = () => {
  return (
    <AnthusFooter
      siteId="primus"
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
  )
} 