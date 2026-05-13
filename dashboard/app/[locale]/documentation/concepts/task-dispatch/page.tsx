export default function TaskDispatchPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Task Dispatch System</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to operate, monitor, and utilize Plexus's task dispatch system for distributed AI operations.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Operating Worker Nodes</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Starting a Worker</h3>
              <p className="text-muted-foreground mb-4">
                Worker nodes can be started using the Plexus CLI. Make sure you're in the correct directory with access to your scorecards:
              </p>
              <div className="bg-muted p-4 rounded-md">
                <code className="text-sm">plexus command worker --concurrency=4 --loglevel=INFO</code>
              </div>
              <p className="text-sm text-muted-foreground mt-2">
                Adjust concurrency based on your system's capabilities.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Required Configuration</h3>
              <p className="text-muted-foreground mb-4">
                Workers require the following environment variables:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li><code className="text-sm">CELERY_AWS_ACCESS_KEY_ID</code>: AWS access key for SQS</li>
                <li><code className="text-sm">CELERY_AWS_SECRET_ACCESS_KEY</code>: AWS secret key for SQS</li>
                <li><code className="text-sm">CELERY_AWS_REGION_NAME</code>: AWS region for SQS</li>
                <li><code className="text-sm">CELERY_RESULT_BACKEND_TEMPLATE</code>: DynamoDB backend URL</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Worker Specialization</h3>
              <p className="text-muted-foreground">
                Workers can be specialized for specific tasks using target patterns:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-2">
                <li><code className="text-sm">datasets/call-criteria</code>: Dataset processing</li>
                <li><code className="text-sm">training/call-criteria</code>: Model training</li>
                <li><code className="text-sm">*/gpu-required</code>: GPU operations</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using the Dashboard UI</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Dispatching Tasks</h3>
              <p className="text-muted-foreground">
                Tasks can be dispatched through various dashboard interfaces:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-2">
                <li>Evaluation pages for running evaluations</li>
                <li>Source processing for data ingestion</li>
                <li>Model training interfaces</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Monitoring Progress</h3>
              <p className="text-muted-foreground">
                Track task progress through the dashboard:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-2">
                <li>Real-time status updates</li>
                <li>Progress bars with completion estimates</li>
                <li>Detailed logs and error messages</li>
                <li>Task history and results</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">CLI Features</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Dispatching Tasks</h3>
              <p className="text-muted-foreground mb-4">
                Use the CLI to dispatch tasks directly:
              </p>
              <div className="bg-muted p-4 rounded-md space-y-2">
                <code className="text-sm block">
                  # Run demo task synchronously<br/>
                  plexus command demo
                </code>
                <code className="text-sm block">
                  # Run evaluation asynchronously<br/>
                  plexus command dispatch "evaluate accuracy --scorecard agent-scorecard --number-of-samples 10"
                </code>
              </div>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Monitoring Tasks</h3>
              <p className="text-muted-foreground mb-4">
                Monitor task status and progress:
              </p>
              <div className="bg-muted p-4 rounded-md">
                <code className="text-sm">plexus command status &lt;task-id&gt;</code>
              </div>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Best Practices</h2>
          <div className="space-y-2">
            <p className="text-muted-foreground">
              Follow these guidelines for optimal task dispatch operation:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
              <li>Configure appropriate concurrency levels for your hardware</li>
              <li>Use worker specialization for resource-intensive tasks</li>
              <li>Monitor worker health and resource usage</li>
              <li>Set up proper logging for troubleshooting</li>
              <li>Implement appropriate error handling in your workflows</li>
            </ul>
          </div>
        </section>
      </div>
    </div>
  )
} 