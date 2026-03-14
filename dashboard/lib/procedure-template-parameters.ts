import type { Schema } from '@/amplify/data/resource'

type ProcedureTemplate = Schema['Procedure']['type']

export function getSystemProcedureParameterValues(
  template: Pick<ProcedureTemplate, 'category'>,
  selectedAccountId: string
): Record<string, any> {
  if (
    template.category === 'builtin:scorecard_create' ||
    template.category === 'builtin:score_code_create'
  ) {
    return {
      account_identifier: selectedAccountId,
    }
  }

  return {}
}
