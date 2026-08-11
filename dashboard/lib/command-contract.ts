export const REGISTERED_COMMAND_ACTIONS = [
  'evaluation.accuracy',
  'evaluation.feedback',
  'prediction.run',
  'report.run',
  'procedure.run',
  'feedback.report',
] as const

export type RegisteredCommandAction = (typeof REGISTERED_COMMAND_ACTIONS)[number]

const COMMAND_ARGUMENT_KEYS: Record<RegisteredCommandAction, readonly string[]> = {
  'evaluation.accuracy': ['scorecardName', 'scoreName', 'numberOfSamples', 'loadFresh', 'versionId'],
  'evaluation.feedback': ['scorecardName', 'scoreName', 'days', 'versionId'],
  'prediction.run': ['scorecardName', 'scoreName', 'itemId', 'versionId'],
  'report.run': ['configurationId', 'parameters'],
  'procedure.run': ['procedureId', 'parameters'],
  'feedback.report': ['report', 'scorecardId', 'scoreId', 'days', 'startDate', 'endDate', 'bucketType', 'timezone', 'weekStart'],
}

const REGISTERED_ACTIONS = new Set<RegisteredCommandAction>(REGISTERED_COMMAND_ACTIONS)

export function isRegisteredCommandAction(action: string): action is RegisteredCommandAction {
  return REGISTERED_ACTIONS.has(action as RegisteredCommandAction)
}

export function parseCommandArguments(raw: unknown): Record<string, unknown> {
  if (typeof raw === 'string') {
    try {
      raw = JSON.parse(raw)
    } catch {
      throw new Error('arguments must be valid JSON')
    }
  }

  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {}
  return raw as Record<string, unknown>
}

export function commandArgumentKeys(action: RegisteredCommandAction): readonly string[] {
  return COMMAND_ARGUMENT_KEYS[action]
}

export function rejectUnsupportedArguments(action: RegisteredCommandAction, args: Record<string, unknown>): void {
  const allowed = commandArgumentKeys(action)
  const unknown = Object.keys(args).filter((key) => !allowed.includes(key))
  if (unknown.length) throw new Error(`unsupported arguments: ${unknown.sort().join(', ')}`)
}

export function sanitizeCommandArguments(action: RegisteredCommandAction, raw: unknown): Record<string, unknown> {
  const args = parseCommandArguments(raw)
  const allowed = commandArgumentKeys(action)
  const sanitized: Record<string, unknown> = {}

  for (const key of allowed) {
    if (Object.prototype.hasOwnProperty.call(args, key)) sanitized[key] = args[key]
  }

  return sanitized
}
