export default function AddEditScorePage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Add/Edit a Score</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to create and manage individual scores within scorecards using the Plexus dashboard interface.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Adding Scores in the Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            Scores are individual evaluation criteria within a scorecard. The dashboard provides
            an intuitive interface for creating and configuring scores.
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Step-by-Step Guide</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Access Score Creation:</strong>
                  <p>Open your scorecard and click "Add Score" or edit an existing scorecard.</p>
                </li>
                <li>
                  <strong>Choose Score Type:</strong>
                  <p>Select from available score types:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Sentiment Analysis</li>
                    <li>Content Quality</li>
                    <li>Grammar Check</li>
                    <li>Custom Metrics</li>
                  </ul>
                </li>
                <li>
                  <strong>Configure Parameters:</strong>
                  <p>Set up the score configuration:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Score name and description</li>
                    <li>Weight (importance in overall scorecard)</li>
                    <li>Threshold (minimum acceptable score)</li>
                    <li>Custom parameters specific to the score type</li>
                  </ul>
                </li>
                <li>
                  <strong>Preview and Test:</strong>
                  <p>Use the preview feature to test the score against sample content.</p>
                </li>
                <li>
                  <strong>Save Score:</strong>
                  <p>Click "Add Score" to include it in your scorecard.</p>
                </li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-3">Editing Existing Scores</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Locate the Score:</strong>
                  <p>Find the score you want to modify within your scorecard.</p>
                </li>
                <li>
                  <strong>Access Edit Mode:</strong>
                  <p>Click the edit icon next to the score.</p>
                </li>
                <li>
                  <strong>Modify Settings:</strong>
                  <p>Update the score's configuration as needed.</p>
                </li>
                <li>
                  <strong>Save Changes:</strong>
                  <p>Click "Save" to apply your modifications.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Score Configuration Tips</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Weight Balancing</h3>
              <p className="text-muted-foreground">
                Carefully consider the relative importance of each score when setting weights.
                The total of all weights in a scorecard should equal 1.0.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Threshold Setting</h3>
              <p className="text-muted-foreground">
                Set appropriate thresholds based on your quality requirements and test
                with representative content samples.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Score Types</h3>
              <p className="text-muted-foreground">
                Choose score types that align with your evaluation goals. Combine different
                types to create comprehensive assessments.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using the CLI</h2>
          <p className="text-muted-foreground mb-4">
            For automated score management, you can use the Plexus CLI:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Get information about a specific score
plexus scores info --score "Quality Score"

# List all scores in a scorecard
plexus scores list --scorecard "Quality Assurance"

# View score configuration
plexus scores info --score "Grammar Check"`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            The Plexus CLI uses a flexible identifier system that allows you to reference scores and scorecards using different types of identifiers:
          </p>
          
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li>For scores:
              <ul className="list-disc pl-6 mt-2">
                <li>By name: <code>--score "Grammar Check"</code></li>
                <li>By key: <code>--score grammar-check</code></li>
                <li>By ID: <code>--score 7a9b2c3d-4e5f-6g7h-8i9j-0k1l2m3n4o5p</code></li>
                <li>By external ID: <code>--score gc-001</code></li>
              </ul>
            </li>
            <li className="mt-2">For scorecards:
              <ul className="list-disc pl-6 mt-2">
                <li>By name: <code>--scorecard "Quality Assurance"</code></li>
                <li>By key: <code>--scorecard quality-assurance</code></li>
                <li>By ID: <code>--scorecard e51cd5ec-1940-4d8e-abcc-faa851390112</code></li>
                <li>By external ID: <code>--scorecard qa-2023</code></li>
              </ul>
            </li>
          </ul>
          
          <p className="text-muted-foreground">
            For more details on using the CLI, see the <a href="/documentation/advanced/cli" className="text-primary hover:underline">CLI documentation</a>.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic score management, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Get a scorecard using any identifier (name, key, ID, or external ID)
scorecard = plexus.scorecards.get("Quality Assurance")

# Get a score using any identifier
score = plexus.scores.get("Grammar Check")

# Get all scores in a scorecard
scores = scorecard.get_scores()

# Get score configuration
config = score.get_configuration()

# Get score evaluation results
results = score.get_results(limit=10)`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Like the CLI, the Python SDK also supports the flexible identifier system, allowing you to reference resources using different types of identifiers.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional score features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>New score types and metrics</li>
            <li>Advanced scoring algorithms</li>
            <li>Custom evaluation parameters</li>
            <li>Score performance analytics</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 