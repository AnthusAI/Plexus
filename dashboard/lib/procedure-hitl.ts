export type PendingHumanInteraction =
  | 'PENDING_APPROVAL'
  | 'PENDING_INPUT'
  | 'PENDING_REVIEW'
  | 'PENDING_ESCALATION'

export interface ControlRequestEnvelope {
  request_id: string
  procedure_id: string
  request_type: string
  prompt?: string
  options?: Array<Record<string, unknown>>
  timeout_seconds?: number | null
  default_value?: unknown
  metadata?: Record<string, unknown>
}

export function isPendingHumanInteraction(value?: string | null): value is PendingHumanInteraction {
  return value === 'PENDING_APPROVAL'
    || value === 'PENDING_INPUT'
    || value === 'PENDING_REVIEW'
    || value === 'PENDING_ESCALATION'
}

export function parseMessageMetadata(metadata: unknown): Record<string, unknown> | null {
  if (!metadata) {
    return null
  }
  if (typeof metadata === 'object' && !Array.isArray(metadata)) {
    return metadata as Record<string, unknown>
  }
  if (typeof metadata !== 'string' || !metadata.trim()) {
    return null
  }
  try {
    const parsed = JSON.parse(metadata)
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
    return null
  } catch {
    return null
  }
}

export function getControlEnvelope(metadata: unknown): ControlRequestEnvelope | null {
  const parsed = parseMessageMetadata(metadata)
  if (!parsed) {
    return null
  }
  const control = parsed.control
  if (!control || typeof control !== 'object' || Array.isArray(control)) {
    return null
  }
  const controlRecord = control as Record<string, unknown>
  if (typeof controlRecord.request_id !== 'string' || !controlRecord.request_id) {
    return null
  }
  if (typeof controlRecord.procedure_id !== 'string' || !controlRecord.procedure_id) {
    return null
  }
  if (typeof controlRecord.request_type !== 'string' || !controlRecord.request_type) {
    return null
  }
  return controlRecord as unknown as ControlRequestEnvelope
}

export function mapPendingInteractionToRequestType(humanInteraction?: string | null): string {
  switch (humanInteraction) {
    case 'PENDING_APPROVAL':
      return 'approval'
    case 'PENDING_INPUT':
      return 'input'
    case 'PENDING_REVIEW':
      return 'review'
    case 'PENDING_ESCALATION':
      return 'escalation'
    default:
      return 'input'
  }
}

interface BuildResponseValueInput {
  requestType: string
  action?: string
  inputText?: string
}

export function buildResponseValue({
  requestType,
  action,
  inputText,
}: BuildResponseValueInput): unknown {
  const normalizedType = requestType.toLowerCase()
  if (normalizedType === 'approval') {
    return action === 'approve'
  }
  if (normalizedType === 'input') {
    return inputText ?? ''
  }
  if (normalizedType === 'review') {
    return {
      decision: action ?? 'approve',
      feedback: inputText ?? '',
    }
  }
  if (normalizedType === 'escalation') {
    return {
      acknowledged: true,
      action: action ?? 'acknowledge',
      note: inputText ?? '',
    }
  }
  return {
    action: action ?? 'submit',
    input: inputText ?? '',
  }
}
