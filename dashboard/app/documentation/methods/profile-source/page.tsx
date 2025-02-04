export default function ProfileSourcePage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Profile a Source</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to analyze and profile your sources using the Plexus dashboard interface.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Profiling Sources in the Dashboard</h2>
          <p className="text-muted-foreground mb-4">
            Source profiling helps you understand the characteristics and patterns in your data
            before running evaluations. The dashboard provides comprehensive tools for analyzing
            your sources.
          </p>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Step-by-Step Guide</h3>
              <ol className="list-decimal pl-6 space-y-3 text-muted-foreground">
                <li>
                  <strong>Access Source Details:</strong>
                  <p>Navigate to your source in the Sources list and click on it to view details.</p>
                </li>
                <li>
                  <strong>Start Profiling:</strong>
                  <p>Click the "Profile Source" button in the source details view.</p>
                </li>
                <li>
                  <strong>Configure Analysis:</strong>
                  <p>Select the profiling options you want to run:</p>
                  <ul className="list-disc pl-6 mt-2 space-y-2">
                    <li>Content analysis</li>
                    <li>Pattern detection</li>
                    <li>Quality metrics</li>
                    <li>Custom analysis options</li>
                  </ul>
                </li>
                <li>
                  <strong>Run Profile:</strong>
                  <p>Click "Start Analysis" to begin the profiling process.</p>
                </li>
                <li>
                  <strong>Review Results:</strong>
                  <p>Once complete, examine the detailed profiling results in the dashboard.</p>
                </li>
              </ol>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Profile Results</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Content Analysis</h3>
              <p className="text-muted-foreground">
                View detailed breakdowns of your source content, including structure, format,
                and key characteristics. The dashboard presents this information through
                interactive visualizations and detailed reports.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Pattern Detection</h3>
              <p className="text-muted-foreground">
                Explore identified patterns and anomalies through the dashboard's pattern
                analysis view. This helps you understand common themes and potential issues
                in your content.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Quality Metrics</h3>
              <p className="text-muted-foreground">
                Review comprehensive quality measurements through intuitive charts and
                detailed metric breakdowns in the dashboard interface.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Profile Management Tips</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Saving Profiles</h3>
              <p className="text-muted-foreground">
                Save profile configurations as templates for quick reuse across multiple sources.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Comparing Results</h3>
              <p className="text-muted-foreground">
                Use the dashboard's comparison view to analyze profile results across different
                sources or time periods.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using the CLI</h2>
          <p className="text-muted-foreground mb-4">
            For automated profiling workflows, you can use the Plexus CLI:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Run a profile on a source
plexus sources profile source-id --analysis-type full

# Get profile results
plexus sources profile-results source-id`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Python SDK Reference</h2>
          <p className="text-muted-foreground mb-4">
            For programmatic profiling, you can use the Python SDK:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Run a profile on a source
profile = plexus.sources.profile(
    source_id="source-id",
    options={
        "content_analysis": True,
        "pattern_detection": True,
        "quality_metrics": True
    }
)

# Get profile results
results = profile.get_results()`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Additional profiling features are being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced visualization options</li>
            <li>Custom profiling templates</li>
            <li>Automated insights generation</li>
            <li>Profile sharing and collaboration</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 