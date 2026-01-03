import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Examples & Patterns - Procedures - Plexus Documentation",
  description: "Real-world examples of Plexus Procedures from simple to complex"
}

export default function ProceduresExamplesPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Examples & Patterns</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Real-world examples from simple tasks to complex multi-stage workflows.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Simple Research Task</h2>
          <div className="flex gap-2 mb-4">
            <span className="inline-block bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-100 text-xs px-2 py-1 rounded">Beginner</span>
            <span className="inline-block bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 text-xs px-2 py-1 rounded">Single Agent</span>
          </div>
          <p className="text-muted-foreground mb-4">
            A straightforward procedure that researches a topic and returns findings.
          </p>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4 text-sm">
              <code>{`name: simple_researcher
version: 1.0.0

params:
  topic:
    type: string
    required: true

outputs:
  summary:
    type: string
    required: true

agents:
  researcher:
    system_prompt: |
      Research: {params.topic}
      Use search tool, provide summary.
    tools: [search, done]
    max_turns: 10

return_prompt: |
  Provide research summary.

workflow: |
  repeat
    Researcher.turn()
  until Tool.called("done") or Iterations.exceeded(10)

  return {
    summary = State.get("summary") or "No summary"
  }`}</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Content Pipeline with HITL</h2>
          <div className="flex gap-2 mb-4">
            <span className="inline-block bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-100 text-xs px-2 py-1 rounded">Intermediate</span>
            <span className="inline-block bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 text-xs px-2 py-1 rounded">HITL</span>
            <span className="inline-block bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 text-xs px-2 py-1 rounded">Multi-Stage</span>
          </div>
          <p className="text-muted-foreground mb-4">
            Generate content, review with human, and publish with approval.
          </p>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4 text-sm">
              <code>{`name: content_pipeline
version: 1.0.0

params:
  topic:
    type: string
    required: true

outputs:
  published:
    type: boolean
    required: true

stages:
  - drafting
  - review
  - publishing

hitl:
  review_content:
    type: review
    message: "Review content"
    timeout: 86400

  confirm_publish:
    type: approval
    message: "Publish?"
    timeout: 3600

agents:
  writer:
    system_prompt: "Write about: {params.topic}"
    tools: [research, write, done]

workflow: |
  -- Generate
  Stage.set("drafting")
  Human.notify({message = "Generating content"})

  repeat
    Writer.turn()
  until Tool.called("done")

  -- Human review
  Stage.set("review")
  local review = Human.review("review_content", {
    artifact = State.get("draft")
  })

  if review.decision == "reject" then
    return {published = false}
  end

  -- Publish
  Stage.set("publishing")
  local approved = Human.approve("confirm_publish")

  if approved then
    publish(review.edited_artifact or State.get("draft"))
    return {published = true}
  else
    return {published = false}
  end`}</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Parallel Research</h2>
          <div className="flex gap-2 mb-4">
            <span className="inline-block bg-orange-100 dark:bg-orange-900 text-orange-800 dark:text-orange-100 text-xs px-2 py-1 rounded">Intermediate</span>
            <span className="inline-block bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 text-xs px-2 py-1 rounded">Async</span>
            <span className="inline-block bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 text-xs px-2 py-1 rounded">Parallel</span>
          </div>
          <p className="text-muted-foreground mb-4">
            Research multiple topics in parallel and aggregate results.
          </p>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4 text-sm">
              <code>{`name: parallel_researcher
version: 1.0.0

params:
  topics:
    type: array
    required: true

outputs:
  results:
    type: array
    required: true

procedures:
  researcher:
    params:
      topic:
        type: string
        required: true

    outputs:
      findings:
        type: string
        required: true

    agents:
      worker:
        system_prompt: "Research: {params.topic}"
        tools: [search, done]

    workflow: |
      repeat
        Worker.turn()
      until Tool.called("done")

      return {findings = State.get("findings")}

workflow: |
  -- Spawn researchers in parallel
  local handles = {}
  for _, topic in ipairs(params.topics) do
    local handle = Procedure.spawn("researcher", {
      topic = topic
    })
    table.insert(handles, handle)
  end

  -- Wait for all
  Procedure.wait_all(handles)

  -- Collect results
  local results = {}
  for _, handle in ipairs(handles) do
    local result = Procedure.result(handle)
    table.insert(results, result)
  end

  return {results = results}`}</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Deployment Pipeline</h2>
          <div className="flex gap-2 mb-4">
            <span className="inline-block bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-100 text-xs px-2 py-1 rounded">Advanced</span>
            <span className="inline-block bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 text-xs px-2 py-1 rounded">HITL</span>
            <span className="inline-block bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-100 text-xs px-2 py-1 rounded">Multi-Stage</span>
          </div>
          <p className="text-muted-foreground mb-4">
            Complete deployment pipeline with verification and rollback.
          </p>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4 text-sm">
              <code>{`name: deployment_pipeline
version: 1.0.0

params:
  version:
    type: string
    required: true
  environment:
    type: string
    enum: [staging, production]
    required: true

outputs:
  deployed:
    type: boolean
    required: true

stages:
  - preparing
  - testing
  - approval
  - deploying
  - verifying

hitl:
  approve_deployment:
    type: approval
    message: "Deploy {params.version} to {params.environment}?"
    timeout: 1800

  approve_rollback:
    type: approval
    message: "Verification failed. Rollback?"
    timeout: 600
    default: true

workflow: |
  -- Prepare
  Stage.set("preparing")
  Human.notify({message = "Preparing deployment"})

  local build_ok = build_artifacts(params.version)
  if not build_ok then
    System.alert({
      message = "Build failed",
      level = "error",
      source = "deployment_pipeline"
    })
    return {deployed = false}
  end

  -- Test
  Stage.set("testing")
  local tests_ok = run_tests()
  if not tests_ok then
    return {deployed = false}
  end

  -- Approval
  Stage.set("approval")
  local approved = Human.approve("approve_deployment", {
    context = {
      version = params.version,
      risk_level = params.environment == "production"
        and "high" or "medium"
    }
  })

  if not approved then
    return {deployed = false}
  end

  -- Deploy
  Stage.set("deploying")
  local deploy_ok, url = deploy(params.version, params.environment)

  if not deploy_ok then
    System.alert({
      message = "Deployment failed",
      level = "critical",
      source = "deployment_pipeline"
    })
    return {deployed = false}
  end

  -- Verify
  Stage.set("verifying")
  Sleep(30)
  local verify_ok = verify_deployment(url)

  if not verify_ok then
    local rollback = Human.approve("approve_rollback")
    if rollback then
      rollback_deployment(params.environment)
      return {deployed = false}
    end
  end

  Human.notify({message = "Deployment successful"})
  return {deployed = true}`}</code>
            </div>
          </pre>
        </section>

        <section className="bg-muted rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-4">More Examples</h2>
          <p className="text-muted-foreground mb-4">
            Complete HTML documentation with 8 detailed examples is available at:
          </p>
          <code className="block bg-background px-4 py-2 rounded text-sm mb-4">
            /plexus/procedures/docs/examples.html
          </code>
          <p className="text-muted-foreground">
            Includes examples for: data processing, recursive task decomposition,
            batch processing with monitoring, and multi-agent workflows.
          </p>
        </section>

        <div className="flex gap-4 mt-8">
          <Link href="/documentation/procedures/api">
            <DocButton>Next: API Reference →</DocButton>
          </Link>
          <Link href="/documentation/procedures/hitl">
            <DocButton variant="outline">← Human-in-the-Loop</DocButton>
          </Link>
        </div>
      </div>
    </div>
  )
}
