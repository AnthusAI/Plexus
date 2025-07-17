import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Setup - Plexus Documentation',
  description: 'Setup and configuration guide for Plexus',
}

export default function SetupPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Setup</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Get started with Plexus quickly and easily. Follow our step-by-step guides to set up your environment and configuration.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Getting Started</h2>
          <div className="grid gap-6">
            <div className="border rounded-lg p-6">
              <h3 className="text-xl font-medium mb-3">
                <a href="/documentation/setup/quick-start" className="text-blue-600 hover:text-blue-800">
                  Quick Start
                </a>
              </h3>
              <p className="text-muted-foreground">
                Get Plexus up and running in minutes with our streamlined installation guide.
                Covers basic installation, dependencies, and first-time setup.
              </p>
            </div>

            <div className="border rounded-lg p-6">
              <h3 className="text-xl font-medium mb-3">
                <a href="/documentation/setup/configuration" className="text-blue-600 hover:text-blue-800">
                  Configuration Files
                </a>
              </h3>
              <p className="text-muted-foreground">
                Learn how to configure Plexus using YAML configuration files for managing credentials,
                API endpoints, and other settings in an organized, maintainable way.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Recommended Setup Path</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">1. Installation</h3>
              <p className="text-muted-foreground">
                Start with the <a href="/documentation/setup/quick-start" className="text-blue-600 hover:text-blue-800">Quick Start</a> guide
                to install Plexus and its dependencies.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">2. Configuration</h3>
              <p className="text-muted-foreground">
                Set up your <a href="/documentation/setup/configuration" className="text-blue-600 hover:text-blue-800">Configuration Files</a> to
                manage your credentials and environment settings.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">3. First Steps</h3>
              <p className="text-muted-foreground">
                Try running <code className="bg-muted px-2 py-1 rounded">plexus item last</code> to verify your setup is working correctly.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Need Help?</h2>
          <p className="text-muted-foreground mb-4">
            If you encounter issues during setup:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Check our troubleshooting tips in each guide</li>
            <li>Review the <a href="https://github.com/AnthusAI/Plexus" className="text-blue-600 hover:text-blue-800">GitHub repository</a> for examples</li>
            <li>Contact <a href="https://forms.gle/KqpKt8ERsr2QcaP1A" className="text-blue-600 hover:text-blue-800">Anthus AI Support</a> for assistance</li>
          </ul>
        </section>
      </div>
    </div>
  )
}