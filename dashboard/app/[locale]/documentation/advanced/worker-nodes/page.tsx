'use client';

export default function WorkerNodesPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <style jsx>{`
        .code-container {
          position: relative;
          overflow-x: auto;
          white-space: pre;
          -webkit-overflow-scrolling: touch;
        }
        
        .code-container::after {
          content: '';
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          width: 16px;
          background: linear-gradient(to right, transparent, var(--background-muted));
          opacity: 0;
          transition: opacity 0.2s;
          pointer-events: none;
        }
        
        .code-container:hover::after {
          opacity: 1;
        }
      `}</style>

      <h1 className="text-4xl font-bold mb-4">Worker Nodes</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to deploy and manage Plexus worker nodes across any infrastructure to process your evaluation tasks.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <p className="text-muted-foreground mb-4">
            Plexus worker nodes are long-running daemon processes that handle evaluation tasks and other operations. 
            You can run these workers on any computer with Python installed - whether it's in the cloud (AWS, Azure, GCP) 
            or on your own premises.
          </p>
          <p className="text-muted-foreground mb-4">
            Workers are managed using the Plexus CLI tool, which makes it easy to start, configure, and monitor worker 
            processes across your infrastructure.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Starting a Worker</h2>
          <p className="text-muted-foreground mb-4">
            Use the <code>plexus command worker</code> command to start a worker process. Here's a basic example:
          </p>
          
          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
              <code>{`plexus command worker \\
  --concurrency 4 \\
  --queue celery \\
  --loglevel INFO`}</code>
            </div>
          </pre>

          <div className="pl-4 space-y-2 text-muted-foreground mb-6">
            <p><code>--concurrency</code>: Number of worker processes (default: 4)</p>
            <p><code>--queue</code>: Queue to process (default: celery)</p>
            <p><code>--loglevel</code>: Logging level (default: INFO)</p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Worker Specialization</h2>
          <p className="text-muted-foreground mb-4">
            Workers can be specialized to handle specific types of tasks using target patterns. This allows you to 
            dedicate certain workers to particular workloads:
          </p>

          <pre className="bg-muted rounded-lg mb-4">
            <div className="code-container p-4">
              <code>{`# Worker that only processes dataset-related tasks
plexus command worker \\
  --target-patterns "datasets/*" \\
  --concurrency 4

# Worker for GPU-intensive tasks
plexus command worker \\
  --target-patterns "*/gpu-required" \\
  --concurrency 2

# Worker handling multiple task types
plexus command worker \\
  --target-patterns "datasets/*,training/*" \\
  --concurrency 8`}</code>
            </div>
          </pre>

          <p className="text-muted-foreground mt-4">
            Target patterns use the format <code>domain/subdomain</code> and support wildcards. Some examples:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-2">
            <li><code>datasets/call-criteria</code> - Only process call criteria dataset tasks</li>
            <li><code>training/call-criteria</code> - Only handle call criteria training tasks</li>
            <li><code>*/gpu-required</code> - Process any tasks requiring GPU resources</li>
            <li><code>datasets/*</code> - Handle all dataset-related tasks</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Deployment Examples</h2>
          <p className="text-muted-foreground mb-4">
            Here are some common deployment scenarios:
          </p>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-2">AWS EC2</h3>
              <pre className="bg-muted rounded-lg mb-2">
                <div className="code-container p-4">
                  <code>{`# Run in a screen session for persistence
screen -S plexus-worker
plexus command worker \\
  --concurrency 8 \\
  --loglevel INFO
# Ctrl+A, D to detach`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Local Development</h3>
              <pre className="bg-muted rounded-lg mb-2">
                <div className="code-container p-4">
                  <code>{`# Run with increased logging for debugging
plexus command worker \\
  --concurrency 2 \\
  --loglevel DEBUG`}</code>
                </div>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">GPU Worker</h3>
              <pre className="bg-muted rounded-lg mb-2">
                <div className="code-container p-4">
                  <code>{`# Dedicated GPU worker with specific targeting
plexus command worker \\
  --concurrency 1 \\
  --target-patterns "*/gpu-required" \\
  --loglevel INFO`}</code>
                </div>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Best Practices</h2>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Use a process manager (like systemd, supervisor, or screen) to keep workers running</li>
            <li>Set concurrency based on available CPU cores and memory</li>
            <li>Use target patterns to optimize resource utilization</li>
            <li>Monitor worker logs for errors and performance issues</li>
            <li>Deploy workers close to your data sources when possible</li>
            <li>Consider using auto-scaling groups in cloud environments</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Additional Resources</h2>
          <p className="text-muted-foreground">
            For more information about worker deployment and management:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>See the <a href="/documentation/advanced/cli" className="text-primary hover:underline">CLI documentation</a> for detailed command reference</li>
            <li>Check the built-in help with <code>plexus command worker --help</code></li>
            <li>View worker logs with <code>--loglevel DEBUG</code> for troubleshooting</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 