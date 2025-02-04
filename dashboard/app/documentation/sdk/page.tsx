export default function SdkPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Python SDK Reference</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Explore the Python SDK for programmatic access to Plexus functionality.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <p className="text-muted-foreground mb-4">
            The Plexus Python SDK provides a simple and intuitive way to interact with Plexus
            programmatically. Use it to automate workflows, manage resources, and integrate
            Plexus into your applications.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Installation</h2>
          <p className="text-muted-foreground mb-4">
            Install the Plexus SDK using pip:
          </p>
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>pip install plexus-sdk</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Quick Start</h2>
          <p className="text-muted-foreground mb-4">
            Here's a simple example to get you started:
          </p>
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`from plexus import Plexus

# Initialize the client
plexus = Plexus(api_key="your-api-key")

# Create a new source
source = plexus.sources.create(
    name="My Source",
    type="text",
    data="Sample content"
)

# Run an evaluation
evaluation = plexus.evaluations.create(
    source_id=source.id,
    scorecard_id="your-scorecard-id"
)`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed SDK documentation is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Complete API reference</li>
            <li>Authentication guides</li>
            <li>Advanced usage examples</li>
            <li>Best practices</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 