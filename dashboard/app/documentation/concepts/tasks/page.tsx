import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { TaskAnimation } from "@/components/landing/TaskAnimation"

export default function TasksPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Tasks</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Understand how Tasks work in Plexus and how our powerful task management system handles your operations efficiently and reliably.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What are Tasks?</h2>
          <p className="text-muted-foreground mb-4">
            Tasks are the backbone of Plexus, serving as the infrastructure that connects all of your organization's 
            operations and team members. At their core, tasks represent commands that operate on Plexus's basic 
            resources—Items, Sources, Scorecards, and Evaluations—and the task management system is how these 
            commands get distributed to worker computers for processing.
          </p>

          <div className="mb-8">
            <TaskAnimation />
          </div>

          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Flexible Access for Different Users</h3>
              <p className="text-muted-foreground mb-4">
                Plexus accommodates different types of users by providing multiple ways to work with tasks:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Command Line Users</strong>: Technical team members can use Plexus's command-line tools 
                  directly, working with YAML configurations and advanced features
                </li>
                <li>
                  <strong>Worker Daemon Users</strong>: Organizations can run Plexus worker daemons that plug into 
                  the task dispatch system, allowing tasks to be managed through the dashboard
                </li>
                <li>
                  <strong>Dashboard Users</strong>: Team members can initiate and monitor tasks entirely through 
                  the web interface, without needing technical expertise
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Common Infrastructure for All</h3>
              <p className="text-muted-foreground mb-4">
                While team members might use different tools based on their roles and expertise, everyone operates 
                on the same underlying infrastructure:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Shared Terminology</strong>: Whether using the dashboard or command line, everyone uses 
                  the same concepts of Items, Sources, Scorecards, and Evaluations
                </li>
                <li>
                  <strong>Unified Business Process</strong>: Data scientists working with data sources, ML engineers 
                  fine-tuning models, and account representatives coordinating with clients all connect through the 
                  same task system
                </li>
                <li>
                  <strong>Seamless Collaboration</strong>: Technical consultants can set up advanced configurations 
                  that non-technical team members can then operate through the dashboard
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Connecting Your Organization</h3>
              <p className="text-muted-foreground">
                The task system serves as the coordination layer that brings together team members with different skills 
                and responsibilities. Whether someone is creating specialized ML models, managing client relationships, 
                or analyzing problem domains, the task system ensures everyone can work together effectively while 
                using the tools that best suit their needs.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">How Tasks Work</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Task Distribution</h3>
              <p className="text-muted-foreground mb-4">
                When you initiate an operation—whether through the dashboard or command line—here's what happens:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  The operation is converted into a task with a unique identifier
                </li>
                <li>
                  Plexus examines the task requirements (like whether it needs GPU access or specific data access)
                </li>
                <li>
                  The task is routed to an appropriate worker computer that can handle those requirements
                </li>
                <li>
                  The worker processes the task and sends back regular progress updates
                </li>
              </ul>
            </div>

            <div className="my-8">
              <TaskAnimation />
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Worker Computers</h3>
              <p className="text-muted-foreground mb-4">
                Worker computers are machines running the Plexus worker daemon. They can be:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Local Machines</strong>: Computers in your office running the worker daemon
                </li>
                <li>
                  <strong>Cloud Servers</strong>: Remote machines set up specifically for processing tasks
                </li>
                <li>
                  <strong>Specialized Hardware</strong>: Machines with GPUs or other specific capabilities
                </li>
              </ul>
              <p className="text-muted-foreground mt-4">
                Each worker advertises its capabilities (like having a GPU or access to certain data), 
                allowing Plexus to route tasks to the most appropriate worker.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Task Communication</h3>
              <p className="text-muted-foreground mb-4">
                Tasks maintain constant communication between the dashboard and workers:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  <strong>Status Updates</strong>: Workers regularly report their progress
                </li>
                <li>
                  <strong>Resource Usage</strong>: Information about CPU, memory, and GPU usage
                </li>
                <li>
                  <strong>Error Reporting</strong>: Detailed information if something goes wrong
                </li>
                <li>
                  <strong>Results Storage</strong>: Completed task results are stored for later access
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Real-Time Progress Tracking</h3>
              <p className="text-muted-foreground mb-4">
                As tasks run, you can monitor their progress in real time. The dashboard shows:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>
                  Progress bars showing overall completion and current stage
                </li>
                <li>
                  Time estimates based on current processing speed
                </li>
                <li>
                  Detailed status messages explaining the current operation
                </li>
                <li>
                  Performance metrics like items processed per second
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Task Lifecycle</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">1. Creation</h3>
              <p className="text-muted-foreground">
                Tasks are created when you initiate operations through the dashboard. Each task is assigned a unique ID 
                and configured based on your requirements.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">2. Queuing</h3>
              <p className="text-muted-foreground">
                Tasks are intelligently queued and distributed to specialized worker nodes. Our system matches tasks 
                with workers that have the right capabilities (like GPU access for intensive operations).
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">3. Execution</h3>
              <p className="text-muted-foreground">
                Worker nodes process tasks and provide continuous updates. You can monitor progress in real-time 
                through the dashboard, with detailed status information at each stage.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">4. Completion</h3>
              <p className="text-muted-foreground">
                When processing finishes, tasks are marked as complete and their results are stored securely. 
                You can access these results through the dashboard for review and analysis.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Related Topics</h2>
          <div className="space-y-4">
            <p className="text-muted-foreground mb-4">
              To learn more about how tasks work in Plexus, check out these related topics:
            </p>
            <div className="flex gap-4">
              <Link href="/documentation/worker-nodes">
                <DocButton>Worker Nodes</DocButton>
              </Link>
              <Link href="/documentation/methods/monitor-tasks">
                <DocButton variant="outline">Task Monitoring Guide</DocButton>
              </Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
} 