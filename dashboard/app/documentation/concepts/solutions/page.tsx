export default function SolutionsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Solutions</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Discover how Plexus's powerful and flexible features can transform your AI operations.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Powerful Task Dispatch System</h2>
          <p className="text-muted-foreground mb-4">
            Plexus features a sophisticated two-level dispatch system that seamlessly connects your applications to distributed worker nodes, enabling efficient execution of AI operations at any scale.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            <div className="rounded-lg p-6 shadow-none border-none bg-card">
              <h3 className="text-xl font-medium mb-3">Flexible Architecture</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Two-level dispatch system for optimal task distribution</li>
                <li>Support for both synchronous and asynchronous operations</li>
                <li>Real-time progress tracking and status updates</li>
                <li>Configurable worker pools for specialized tasks</li>
              </ul>
            </div>
            <div className="rounded-lg p-6 shadow-none border-none bg-card">
              <h3 className="text-xl font-medium mb-3">Enterprise-Ready</h3>
              <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
                <li>Built on proven AWS infrastructure</li>
                <li>Automatic scaling and load balancing</li>
                <li>Comprehensive monitoring and logging</li>
                <li>Robust error handling and recovery</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Key Features</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">Worker Specialization</h3>
              <p className="text-muted-foreground">
                Target specific workers for specialized tasks using a flexible pattern matching system. Direct GPU-intensive operations to capable nodes while routing data processing to optimized instances.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-3">Progress Tracking</h3>
              <p className="text-muted-foreground">
                Monitor task progress in real-time with detailed status updates, estimated completion times, and performance metrics. Perfect for long-running AI operations.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-3">Resource Management</h3>
              <p className="text-muted-foreground">
                Efficiently manage system resources with configurable worker pools, automatic task distribution, and intelligent queue management.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Integration Options</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="rounded-lg p-6 shadow-none border-none bg-card">
              <h3 className="text-xl font-medium mb-3">Dashboard UI</h3>
              <p className="text-muted-foreground">
                Modern web interface for task management, monitoring, and control.
              </p>
            </div>
            <div className="rounded-lg p-6 shadow-none border-none bg-card">
              <h3 className="text-xl font-medium mb-3">CLI Tools</h3>
              <p className="text-muted-foreground">
                Powerful command-line tools for automation and scripting.
              </p>
            </div>
            <div className="rounded-lg p-6 shadow-none border-none bg-card">
              <h3 className="text-xl font-medium mb-3">Python SDK</h3>
              <p className="text-muted-foreground">
                Native Python integration for seamless development workflows.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
} 