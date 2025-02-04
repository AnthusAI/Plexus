export default function CliPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
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
            configuring worker nodes, and monitoring tasks.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Installation</h2>
          <p className="text-muted-foreground mb-4">
            Install the Plexus CLI tool using pip:
          </p>
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>pip install plexus-cli</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed CLI documentation is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Complete command reference</li>
            <li>Configuration guides</li>
            <li>Common usage patterns</li>
            <li>Advanced features</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 