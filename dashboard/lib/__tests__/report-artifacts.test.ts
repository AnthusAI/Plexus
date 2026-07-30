import {
  buildReportArtifactHref,
  parseReportArtifactManifest,
  parseOptimizationRunRevisions,
  readTaskArtifact,
  selectReportRevision,
  selectArtifactDescriptor,
  taskArtifactFilename,
  type ArtifactDescriptor,
} from '../report-artifacts'

const descriptor: ArtifactDescriptor = {
  logical_id: 'scorecard_summary:abc123',
  kind: 'scorecard_summary',
  display_name: 'Summary',
  scope: 'scorecard',
  content_type: 'text/markdown',
  size_bytes: 5,
  sha256: '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',
  task_id: 'task-1',
  object_key: 'tasks/task-1/scorecard-summary-r0002.md',
  source_revision: 2,
}

const responseWith = (bytes: Uint8Array): Response => ({
  ok: true,
  status: 200,
  arrayBuffer: async () => bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  ) as ArrayBuffer,
} as Response)

describe('report artifact links', () => {
  it('builds a revision-pinned relative or canonical HTTPS link', () => {
    expect(buildReportArtifactHref({
      reportId: 'report-1',
      revision: 2,
      logicalId: descriptor.logical_id,
    })).toBe('/lab/reports/report-1?revision=2&artifact=scorecard_summary%3Aabc123')

    expect(buildReportArtifactHref({
      reportId: 'report-1',
      revision: 2,
      logicalId: descriptor.logical_id,
      dashboardBaseUrl: 'https://dashboard.example.com/',
    })).toBe('https://dashboard.example.com/lab/reports/report-1?revision=2&artifact=scorecard_summary%3Aabc123')
  })

  it('parses the exact revision and preserves a newer-revision signal', () => {
    const revisions = parseOptimizationRunRevisions({
      optimization_run: {
        latest_revision: { number: 3 },
        revisions: [
          { number: 2, manifest: descriptor },
          { number: 3, manifest: { ...descriptor, source_revision: 3 } },
        ],
      },
    })

    expect(selectReportRevision(revisions, 2)).toMatchObject({ number: 2 })
    expect(revisions.latestRevisionNumber).toBe(3)
  })

  it('rejects malformed or unknown revisions', () => {
    expect(() => parseOptimizationRunRevisions({ optimization_run: {} })).toThrow(
      'Report does not contain durable optimization revisions.',
    )
    expect(() => selectReportRevision({ latestRevisionNumber: 2, revisions: [] }, 1)).toThrow(
      'Report revision 1 was not found.',
    )
  })

  it('derives only the authorized task-relative filename', () => {
    expect(taskArtifactFilename(descriptor)).toBe('scorecard-summary-r0002.md')
    expect(() => taskArtifactFilename({
      ...descriptor,
      object_key: 'tasks/another-task/file.md',
    })).toThrow('Artifact object key does not belong to its Task.')
  })

  it('selects one exact logical artifact from the selected revision manifest', () => {
    const manifest = parseReportArtifactManifest({
      revision: 2,
      artifacts: [descriptor],
    }, 2)
    expect(selectArtifactDescriptor(manifest, descriptor.logical_id)).toEqual(descriptor)
    expect(() => parseReportArtifactManifest({
      revision: 3,
      artifacts: [descriptor],
    }, 2)).toThrow('does not match')
    expect(() => selectArtifactDescriptor(manifest, 'missing')).toThrow('was not found uniquely')
  })

  it('uses an on-demand ticket and verifies size and checksum', async () => {
    const issueTicket = jest.fn().mockResolvedValue({
      method: 'GET',
      url: 'https://storage.example.com/temporary',
      requiredHeaders: {},
    })
    const fetcher = jest.fn().mockResolvedValue(responseWith(
      new Uint8Array([104, 101, 108, 108, 111]),
    ))

    const bytes = await readTaskArtifact(descriptor, {
      issueTicket,
      fetcher,
      digest: async () => descriptor.sha256,
    })

    expect(Array.from(bytes)).toEqual([104, 101, 108, 108, 111])
    expect(issueTicket).toHaveBeenCalledWith({
      operation: 'READ',
      resourceType: 'TASK',
      resourceId: 'task-1',
      artifactType: 'TASK_ATTACHMENT',
      filename: 'scorecard-summary-r0002.md',
      contentType: 'text/markdown',
      sizeBytes: 5,
      sha256: descriptor.sha256,
    })
  })

  it('fails closed when downloaded bytes do not match the descriptor', async () => {
    await expect(readTaskArtifact(descriptor, {
      issueTicket: async () => ({
        method: 'GET',
        url: 'https://storage.example.com/temporary',
        requiredHeaders: {},
      }),
      fetcher: async () => responseWith(new Uint8Array([119, 114, 111, 110, 103])),
      digest: async () => '0'.repeat(64),
    })).rejects.toThrow('Artifact checksum does not match its revision manifest.')
  })
})
