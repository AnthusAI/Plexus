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
                Similar to scorecards, scores can be referenced using various identifiers:
              </p>
              
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-6">
                <li><strong>DynamoDB ID</strong>: The unique UUID assigned to the score</li>
                <li><strong>Name</strong>: The human-readable name of the score</li>
                <li><strong>Key</strong>: The machine-friendly key of the score</li>
                <li><strong>External ID</strong>: An optional external identifier for the score</li>
              </ul>
              
              <p className="text-muted-foreground mb-4">
                When using the <code>--score</code> parameter, you can use any of these identifiers:
              </p>
              
              <pre className="bg-muted rounded-lg mb-6">
                <div className="code-container p-4">
                  <code>{`# Using DynamoDB ID
plexus scores info --scorecard "Quality Assurance" --score 7a9b2c3d-4e5f-6g7h-8i9j-0k1l2m3n4o5p

# Using Name (with quotes for names containing spaces)
plexus scores info --scorecard "Quality Assurance" --score "Grammar Check"

# Using Key
plexus scores info --scorecard "Quality Assurance" --score grammar-check

# Using External ID
plexus scores info --scorecard "Quality Assurance" --score gc-001

# Combining different identifier types for scorecard and score
plexus scores info --scorecard quality_assurance --score "Grammar Check"`}</code>
                </div>
              </pre>
              
              <p className="text-muted-foreground">
                The flexible identifier system makes it easy to reference scores in a way that's most convenient for your workflow.
                You can use different identifier types for the scorecard and score in the same command.
              </p>
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
plexus scores list --scorecard example1

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
          <h2 className="text-2xl font-semibold mb-4">Score Management Commands</h2>
          <p className="text-muted-foreground mb-4">
            The CLI provides commands for managing and viewing information about scores.
          </p>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Viewing Score Information</h3>
              <p className="text-muted-foreground mb-4">
                The <code>scores info</code> command displays detailed information about a specific score, including its versions:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`plexus scores info --scorecard "Example Scorecard" --score "Example Score"`}</code>
                </div>
              </pre>
              <p className="text-muted-foreground mb-4">
                This command provides:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Score Details</strong>: Name, key, external ID, type, and order
                </li>
                <li>
                  <strong>Scorecard Information</strong>: Name, key, external ID, and section
                </li>
                <li>
                  <strong>Score Versions</strong>: Up to 10 versions in reverse chronological order (newest first)
                </li>
              </ul>
              
              <h4 className="text-lg font-medium mt-6 mb-2">Version Information</h4>
              <p className="text-muted-foreground mb-4">
                For each version, the command displays:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Version ID</strong>: Unique identifier for the version
                </li>
                <li>
                  <strong>Creation Date</strong>: When the version was created
                </li>
                <li>
                  <strong>Note</strong>: Any notes associated with the version (if available)
                </li>
                <li>
                  <strong>Configuration</strong>: The first 4 lines of the version's configuration
                </li>
                <li>
                  <strong>Status Indicators</strong>: Whether the version is the Champion (active) or Featured
                </li>
              </ul>
              
              <p className="text-muted-foreground mt-4">
                Example output:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4 text-xs">
                  <code>{`Score Information:
  Name: Grammar Check
  Key: grammar-check
  External ID: 123
  Type: LangGraphScore
  Order: 1

Scorecard Information:
  Name: Quality Assurance
  Key: quality_assurance
  External ID: 456
  Section: Default

Score Versions (3 of 3 total versions, newest first):
  Version: 7a9b2c3d-4e5f-6g7h-8i9j-0k1l2m3n4o5p
  Created: 2023-10-15 14:30:45
  Note: Updated prompt for better accuracy
  Configuration:
    {
      "prompt": "Evaluate the grammar of the following text...",
      "model": "gpt-4",
      // ... configuration continues ...
    }
  [Champion]

  Version: 8b9c3d4e-5f6g-7h8i-9j0k-1l2m3n4o5p6q
  Created: 2023-09-20 09:15:22
  Configuration:
    {
      "prompt": "Check the following text for grammar errors...",
      "model": "gpt-3.5-turbo",
      // ... configuration continues ...
    }
  [Featured]

  Version: 9c0d4e5f-6g7h-8i9j-0k1l-2m3n4o5p6q7r
  Created: 2023-08-05 11:45:33
  Configuration:
    {
      "prompt": "Analyze the grammar in this content...",
      "model": "gpt-3.5-turbo",
      // ... configuration continues ...
    }`}</code>
                </div>
              </pre>
              <p className="text-muted-foreground">
                This command displays up to 10 versions in reverse chronological order (newest first), showing which 
                version is the champion and which versions are featured.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Listing Scores in a Scorecard</h3>
              <p className="text-muted-foreground mb-4">
                The <code>scores list</code> command displays all scores within a scorecard:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`plexus scores list --scorecard "Example Scorecard"

# You can also use the score alias (singular form)
plexus score list --scorecard "Example Scorecard"`}</code>
                </div>
              </pre>
              <p className="text-muted-foreground mb-4">
                This command provides a detailed view of all scores organized by section, including:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Score Names</strong>: The human-readable names of each score
                </li>
                <li>
                  <strong>Score IDs</strong>: The unique identifiers for each score
                </li>
                <li>
                  <strong>Score Keys</strong>: The machine-friendly keys for each score
                </li>
                <li>
                  <strong>External IDs</strong>: Any external identifiers associated with the scores
                </li>
              </ul>
            </div>
          </div>
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