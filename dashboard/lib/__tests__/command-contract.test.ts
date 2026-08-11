import {
  commandArgumentKeys,
  isRegisteredCommandAction,
  parseCommandArguments,
  rejectUnsupportedArguments,
  sanitizeCommandArguments,
  type RegisteredCommandAction,
} from '@/lib/command-contract'

describe('command contract', () => {
  it('defines allowlists for every registered dispatch action', () => {
    const actions: RegisteredCommandAction[] = [
      'evaluation.accuracy',
      'evaluation.feedback',
      'prediction.run',
      'report.run',
      'procedure.run',
      'feedback.report',
    ]

    for (const action of actions) {
      expect(commandArgumentKeys(action).length).toBeGreaterThan(0)
      expect(isRegisteredCommandAction(action)).toBe(true)
    }
  })

  it('parses AWSJSON argument strings and rejects malformed JSON', () => {
    expect(parseCommandArguments('{"scoreName":"Score"}')).toEqual({ scoreName: 'Score' })
    expect(() => parseCommandArguments('{bad-json')).toThrow('arguments must be valid JSON')
  })

  it('rejects unsupported fields and sanitizes frontend payloads to the allowlist', () => {
    const action: RegisteredCommandAction = 'evaluation.accuracy'
    const args = { scorecardName: 'Card', scoreName: 'Score', numberOfSamples: 10, loadFresh: true, logToLanggraph: true }

    expect(() => rejectUnsupportedArguments(action, args)).toThrow('unsupported arguments: logToLanggraph')
    expect(sanitizeCommandArguments(action, args)).toEqual({
      scorecardName: 'Card',
      scoreName: 'Score',
      numberOfSamples: 10,
      loadFresh: true,
    })
  })
})

