export default function MonitorTasksPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Monitor Tasks</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to track and manage tasks in your Plexus deployment.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Task Monitoring</h2>
          <p className="text-muted-foreground mb-4">
            Tasks represent individual units of work in Plexus, such as evaluations,
            source processing, or model training. Monitoring tasks helps you track progress
            and manage your workflows effectively.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Using the Dashboard</h3>
              <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
                <li>Navigate to the Tasks section</li>
                <li>View active and completed tasks</li>
                <li>Filter tasks by type or status</li>
                <li>Monitor task progress</li>
                <li>View detailed task information</li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the SDK</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# List all tasks
tasks = plexus.tasks.list()

# Get specific task details
task = plexus.tasks.get(task_id="task-id")

# Monitor task status
status = task.get_status()

# Get task results when complete
if status == "completed":
    results = task.get_results()`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Task Management</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Filtering Tasks</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Filter tasks by type and status
active_evaluations = plexus.tasks.list(
    type="evaluation",
    status="running"
)

# Filter by date range
recent_tasks = plexus.tasks.list(
    start_date="2024-01-01",
    end_date="2024-01-31"
)`}</code>
              </pre>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Task Operations</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Cancel a running task
plexus.tasks.cancel(task_id="task-id")

# Retry a failed task
plexus.tasks.retry(task_id="task-id")

# Delete a completed task
plexus.tasks.delete(task_id="task-id")`}</code>
              </pre>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Task Notifications</h2>
          <p className="text-muted-foreground mb-4">
            Set up notifications to stay informed about task status changes:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Configure task notifications
plexus.tasks.configure_notifications(
    task_id="task-id",
    notifications={
        "on_complete": True,
        "on_error": True,
        "email": "user@example.com"
    }
)`}</code>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation about task monitoring is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced task monitoring features</li>
            <li>Task performance analytics</li>
            <li>Custom notification integrations</li>
            <li>Task automation workflows</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 