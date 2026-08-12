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

  it('packages declared authority groups with stable unique ids', () => {
    expect(WORKER_APPSYNC_AUTHORITY_GROUPS.map((group) => group.source)).toEqual([
      'lifecycle',
      'evaluation.accuracy',
      'evaluation.feedback',
      'feedback.report',
      'prediction.run',
      'procedure.run',
      'report.run',
    ])
    expect(new Set(WORKER_APPSYNC_AUTHORITY_GROUPS.map((group) => group.id)).size)
      .toBe(WORKER_APPSYNC_AUTHORITY_GROUPS.length)
    expect([...new Set(WORKER_APPSYNC_AUTHORITY_GROUPS.flatMap((group) => group.roots))].sort())
      .toEqual([...LIFECYCLE_APPSYNC_ROOTS, ...WORKER_DOMAIN_APPSYNC_ROOTS].sort())
  })

  it('grants report commands the exact configuration lookup they execute', () => {
    expect(ACTION_AUTHORITY['report.run'].appsync).toContain('Query/getReportConfiguration')
    expect(WORKER_APPSYNC_AUTHORITY_GROUPS.find((group) => group.source === 'report.run')?.roots)
      .toContain('Query/getReportConfiguration')
  })

  it('keeps each managed-policy document to authority declared by that action', () => {
    const procedureGroup = WORKER_APPSYNC_AUTHORITY_GROUPS.find((group) => group.source === 'procedure.run')

    // The task role is shared by every command, so action groups are policy
    // documents, not runtime permission boundaries.  Inherited roots already
    // exist in their declaring documents; duplicating them can exceed IAM's
    // 6,144-byte managed-policy limit.
    expect(procedureGroup?.roots).not.toContain('Query/getScorecard')
    expect(procedureGroup?.roots).toContain('Query/getProcedure')
  })

  it('limits direct AWS storage authority to the three workload buckets', () => {
    expect(WORKER_STORAGE_AUTHORITIES).toEqual([
      'dataSources:read',
      'reportBlockDetails:readWrite',
      'scoreResultAttachments:readWrite',
    ])
  })
})
