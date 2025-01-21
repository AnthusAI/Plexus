import React from 'react'
import { render, screen } from '@testing-library/react'
import { Footer } from '../Footer'

describe('Footer', () => {
  it('renders the company name and copyright notice', () => {
    render(<Footer />)
    const currentYear = new Date().getFullYear()
    expect(screen.getByText(`© ${currentYear} Anthus AI Solutions`))
      .toBeInTheDocument()
  })

  it('renders all section headings', () => {
    render(<Footer />)
    expect(screen.getByText('About')).toBeInTheDocument()
    expect(screen.getByText('Resources')).toBeInTheDocument()
    expect(screen.getByText('Connect')).toBeInTheDocument()
  })

  it('renders all resource links', () => {
    render(<Footer />)
    expect(screen.getByText('Articles')).toHaveAttribute('href', 'https://anth.us/articles')
    expect(screen.getByText('Posts')).toHaveAttribute('href', 'https://anth.us/posts')
    expect(screen.getByText('Updates')).toHaveAttribute('href', 'https://x.com/Anthus_AI')
  })

  it('renders all social media links with correct attributes', () => {
    render(<Footer />)
    
    const githubLink = screen.getByLabelText('Follow us on GitHub')
    expect(githubLink).toHaveAttribute('href', 'https://github.com/AnthusAI')
    expect(githubLink).toHaveAttribute('target', '_blank')
    expect(githubLink).toHaveAttribute('rel', 'noopener noreferrer')

    const linkedinLink = screen.getByLabelText('Connect on LinkedIn')
    expect(linkedinLink).toHaveAttribute(
      'href', 
      'https://www.linkedin.com/company/anthus-ai-solutions'
    )
    expect(linkedinLink).toHaveAttribute('target', '_blank')
    expect(linkedinLink).toHaveAttribute('rel', 'noopener noreferrer')

    const discordLink = screen.getByLabelText('Join us on Discord')
    expect(discordLink).toHaveAttribute('href', 'https://discord.gg/uStyWraJ2M')
    expect(discordLink).toHaveAttribute('target', '_blank')
    expect(discordLink).toHaveAttribute('rel', 'noopener noreferrer')

    const contactLink = screen.getByLabelText('Contact Us')
    expect(contactLink).toHaveAttribute(
      'href', 
      'https://docs.google.com/forms/d/e/1FAIpQLSdWlt4KpwPSBHzg3o8fikHcfrzxo5rCcV-0-zDt815NZ1tcyg/viewform?usp=sf_link'
    )
    expect(contactLink).toHaveAttribute('target', '_blank')
    expect(contactLink).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('renders the about text and Anth.us link', () => {
    render(<Footer />)
    expect(screen.getByText(/Plexus is a product of Anth.us/)).toBeInTheDocument()
    const anthusLink = screen.getByText('Learn more about Anth.us →')
    expect(anthusLink).toHaveAttribute('href', 'https://anth.us')
    expect(anthusLink).toHaveAttribute('target', '_blank')
    expect(anthusLink).toHaveAttribute('rel', 'noopener noreferrer')
  })
}) 