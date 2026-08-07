import { readFileSync } from 'fs'
import path from 'path'

const schema = readFileSync(path.join(process.cwd(), 'amplify/data/resource.ts'), 'utf8')

function modelDefinition(name: string): string {
  const start = schema.indexOf(`    ${name}: a`)
  if (start < 0) throw new Error(`missing ${name} model`)
  const next = schema.slice(start + 1).search(/\n    [A-Za-z][A-Za-z0-9]*: a/)
  return next < 0 ? schema.slice(start) : schema.slice(start, start + 1 + next)
}

describe('worker domain model IAM authorization', () => {
  it.each([
    'Account', 'Scorecard', 'ScorecardSection', 'Score', 'Item',
    'FeedbackItem', 'ReportConfiguration', 'DataSource', 'DataSourceVersion', 'DataSet',
  ])('%s is IAM-readable for registered workloads', (model) => {
    expect(modelDefinition(model)).toContain("allow.authenticated('identityPool').to(['read'])")
  })

  it.each(['Evaluation', 'ScoringJob', 'ScoreResult', 'Report', 'ReportBlock', 'Procedure', 'ChatSession', 'ChatMessage'])
  ('%s permits only the runtime read/create/update set', (model) => {
    expect(modelDefinition(model)).toContain(
      "allow.authenticated('identityPool').to(['read', 'create', 'update'])",
    )
  })

  it('allows procedure score-version creation without allowing update or delete', () => {
    expect(modelDefinition('ScoreVersion')).toContain(
      "allow.authenticated('identityPool').to(['read', 'create'])",
    )
  })
})
