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
          <h2 className="text-2xl font-semibold mb-4">Score Version Management</h2>
          <p className="text-muted-foreground mb-4">
            Scores in Plexus support versioning, allowing you to track changes and manage different implementations:
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Creating New Versions</h3>
              <p className="text-muted-foreground">
                When you edit a score and save changes, a new version is automatically created. 
                You can add notes to document the changes made in each version.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Champion Versions</h3>
              <p className="text-muted-foreground">
                Each score has a designated "champion" version that is used for evaluations.
                You can promote any version to champion status when you're satisfied with its performance.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Featured Versions</h3>
              <p className="text-muted-foreground">
                Mark important versions as "featured" to highlight them in the version history.
                This helps track significant milestones in your score's development.
              </p>
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
            <code>{`# View detailed information about a score
plexus scorecards score "Score Name" --account "account-name"
plexus scorecards score "score-key" --account "account-name"

# Show version history and configuration
plexus scorecards score "Score Name" --account "account-name" --show-versions --show-config

# List all scores for a specific scorecard
plexus scorecards list-scores --scorecard-id "scorecard-id"

# Coming soon:
# View version history for a score
plexus scorecards history --account-key "account-key" --score-key "score-key"

# Promote a version to champion
plexus scorecards promote --account-key "account-key" --score-id "score-id" --version-id "version-id"

# Add a new score to a scorecard
plexus scores add --scorecard-id "card-id" --name "Quality Score" --type quality --weight 0.5

# List all scores in a scorecard
plexus scores list --scorecard "Quality Assurance"

# View score configuration
plexus scores info --score "Grammar Check"`}</code>
          </pre>
          
          <div className="mt-4 space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Efficient Score Lookup</h3>
              <p className="text-muted-foreground">
                The <code>score</code> command supports multiple lookup methods:
              </p>
              <ul className="list-disc pl-6 mt-2 space-y-2 text-muted-foreground">
                <li>By ID: <code>plexus scorecards score "score-id"</code></li>
                <li>By key: <code>plexus scorecards score "score-key"</code></li>
                <li>By name: <code>plexus scorecards score "Score Name"</code></li>
                <li>By external ID: <code>plexus scorecards score "external-id"</code></li>
              </ul>
              <p className="text-muted-foreground mt-2">
                You can scope the search to a specific account or scorecard for faster results.
              </p>
            </div>
          </div>
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
          <h2 className="text-2xl font-semibold mb-4">YAML Configuration</h2>
          <p className="text-muted-foreground mb-4">
            Scores can be configured using YAML for advanced customization:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`name: Quality Score
key: quality-score
externalId: score_123
type: LangGraphScore
parameters:
  check_grammar: true
  check_style: true
  min_word_count: 100
threshold: 0.8
weight: 0.5`}</code>
          </pre>
          
          <p className="text-muted-foreground mt-2">
            Coming soon: The ability to pull and push YAML configurations using the CLI for offline editing and version control.
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
            <li>Bulk score operations</li>
            <li>YAML synchronization for offline editing</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 