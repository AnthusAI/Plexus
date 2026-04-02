import { spawn } from 'child_process'
import { NextRequest, NextResponse } from 'next/server'

export const runtime = 'nodejs'

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function normalizeFeedbackItemIds(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  const ids = value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0)
  return [...new Set(ids)].sort()
}

function parsePositiveInteger(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed <= 0) return null
  return parsed
}

export async function POST(request: NextRequest) {
  let payload: unknown
  try {
    payload = await request.json()
  } catch {
    return NextResponse.json({ accepted: false, error: 'Invalid JSON payload' }, { status: 400 })
  }

  const taskId = (payload as { taskId?: unknown })?.taskId
  const scorecard = (payload as { scorecard?: unknown })?.scorecard
  const score = (payload as { score?: unknown })?.score
  const maxItems = parsePositiveInteger((payload as { maxItems?: unknown })?.maxItems)
  const days = parsePositiveInteger((payload as { days?: unknown })?.days)
  const feedbackItemIds = normalizeFeedbackItemIds((payload as { feedbackItemIds?: unknown })?.feedbackItemIds)

  if (!isNonEmptyString(taskId) || !UUID_RE.test(taskId.trim())) {
    return NextResponse.json({ accepted: false, error: 'taskId must be a UUID' }, { status: 400 })
  }
  if (!isNonEmptyString(scorecard) || !isNonEmptyString(score)) {
    return NextResponse.json({ accepted: false, error: 'scorecard and score are required' }, { status: 400 })
  }

  const normalizedTaskId = taskId.trim()
  const args = [
    'score',
    'dataset-curate',
    '--scorecard',
    scorecard.trim(),
    '--score',
    score.trim(),
    '--max-items',
    String(maxItems ?? Math.max(feedbackItemIds.length, 100)),
    '--task-id',
    normalizedTaskId,
  ]

  if (days !== null && feedbackItemIds.length === 0) {
    args.push('--days', String(days))
  }
  if (feedbackItemIds.length > 0) {
    args.push('--feedback-item-ids', feedbackItemIds.join(','))
  }

  const child = spawn('plexus', args, {
    stdio: 'ignore',
    detached: true,
    env: {
      ...process.env,
      PLEXUS_DISPATCH_TASK_ID: normalizedTaskId,
    },
  })

  try {
    await new Promise<void>((resolve, reject) => {
      child.once('spawn', () => resolve())
      child.once('error', (error) => reject(error))
    })
  } catch (error) {
    return NextResponse.json(
      {
        accepted: false,
        error: error instanceof Error ? error.message : 'Failed to launch associated dataset runner',
      },
      { status: 500 },
    )
  }

  child.unref()
  return NextResponse.json({
    accepted: true,
    taskId: normalizedTaskId,
    requestedMaxItems: maxItems ?? Math.max(feedbackItemIds.length, 100),
    explicitFeedbackItemCount: feedbackItemIds.length,
  })
}
