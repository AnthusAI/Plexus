export default function EvaluationsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Evaluations</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn about the evaluation process and how to analyze your content using Plexus.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Evaluations?</h2>
          <p className="text-muted-foreground mb-4">
            Evaluations are the process of analyzing your sources using scorecards to generate
            insights and ensure quality. Each evaluation applies a scorecard's criteria to
            assess specific aspects of your content.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Evaluation Process</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">1. Initialization</h3>
              <p className="text-muted-foreground">
                Select a source and scorecard to begin the evaluation process.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">2. Processing</h3>
              <p className="text-muted-foreground">
                Plexus analyzes your content using AI models based on the scorecard criteria.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">3. Results</h3>
              <p className="text-muted-foreground">
                Review detailed results and insights from the evaluation.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation about Evaluations is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Step-by-step evaluation guides</li>
            <li>Understanding evaluation results</li>
            <li>Batch evaluation processes</li>
            <li>Advanced evaluation configurations</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 