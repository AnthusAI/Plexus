/**
 * POST /api/console/procedure-clone-state
 *
 * Copies optimizer State from a source procedure to a target procedure,
 * truncated to the first N cycles.  Used by the "Branch from cycle N" UI
 * action: the target gets a populated State (so continuation detection fires)
 * but empty checkpoints (so Tactus runs fresh from cycle N+1).
 *
 * The caller is responsible for creating the target Procedure record before
 * calling this route.
 */
import { spawn } from "child_process"
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function isValidId(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value.trim())
}

export async function POST(request: NextRequest) {
  let payload: unknown
  try {
    payload = await request.json()
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON payload" }, { status: 400 })
  }

  const sourceProcedureId = (payload as { sourceProcedureId?: unknown })?.sourceProcedureId
  const targetProcedureId = (payload as { targetProcedureId?: unknown })?.targetProcedureId
  const truncateToCycle = (payload as { truncateToCycle?: unknown })?.truncateToCycle

  if (!isValidId(sourceProcedureId) || !isValidId(targetProcedureId)) {
    return NextResponse.json(
      { ok: false, error: "sourceProcedureId and targetProcedureId must be UUIDs" },
      { status: 400 },
    )
  }
  if (typeof truncateToCycle !== "number" || !Number.isInteger(truncateToCycle) || truncateToCycle < 0) {
    return NextResponse.json(
      { ok: false, error: "truncateToCycle must be a non-negative integer" },
      { status: 400 },
    )
  }

  const result = await new Promise<{ ok: boolean; error?: string }>((resolve) => {
    const child = spawn(
      "plexus",
      [
        "procedure", "clone-state",
        sourceProcedureId.trim(),
        targetProcedureId.trim(),
        "--truncate-to-cycle", String(truncateToCycle),
      ],
      { stdio: ["ignore", "pipe", "pipe"] },
    )
    let stderr = ""
    child.stderr?.on("data", (chunk: Buffer) => { stderr += chunk.toString() })
    child.on("close", (code) => {
      if (code === 0) {
        resolve({ ok: true })
      } else {
        resolve({ ok: false, error: `clone-state exited ${code}: ${stderr.slice(0, 300)}` })
      }
    })
    child.on("error", (err) => resolve({ ok: false, error: err.message }))
  })

  if (!result.ok) {
    return NextResponse.json(
      { ok: false, error: `Failed to clone state: ${result.error}` },
      { status: 500 },
    )
  }

  return NextResponse.json({
    ok: true,
    sourceProcedureId: sourceProcedureId.trim(),
    targetProcedureId: targetProcedureId.trim(),
    truncateToCycle,
  })
}
