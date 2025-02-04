export default function TasksPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Tasks</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Understand how Tasks work in Plexus and how to manage your evaluation workflows.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Tasks?</h2>
          <p className="text-muted-foreground mb-4">
            Tasks are individual units of work in Plexus that represent operations like
            evaluations, source processing, or model training. They help you track and
            manage the progress of your workflows.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Task Lifecycle</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">1. Creation</h3>
              <p className="text-muted-foreground">
                Tasks are created when you initiate operations like evaluations or source processing.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">2. Queuing</h3>
              <p className="text-muted-foreground">
                Tasks are queued and distributed to available worker nodes for processing.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">3. Execution</h3>
              <p className="text-muted-foreground">
                Worker nodes process tasks and update their status in real-time.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">4. Completion</h3>
              <p className="text-muted-foreground">
                Tasks are marked as complete when processing finishes, with results available
                for review.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation about Tasks is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Task monitoring and management</li>
            <li>Error handling and retries</li>
            <li>Task prioritization</li>
            <li>Advanced task configurations</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 