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
            <code>{`# Add a new score to a scorecard
plexus scores add --scorecard-id "card-id" --name "Quality Score" --type quality --weight 0.5

# Update an existing score
plexus scores update score-id --weight 0.6 --threshold 0.8

# Remove a score
plexus scores delete score-id`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic score management, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Add a new score to a scorecard
scorecard = plexus.scorecards.get("card-id")
score = scorecard.add_score(
    name="Quality Score",
    type="quality",
    weight=0.5,
    threshold=0.8,
    parameters={
        "check_grammar": True,
        "check_style": True
    }
)

# Update a score
score.update(weight=0.6, threshold=0.85)

# Remove a score
score.delete()`}</code>
          </pre>
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