import { describe, expect, it } from '@jest/globals'
import { getSystemProcedureParameterValues } from '../procedure-template-parameters'

describe('procedure-template-parameters', () => {
  it('injects the selected account id for Create Scorecard runs', () => {
    const values = getSystemProcedureParameterValues(
      { category: 'builtin:scorecard_create' } as any,
      'account-123'
    )

    expect(values).toEqual({
      account_identifier: 'account-123',
    })
  })

  it('does not inject system parameters for other templates', () => {
    const values = getSystemProcedureParameterValues(
      { category: 'builtin:other_template' } as any,
      'account-123'
    )

    expect(values).toEqual({})
  })

  it('injects the selected account id for Create Score Code runs', () => {
    const values = getSystemProcedureParameterValues(
      { category: 'builtin:score_code_create' } as any,
      'account-123'
    )

    expect(values).toEqual({
      account_identifier: 'account-123',
    })
  })
})
