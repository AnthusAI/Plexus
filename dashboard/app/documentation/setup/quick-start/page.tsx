import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Quick Start - Plexus Documentation',
  description: 'Get started with Plexus quickly and easily',
}

export default function QuickStartPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Quick Start</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Get Plexus up and running in just a few minutes with this streamlined installation guide.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Prerequisites</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground">
              Before installing Plexus, make sure you have:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li><strong>Python 3.11+</strong> - Plexus requires Python 3.11 or later</li>
              <li><strong>Git</strong> - For cloning the repository</li>
              <li><strong>pip</strong> - Python package manager (included with Python)</li>
              <li><strong>Virtual environment</strong> (recommended) - To isolate dependencies</li>
            </ul>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Installation Steps</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">1. Clone the Repository</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`git clone https://github.com/AnthusAI/Plexus.git
cd Plexus`}</code>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">2. Set Up Python Environment</h3>
              <p className="text-muted-foreground mb-3">
                Create and activate a virtual environment (recommended):
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\\Scripts\\activate`}</code>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">3. Install Plexus</h3>
              <p className="text-muted-foreground mb-3">
                Install Plexus in development mode:
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>pip install -e .</code>
              </pre>
              <p className="text-muted-foreground text-sm">
                The <code>-e</code> flag installs in "editable" mode, allowing you to modify the code and see changes immediately.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">4. Set Up Configuration</h3>
              <p className="text-muted-foreground mb-3">
                Create your configuration directory and copy the example file:
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Create configuration directory
mkdir -p .plexus

# Copy example configuration
cp plexus.yaml.example .plexus/config.yaml`}</code>
              </pre>
              <p className="text-muted-foreground">
                Edit <code>.plexus/config.yaml</code> with your specific settings. See the{' '}
                <a href="/documentation/setup/configuration" className="text-blue-600 hover:text-blue-800">
                  Configuration Files
                </a>{' '}
                guide for detailed instructions.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">5. Verify Installation</h3>
              <p className="text-muted-foreground mb-3">
                Test that everything is working:
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Check Plexus version
plexus --help

# Test configuration loading (requires valid credentials)
plexus item last`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Common Issues</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Command Not Found</h3>
              <p className="text-muted-foreground">
                If you get a "command not found" error when running <code>plexus</code>:
              </p>
              <ul className="list-disc pl-6 mt-2 space-y-2 text-muted-foreground">
                <li>Make sure your virtual environment is activated</li>
                <li>Verify the installation with <code>pip list | grep plexus</code></li>
                <li>Try reinstalling with <code>pip install -e .</code></li>
              </ul>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Missing Credentials</h3>
              <p className="text-muted-foreground">
                If you get AWS credentials errors, make sure your <code>.plexus/config.yaml</code> file
                contains valid AWS credentials and API keys. See the{' '}
                <a href="/documentation/setup/configuration" className="text-blue-600 hover:text-blue-800">
                  Configuration Files
                </a>{' '}
                guide for details.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <p className="text-muted-foreground mb-4">
            Now that you have Plexus installed:
          </p>
          <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
            <li>
              <strong>Configure your environment:</strong>
              <p>Set up your <a href="/documentation/setup/configuration" className="text-blue-600 hover:text-blue-800">Configuration Files</a> with your specific credentials and settings.</p>
            </li>
            <li>
              <strong>Explore the concepts:</strong>
              <p>Learn about <a href="/documentation/concepts" className="text-blue-600 hover:text-blue-800">Items, Scorecards, and Scores</a> to understand how Plexus works.</p>
            </li>
            <li>
              <strong>Try the CLI:</strong>
              <p>Use commands like <code>plexus item last</code> and <code>plexus scorecards list</code> to explore your data.</p>
            </li>
            <li>
              <strong>Run evaluations:</strong>
              <p>Learn how to <a href="/documentation/methods/evaluate-score" className="text-blue-600 hover:text-blue-800">evaluate scores</a> and measure performance.</p>
            </li>
          </ol>
        </section>
      </div>
    </div>
  )
}