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
            source processing, or model training. You can monitor tasks through both
            the web dashboard and the command line interface.
          </p>
          
          <div className="space-y-8">
            <div>
              <h3 className="text-xl font-medium mb-2">Using the Dashboard</h3>
              <p className="text-muted-foreground mb-4">
                The web dashboard provides a visual interface for monitoring tasks:
              </p>
              <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
                <li>Navigate to the Tasks section in the dashboard</li>
                <li>View active and completed tasks in real-time</li>
                <li>Use filters to find specific tasks by type or status</li>
                <li>Monitor task progress with visual progress bars</li>
                <li>View detailed task information including stages and logs</li>
                <li>Track task performance and resource usage</li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the CLI</h3>
              <p className="text-muted-foreground mb-4">
                The Plexus CLI provides powerful tools for monitoring tasks directly from your terminal:
              </p>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# List tasks for an account (shows 10 most recent by default)
plexus tasks list --account your-account-key

# Show all tasks instead of just the most recent
plexus tasks list --account your-account-key --all

# Filter tasks by status
plexus tasks list --account your-account-key --status RUNNING
plexus tasks list --account your-account-key --status COMPLETED
plexus tasks list --account your-account-key --status FAILED

# Filter tasks by type
plexus tasks list --account your-account-key --type evaluation

# Combine filters
plexus tasks list --account your-account-key --status RUNNING --type evaluation

# Limit the number of tasks shown
plexus tasks list --account your-account-key --limit 5`}</code>
              </pre>
              <p className="text-sm text-muted-foreground mb-4">
                The CLI output displays comprehensive task information in a well-formatted view:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Basic task details (ID, type, status, target, command)</li>
                <li>Associated IDs (account, scorecard, score)</li>
                <li>Current stage and worker information</li>
                <li>Complete timing information (created, started, completed, estimated)</li>
                <li>Color-coded status indicators (blue for running, green for completed, red for failed)</li>
                <li>Error messages and details when available</li>
                <li>Task metadata and output logs</li>
              </ul>
            </div>
          </div>
        </section>

        <section className="border-t-2 border-destructive/10 pt-8">
          <h2 className="text-2xl font-semibold mb-4 text-destructive">Danger Zone: Task Deletion</h2>
          <div className="bg-destructive/5 p-6 rounded-lg border border-destructive/20">
            <p className="text-destructive font-medium mb-4">
              ⚠️ Warning: Task deletion is a permanent operation. Deleted tasks cannot be recovered.
              Only use these commands when you are absolutely certain about the deletion.
            </p>
            
            <div className="space-y-4">
              <p className="text-muted-foreground">
                The CLI provides commands for task deletion with built-in safety measures:
              </p>
              
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Delete a specific task by ID
plexus tasks delete --account your-account-key --task-id "task-id"

# Delete all failed tasks for an account
plexus tasks delete --account your-account-key --status FAILED

# Delete all tasks of a specific type for an account
plexus tasks delete --account your-account-key --type evaluation

# Delete ALL tasks for a specific account
plexus tasks delete --account your-account-key --all

# Delete ALL tasks across ALL accounts (USE WITH EXTREME CAUTION)
plexus tasks delete --all

# Skip confirmation prompt with -y/--yes (USE WITH EXTREME CAUTION)
plexus tasks delete --all -y`}</code>
              </pre>

              <div className="space-y-2 text-sm text-muted-foreground">
                <p>Safety Features:</p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>The <code>--all</code> flag is required for bulk deletion</li>
                  <li>Account scope is clearly indicated in confirmations</li>
                  <li>Confirmation prompt is shown by default (can be skipped with <code>-y</code>)</li>
                  <li>Preview of tasks to be deleted is always shown</li>
                  <li>Associated task stages are automatically cleaned up</li>
                  <li>Progress bar shows deletion status</li>
                </ul>

                <p className="mt-4">Before deleting tasks, consider:</p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Are there any dependent operations that might be affected?</li>
                  <li>Do you need to keep the task records for auditing purposes?</li>
                  <li>Have you backed up any important task results?</li>
                  <li>Are you targeting the correct tasks with your filters?</li>
                  <li>If using <code>--all</code> without <code>--account</code>, are you certain you want to delete tasks across ALL accounts?</li>
                </ul>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
} 