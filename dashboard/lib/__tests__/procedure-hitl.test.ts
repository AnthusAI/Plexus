import {
  buildResponseValue,
  getControlEnvelope,
  isPendingHumanInteraction,
  mapPendingInteractionToRequestType,
  parseMessageMetadata,
} from '../procedure-hitl'

describe('procedure-hitl helpers', () => {
  it('parses metadata.control envelope from object and string', () => {
    const metadataObject = {
      control: {
        request_id: 'req-1',
        procedure_id: 'proc-1',
        request_type: 'input',
      },
    }
    expect(getControlEnvelope(metadataObject)).toEqual(metadataObject.control)

    const metadataString = JSON.stringify(metadataObject)
    expect(getControlEnvelope(metadataString)).toEqual(metadataObject.control)
  })

  it('returns null for non-canonical metadata envelopes', () => {
    expect(getControlEnvelope(null)).toBeNull()
    expect(getControlEnvelope('{}')).toBeNull()
    expect(getControlEnvelope({ control: { request_type: 'input' } })).toBeNull()
  })

  it('maps pending human interaction to request type', () => {
    expect(mapPendingInteractionToRequestType('PENDING_APPROVAL')).toBe('approval')
    expect(mapPendingInteractionToRequestType('PENDING_INPUT')).toBe('input')
    expect(mapPendingInteractionToRequestType('PENDING_REVIEW')).toBe('review')
    expect(mapPendingInteractionToRequestType('PENDING_ESCALATION')).toBe('escalation')
    expect(mapPendingInteractionToRequestType(undefined)).toBe('input')
  })

  it('builds canonical response values by request type', () => {
    expect(buildResponseValue({ requestType: 'approval', action: 'approve' })).toBe(true)
    expect(buildResponseValue({ requestType: 'approval', action: 'reject' })).toBe(false)
    expect(buildResponseValue({ requestType: 'input', inputText: 'details' })).toBe('details')
    expect(buildResponseValue({ requestType: 'review', action: 'revise', inputText: 'changes' })).toEqual({
      decision: 'revise',
      feedback: 'changes',
    })
  })

  it('recognizes pending interaction values', () => {
    expect(isPendingHumanInteraction('PENDING_APPROVAL')).toBe(true)
    expect(isPendingHumanInteraction('RESPONSE')).toBe(false)
  })

  it('parses metadata objects and strings', () => {
    expect(parseMessageMetadata({ a: 1 })).toEqual({ a: 1 })
    expect(parseMessageMetadata('{"a":1}')).toEqual({ a: 1 })
    expect(parseMessageMetadata('')).toBeNull()
    expect(parseMessageMetadata('not-json')).toBeNull()
  })
})
