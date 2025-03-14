export default function EvaluateScorePage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Evaluate a Score</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to run evaluations using individual scores or complete scorecards.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Running an Evaluation</h2>
          <p className="text-muted-foreground mb-4">
            You can evaluate content using individual scores or entire scorecards. The evaluation
            process analyzes your content against the defined criteria and provides detailed results.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Using the Dashboard</h3>
              <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
                <li>Select your source content</li>
                <li>Choose a scorecard or individual score</li>
                <li>Click "Run Evaluation"</li>
                <li>Monitor the evaluation progress</li>
                <li>Review the results</li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the SDK</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Evaluate using a specific score (accepts ID, name, key, or external ID)
evaluation = plexus.evaluations.create(
    source_id="source-id",
    score="Grammar Check"  # Can use name, key, ID, or external ID
)

# Or evaluate using an entire scorecard (accepts ID, name, key, or external ID)
evaluation = plexus.evaluations.create(
    source_id="source-id",
    scorecard="Content Quality"  # Can use name, key, ID, or external ID
)

# Get evaluation results
results = evaluation.get_results()

# Print score values
for score in results.scores:
    print(f"{score.name}: {score.value}")`}</code>
              </pre>
              
              <p className="text-muted-foreground mb-4">
                The SDK supports the flexible identifier system, allowing you to reference scorecards and scores using different types of identifiers (name, key, ID, or external ID).
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the CLI</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Evaluate using a scorecard
plexus evaluate accuracy --scorecard "Content Quality" --number-of-samples 100

# List evaluation results
plexus evaluations list

# View detailed results for a specific evaluation
plexus evaluations list-results --evaluation evaluation-id`}</code>
              </pre>
              
              <p className="text-muted-foreground mb-4">
                The CLI supports the flexible identifier system, allowing you to reference scorecards using different types of identifiers (name, key, ID, or external ID).
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Results</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Score Values</h3>
              <p className="text-muted-foreground">
                Numerical or categorical results for each evaluated criterion.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Explanations</h3>
              <p className="text-muted-foreground">
                Detailed reasoning behind each score's evaluation result.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Suggestions</h3>
              <p className="text-muted-foreground">
                Recommendations for improvement based on the evaluation results.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Batch Evaluations</h2>
          <p className="text-muted-foreground mb-4">
            You can evaluate multiple sources at once using batch processing:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Create a batch evaluation
batch = plexus.evaluations.create_batch(
    source_ids=["source-1", "source-2", "source-3"],
    scorecard="Quality Assurance"  # Can use name, key, ID, or external ID
)

# Monitor batch progress
status = batch.get_status()

# Get results when complete
results = batch.get_results()`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Like individual evaluations, batch evaluations also support the flexible identifier system for scorecards and scores.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation about evaluations is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced evaluation options</li>
            <li>Custom result formatting</li>
            <li>Evaluation performance optimization</li>
            <li>Result analysis techniques</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 