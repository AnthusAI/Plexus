import {
  ACTION_AUTHORITY,
  LIFECYCLE_APPSYNC_ROOTS,
  REGISTERED_COMMAND_ACTIONS,
  WORKER_APPSYNC_AUTHORITY_GROUPS,
  WORKER_DOMAIN_APPSYNC_ROOTS,
  WORKER_STORAGE_AUTHORITIES,
} from './authority-manifest'

describe('command worker action authority manifest', () => {
  it('covers every registered structured action with evidence and no wildcard root', () => {
    expect(REGISTERED_COMMAND_ACTIONS).toEqual([
      'evaluation.accuracy',
      'evaluation.feedback',
      'feedback.report',
      'prediction.run',
      'procedure.run',
      'report.run',
    ])
    for (const action of REGISTERED_COMMAND_ACTIONS) {
      expect(ACTION_AUTHORITY[action].appsync.length).toBeGreaterThan(0)
      expect(ACTION_AUTHORITY[action].evidence.length).toBeGreaterThan(0)
      expect(ACTION_AUTHORITY[action].appsync.every((root) => !root.includes('*'))).toBe(true)
    }
  })

  it('keeps the six lifecycle roots separate from audited domain authority', () => {
    expect(LIFECYCLE_APPSYNC_ROOTS).toHaveLength(6)
    expect(new Set(LIFECYCLE_APPSYNC_ROOTS).size).toBe(6)
    expect(WORKER_DOMAIN_APPSYNC_ROOTS).not.toEqual(expect.arrayContaining(LIFECYCLE_APPSYNC_ROOTS))
  })

  it('packages only non-empty direct authority groups with stable unique ids', () => {
    expect(WORKER_APPSYNC_AUTHORITY_GROUPS.map((group) => group.source)).toEqual([
      'lifecycle',
      'evaluation.accuracy',
      'evaluation.feedback',
      'feedback.report',
      'prediction.run',
      'procedure.run',
    ])
    expect(new Set(WORKER_APPSYNC_AUTHORITY_GROUPS.map((group) => group.id)).size)
      .toBe(WORKER_APPSYNC_AUTHORITY_GROUPS.length)
    expect([...new Set(WORKER_APPSYNC_AUTHORITY_GROUPS.flatMap((group) => group.roots))].sort())
      .toEqual([...LIFECYCLE_APPSYNC_ROOTS, ...WORKER_DOMAIN_APPSYNC_ROOTS].sort())
  })

  it('limits direct AWS storage authority to the three workload buckets', () => {
    expect(WORKER_STORAGE_AUTHORITIES).toEqual([
      'dataSources:read',
      'reportBlockDetails:readWrite',
      'scoreResultAttachments:readWrite',
    ])
  })
})
