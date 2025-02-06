export default function SourcesPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Sources</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn about Sources in Plexus and how they form the foundation of your evaluation workflows.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Sources?</h2>
          <p className="text-muted-foreground mb-4">
            Sources are the input data that you want to evaluate using Plexus. They can be text,
            audio files, or other supported formats that you want to analyze using AI models.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Types of Sources</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Text Sources</h3>
              <p className="text-muted-foreground">
                Plain text content that can be evaluated for various metrics like sentiment,
                quality, or compliance with specific criteria.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Audio Sources</h3>
              <p className="text-muted-foreground">
                Audio recordings that can be transcribed and analyzed for content,
                quality, or specific patterns.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation about Sources is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Source creation and management</li>
            <li>Supported formats and limitations</li>
            <li>Best practices for organizing sources</li>
            <li>Advanced source configurations</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 