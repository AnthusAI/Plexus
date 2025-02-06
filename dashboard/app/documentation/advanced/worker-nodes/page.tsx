export default function WorkerNodesPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Worker Nodes</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to connect, configure, and manage Plexus worker nodes for distributed processing.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Overview</h2>
          <p className="text-muted-foreground mb-4">
            Worker nodes are the distributed computing units that power Plexus's scalable AI operations.
            They handle tasks like model inference, data processing, and evaluation workflows.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Getting Started</h2>
          <p className="text-muted-foreground mb-4">
            To begin using worker nodes, you'll need to:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>Set up your environment</li>
            <li>Configure authentication</li>
            <li>Deploy your first worker node</li>
            <li>Monitor node performance</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation for worker nodes is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Step-by-step setup guides</li>
            <li>Configuration options and best practices</li>
            <li>Scaling strategies</li>
            <li>Troubleshooting tips</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 