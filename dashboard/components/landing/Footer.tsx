import React from 'react'
import AnthusFooter from 'anthus-footer'

export const Footer = () => {
  return (
    <AnthusFooter
      siteId="plexus"
      subtitle="Part of the Anthus Platform"
      description="Plexus is the Anthus MLOps platform and agent incubator for evaluating, deploying, and continuously improving AI agents."
      additionalColumns={[
        {
          title: 'Resources',
          links: [
            { label: 'Documentation', href: '/documentation', external: false },
            { label: 'Python SDK', href: 'https://anthusai.github.io/Plexus/' },
            { label: 'Change Log', href: 'https://github.com/AnthusAI/Plexus/blob/main/CHANGELOG.md' },
          ],
        },
      ]}
    />
  )
} 