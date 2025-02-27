'use client';

export default function CliPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <style jsx>{`
        .code-container {
          position: relative;
          overflow-x: auto;
          white-space: pre;
          -webkit-overflow-scrolling: touch;
        }
        
        .code-container::after {
          content: '';
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          width: 16px;
          background: linear-gradient(to right, transparent, var(--background-muted));
          opacity: 0;
          transition: opacity 0.2s;
          pointer-events: none;
        }
        
        .code-container:hover::after {
          opacity: 1;
        }
      `}</style>

      <h1 className="text-4xl font-bold mb-4">
        <code className="text-[36px]">plexus</code> CLI Tool
      </h1>
      <p className="text-lg text-muted-foreground mb-8">
        Master the command-line interface for managing your Plexus deployment.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus CLI tool provides a powerful command-line interface for managing your Plexus deployment,
            with a focus on evaluating and monitoring scorecard performance.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Installation</h2>
          <p className="text-muted-foreground mb-4">
            Install the Plexus CLI tool using pip:
          </p>
          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
              <code>pip install plexus-cli</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Flexible Identifier System</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus CLI uses a flexible identifier system that allows you to reference resources using different types of identifiers. This makes commands more intuitive and reduces the need to look up specific IDs.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Scorecard Identifiers</h3>
              <p className="text-muted-foreground mb-4">
                When using the <code>--scorecard</code> parameter, you can provide any of the following:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li><strong>DynamoDB ID</strong>: The unique database identifier (e.g., <code>e51cd5ec-1940-4d8e-abcc-faa851390112</code>)</li>
                <li><strong>Name</strong>: The human-readable name (e.g., <code>"Quality Assurance"</code>)</li>
                <li><strong>Key</strong>: The URL-friendly key (e.g., <code>quality-assurance</code>)</li>
                <li><strong>External ID</strong>: Your custom external identifier (e.g., <code>qa-2023</code>)</li>
              </ul>
              
              <p className="text-muted-foreground mt-4">
                Examples:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`# All of these commands do the same thing, using different identifier types
plexus scorecards info --scorecard e51cd5ec-1940-4d8e-abcc-faa851390112
plexus scorecards info --scorecard "Quality Assurance"
plexus scorecards info --scorecard quality-assurance
plexus scorecards info --scorecard qa-2023`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Score Identifiers</h3>
              <p className="text-muted-foreground mb-4">
                Similarly, when using the <code>--score</code> parameter, you can provide any of the following:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li><strong>DynamoDB ID</strong>: The unique database identifier</li>
                <li><strong>Name</strong>: The human-readable name</li>
                <li><strong>Key</strong>: The URL-friendly key</li>
                <li><strong>External ID</strong>: Your custom external identifier</li>
              </ul>
              
              <p className="text-muted-foreground mt-4">
                Examples:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`# All of these commands do the same thing, using different identifier types
plexus scores info --score 7a9b2c3d-4e5f-6g7h-8i9j-0k1l2m3n4o5p
plexus scores info --score "Grammar Check"
plexus scores info --score grammar-check
plexus scores info --score gc-001`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Account Identifiers</h3>
              <p className="text-muted-foreground mb-4">
                When using the <code>--account</code> parameter, you can provide any of the following:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li><strong>DynamoDB ID</strong>: The unique database identifier</li>
                <li><strong>Name</strong>: The human-readable name</li>
                <li><strong>Key</strong>: The URL-friendly key</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Common Scorecard Commands</h2>
          <p className="text-muted-foreground mb-4">
            Here are some common commands for managing scorecards:
          </p>
          
          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
              <code>{`# List all scorecards
plexus scorecards list

# Get detailed information about a specific scorecard
plexus scorecards info --scorecard example1

# List all scores in a scorecard
plexus scorecards list-scores --scorecard example1

# Pull scorecard configuration to YAML
plexus scorecards pull --scorecard example1 --output ./my-scorecards

# Push scorecard configuration from YAML
plexus scorecards push --file ./my-scorecard.yaml --update

# Delete a scorecard
plexus scorecards delete --scorecard example1`}</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Running Evaluations</h2>
          <p className="text-muted-foreground mb-4">
            The primary way to evaluate your scorecard's performance is using the <code>evaluate accuracy</code> command:
          </p>
          
          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
              <code>{`plexus \\
  evaluate \\
  accuracy \\
  --scorecard "Inbound Leads" \\
  --number-of-samples 100 \\
  --visualize`}</code>
            </div>
          </pre>

          <div className="pl-4 space-y-2 text-muted-foreground mb-6">
            <p><code>--scorecard</code>: Scorecard to evaluate (accepts ID, name, key, or external ID)</p>
            <p><code>--number-of-samples</code>: Number of samples to evaluate (recommended: 100+)</p>
            <p><code>--visualize</code>: Generate visualizations of the results</p>
          </div>

          <p className="text-muted-foreground mb-4">
            This command will evaluate your scorecard against labeled samples and provide detailed accuracy metrics,
            including precision, recall, and confusion matrices when visualization is enabled.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Viewing Evaluation Results</h2>
          <p className="text-muted-foreground mb-4">
            After running evaluations, you can view the results:
          </p>

          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
              <code>{`# List all evaluation records
plexus \\
  evaluations \\
  list

# View detailed results
plexus \\
  evaluations \\
  list-results \\
  --evaluation evaluation-id \\
  --limit 100`}</code>
            </div>
          </pre>

          <p className="text-muted-foreground mb-4">
            The results include accuracy metrics, individual predictions, and any visualizations that were generated
            during the evaluation.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Additional Resources</h2>
          <p className="text-muted-foreground">
            For more detailed information about specific features:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Visit our <a href="/documentation/basics/evaluations" className="text-primary hover:underline">Evaluations Guide</a></li>
            <li>Check the built-in help with <code>plexus --help</code></li>
            <li>Get command-specific help with <code>plexus evaluate accuracy --help</code></li>
          </ul>
        </section>
      </div>
    </div>
  )
} 