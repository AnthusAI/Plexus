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
plexus scorecards push --scorecard example1 --file ./my-scorecard.yaml --note "Updated configuration"

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
          <h2 className="text-2xl font-semibold mb-4">Score Result Commands</h2>
          <p className="text-muted-foreground mb-4">
            The CLI provides commands for viewing and analyzing individual score results:
          </p>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Listing Score Results</h3>
              <p className="text-muted-foreground mb-4">
                The <code>results list</code> command displays recent score results with optional filtering:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`# List score results for a specific scorecard
plexus results list --scorecard "Example Scorecard" --limit 20

# List score results for a specific account
plexus results list --account "Example Account" --limit 20`}</code>
                </div>
              </pre>
              <p className="text-muted-foreground mb-4">
                This command requires either a scorecard or account identifier and provides:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Basic Information</strong>: ID, value, confidence, correct status, and related IDs
                </li>
                <li>
                  <strong>Timestamps</strong>: When the result was created and last updated
                </li>
                <li>
                  <strong>Metadata</strong>: Pretty-printed JSON showing input data and context
                </li>
                <li>
                  <strong>Trace</strong>: Detailed record of the evaluation process (when available)
                </li>
                <li>
                  <strong>Explanation</strong>: The reasoning behind the result (when available)
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Viewing Detailed Score Result Information</h3>
              <p className="text-muted-foreground mb-4">
                The <code>results info</code> command displays detailed information about a specific score result:
              </p>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`plexus results info --id "result-id-here"`}</code>
                </div>
              </pre>
              <p className="text-muted-foreground mb-4">
                This command provides a comprehensive view of a single score result, including:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Complete Result Data</strong>: All fields and values associated with the result
                </li>
                <li>
                  <strong>Formatted Metadata</strong>: Nicely formatted JSON for easy reading
                </li>
                <li>
                  <strong>Formatted Trace</strong>: Detailed execution trace with clear visual separation
                </li>
                <li>
                  <strong>Relationship Information</strong>: Links to related entities like items, scorecards, and evaluations
                </li>
              </ul>
              <p className="text-muted-foreground mt-4">
                This command is particularly useful for debugging evaluation issues or understanding exactly how a specific result was determined.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Report Commands</h2>
          <p className="text-muted-foreground mb-4">
            Manage report configurations and generated reports using the following commands.
            Remember to run commands from your project root using `python -m plexus.cli.CommandLineInterface ...`
            if you are working on the codebase locally, to avoid conflicts with globally installed versions.
          </p>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-2">Report Configuration Commands</h3>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`# List available report configurations for your account
python -m plexus.cli.CommandLineInterface report config list

# Show details of a specific report configuration (using ID or Name)
# Note: Uses the flexible identifier system (tries ID, then Name if it looks like UUID; otherwise Name then ID)
python -m plexus.cli.CommandLineInterface report config show <id_or_name>

# Create a new report configuration from a Markdown/YAML file
python -m plexus.cli.CommandLineInterface report config create --name "My Report Config" --file ./path/to/config.md [--description "Optional description"]

# Delete a report configuration (prompts for confirmation)
python -m plexus.cli.CommandLineInterface report config delete <id_or_name>

# Delete a report configuration (skip confirmation prompt)
python -m plexus.cli.CommandLineInterface report config delete <id_or_name> --yes`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Report Generation and Viewing Commands</h3>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`# Trigger a new report generation task based on a configuration (using ID or Name for config)
python -m plexus.cli.CommandLineInterface report run --config <config_id_or_name> [param1=value1 param2=value2 ...]

# List generated reports, optionally filtered by configuration (using ID or Name for config filter)
# Shows Report ID, Name, Config ID, Task ID, and Task Status
python -m plexus.cli.CommandLineInterface report list [--config <config_id_or_name>]

# Show details of a specific generated report (using ID or Name)
# Includes Report details, linked Task status/details, rendered output, and Report Block summary
python -m plexus.cli.CommandLineInterface report show <report_id_or_name>

# Show details of the most recently created report
python -m plexus.cli.CommandLineInterface report last`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Report Block Inspection Commands</h3>
              <pre className="bg-muted rounded-lg mb-4">
                <div className="code-container p-4">
                  <code>{`# List the analysis blocks for a specific report (requires Report ID)
python -m plexus.cli.CommandLineInterface report block list <report_id>

# Show details of a specific block within a report (requires Report ID and block position or name)
# Displays block details, output JSON (syntax highlighted), and logs
python -m plexus.cli.CommandLineInterface report block show <report_id> <block_position_or_name>`}</code>
                </div>
              </pre>
            </div>
          </div>
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