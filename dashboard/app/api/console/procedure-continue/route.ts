/**
 * POST /api/console/procedure-continue
 *
 * Clears procedure checkpoints (preserving accumulated State) and re-dispatches
 * the procedure so the optimizer resumes from where it left off.
 *
 * The frontend is responsible for updating YAML params (max_iterations, hint)
 * and creating the Task record before calling this route.
 */
import { spawn } from "child_process"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const BUILTIN_PROCEDURE_RE = /^builtin:[a-z0-9][a-z0-9/_-]*$/i

function isValidId(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value.trim())
}

function isValidProcedureId(value: unknown): value is string {
  if (typeof value !== "string") return false
  const trimmed = value.trim()
  return UUID_RE.test(trimmed) || BUILTIN_PROCEDURE_RE.test(trimmed)
}

export async function POST(request: NextRequest) {
  let payload: unknown
  try {
    payload = await request.json()
  } catch {
    return NextResponse.json({ accepted: false, error: "Invalid JSON payload" }, { status: 400 })
  }

  const procedureId = (payload as { procedureId?: unknown })?.procedureId
  const taskId = (payload as { taskId?: unknown })?.taskId

  if (!isValidProcedureId(procedureId) || !isValidId(taskId)) {
    return NextResponse.json(
      {
        accepted: false,
        error: "taskId must be a UUID and procedureId must be a UUID or builtin:* key",
      },
      { status: 400 },
    )
  }

  const normalizedProcedureId = (procedureId as string).trim()
  const normalizedTaskId = (taskId as string).trim()

  // Clear checkpoints only (preserve accumulated State) via plexus CLI.
  // This prevents Tactus from replaying the completed procedure from cache,
  // while keeping the iterations/baseline/dataset State so the optimizer can
  // detect continuation and skip the expensive init phase.
  const resetResult = await new Promise<{ ok: boolean; error?: string }>((resolve) => {
    const resetChild = spawn(
      "plexus",
      ["procedure", "reset", normalizedProcedureId, "--checkpoints-only"],
      { stdio: ["ignore", "pipe", "pipe"] },
    )
    let stderr = ""
    resetChild.stderr?.on("data", (chunk: Buffer) => { stderr += chunk.toString() })
    resetChild.on("close", (code) => {
      if (code === 0) {
        resolve({ ok: true })
      } else {
        resolve({ ok: false, error: `reset exited ${code}: ${stderr.slice(0, 300)}` })
      }
    })
    resetChild.on("error", (err) => resolve({ ok: false, error: err.message }))
  })

  if (!resetResult.ok) {
    return NextResponse.json(
      { accepted: false, error: `Failed to reset checkpoints: ${resetResult.error}` },
      { status: 500 },
    )
  }

  // Dispatch the procedure run (same as /api/console/procedure-run)
  const child = spawn("plexus", ["procedure", "run", normalizedProcedureId, "-o", "json"], {
    env: {
      ...process.env,
      PLEXUS_DISPATCH_TASK_ID: normalizedTaskId,
    },
    stdio: "ignore",
    detached: true,
  })

  try {
    await new Promise<void>((resolve, reject) => {
      child.once("spawn", () => resolve())
      child.once("error", (error) => reject(error))
    })
  } catch (error) {
    return NextResponse.json(
      {
        accepted: false,
        error: error instanceof Error ? error.message : "Failed to launch procedure runner",
      },
      { status: 500 },
    )
  }

  child.unref()
  return NextResponse.json({
    accepted: true,
    taskId: normalizedTaskId,
    procedureId: normalizedProcedureId,
  })
}
