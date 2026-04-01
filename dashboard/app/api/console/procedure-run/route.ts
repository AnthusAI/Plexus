import { spawn } from "child_process"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const BUILTIN_PROCEDURE_RE = /^builtin:[a-z0-9][a-z0-9/_-]*$/i

function isValidId(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value.trim())
}

function isValidProcedureId(value: unknown): value is string {
  if (typeof value !== "string") {
    return false
  }
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
      { accepted: false, error: "taskId must be a UUID and procedureId must be a UUID or builtin:* key" },
      { status: 400 },
    )
  }
  const normalizedProcedureId = procedureId.trim()
  const normalizedTaskId = taskId.trim()

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
