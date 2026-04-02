import React from 'react'
import AnthusFooter from 'anthus-footer'

export const Footer = () => {
  const theme = {
    background: 'var(--background)',
    groupedBackground: 'var(--muted)',
    panelBackground: 'var(--card)',
    foreground: 'var(--foreground)',
    mutedForeground: 'var(--muted-foreground)',
    link: 'var(--foreground)',
    fontFamilyBody: 'inherit',
    fontFamilyHeading: 'inherit',
    maxWidth: '1120px',
  }

  return (
    <AnthusFooter
      siteId="plexus"
      mode="auto"
      subtitle="Part of the Anthus Platform"
      description="Plexus is the Anthus MLOps platform and agent incubator for evaluating, deploying, and continuously improving AI agents."
      theme={theme}
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