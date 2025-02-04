export default function ScorecardsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Scorecards</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Understand how to create and manage Scorecards to evaluate your content effectively.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Scorecards?</h2>
          <p className="text-muted-foreground mb-4">
            Scorecards are collections of evaluation criteria that define how your content
            should be analyzed. They help ensure consistent evaluation across all your sources.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Components</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Scores</h3>
              <p className="text-muted-foreground">
                Individual evaluation criteria that assess specific aspects of your content.
                Each score can be customized with its own evaluation logic and requirements.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Weights</h3>
              <p className="text-muted-foreground">
                Importance factors that determine how much each score contributes to the
                overall evaluation result.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation about Scorecards is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Scorecard creation workflow</li>
            <li>Score configuration options</li>
            <li>Best practices for scorecard design</li>
            <li>Advanced scoring techniques</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 