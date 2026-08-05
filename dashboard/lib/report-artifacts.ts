export interface TaskArtifactReference {
  task_id: string
  object_key: string
  content_type: string
  size_bytes: number
  sha256: string
}

export interface ArtifactDescriptor extends TaskArtifactReference {
  logical_id: string
  kind: string
  display_name: string
  scope: 'run' | 'scorecard' | 'score'
  source_revision: number
  scorecard_name?: string
  score_name?: string
  dashboard_url?: string
}

export interface ReportRevisionReference {
  number: number
  milestone?: string
  published_at?: string
  manifest: TaskArtifactReference
}

export interface OptimizationRunRevisions {
  latestRevisionNumber: number
  revisions: ReportRevisionReference[]
}

export interface ReportArtifactManifest {
  revision: number
  artifacts: ArtifactDescriptor[]
}

export interface ArtifactTransferReadRequest {
  operation: 'READ'
  resourceType: 'TASK'
  resourceId: string
  artifactType: 'TASK_ATTACHMENT'
  filename: string
  contentType: string
  sizeBytes: number
  sha256: string
}

export interface ArtifactReadTicket {
  method: 'GET'
  url: string
  requiredHeaders: Record<string, string>
}

type ArtifactReadDependencies = {
  issueTicket: (request: ArtifactTransferReadRequest) => Promise<ArtifactReadTicket>
  fetcher?: typeof fetch
  digest?: (bytes: Uint8Array) => Promise<string>
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? value as Record<string, unknown> : null
}

function parseJsonObject(value: unknown): Record<string, unknown> | null {
  if (typeof value !== 'string') return objectValue(value)
  try {
    return objectValue(JSON.parse(value))
  } catch {
    return null
  }
}

function parseTaskArtifactReference(value: unknown): TaskArtifactReference | null {
  const candidate = objectValue(value)
  if (!candidate) return null
  if (
    typeof candidate.task_id !== 'string' ||
    typeof candidate.object_key !== 'string' ||
    typeof candidate.content_type !== 'string' ||
    typeof candidate.size_bytes !== 'number' ||
    !Number.isSafeInteger(candidate.size_bytes) ||
    candidate.size_bytes < 0 ||
    typeof candidate.sha256 !== 'string' ||
    !/^[a-f0-9]{64}$/i.test(candidate.sha256)
  ) {
    return null
  }
  return {
    task_id: candidate.task_id,
    object_key: candidate.object_key,
    content_type: candidate.content_type,
    size_bytes: candidate.size_bytes,
    sha256: candidate.sha256.toLowerCase(),
  }
}

export function parseArtifactDescriptor(value: unknown): ArtifactDescriptor | null {
  const candidate = objectValue(value)
  const reference = parseTaskArtifactReference(candidate)
  const scope = candidate?.scope
  if (
    !candidate ||
    !reference ||
    typeof candidate.logical_id !== 'string' ||
    !candidate.logical_id ||
    typeof candidate.kind !== 'string' ||
    typeof candidate.display_name !== 'string' ||
    !['run', 'scorecard', 'score'].includes(String(scope)) ||
    !Number.isSafeInteger(candidate.source_revision) ||
    Number(candidate.source_revision) < 1
  ) {
    return null
  }
  return {
    ...reference,
    logical_id: candidate.logical_id,
    kind: candidate.kind,
    display_name: candidate.display_name,
    scope: scope as ArtifactDescriptor['scope'],
    source_revision: Number(candidate.source_revision),
    scorecard_name: typeof candidate.scorecard_name === 'string'
      ? candidate.scorecard_name
      : undefined,
    score_name: typeof candidate.score_name === 'string'
      ? candidate.score_name
      : undefined,
    dashboard_url: typeof candidate.dashboard_url === 'string'
      ? candidate.dashboard_url
      : undefined,
  }
}

export function buildReportArtifactHref({
  reportId,
  revision,
  logicalId,
  dashboardBaseUrl,
}: {
  reportId: string
  revision: number
  logicalId: string
  dashboardBaseUrl?: string
}): string {
  if (!reportId || !logicalId || !Number.isSafeInteger(revision) || revision < 1) {
    throw new Error('Report ID, logical artifact ID, and positive revision are required.')
  }
  const path = `/lab/reports/${encodeURIComponent(reportId)}?revision=${revision}&artifact=${encodeURIComponent(logicalId)}`
  if (!dashboardBaseUrl) return path

  const base = new URL(dashboardBaseUrl)
  if (
    base.protocol !== 'https:' ||
    base.username ||
    base.password ||
    base.pathname !== '/' ||
    base.search ||
    base.hash
  ) {
    throw new Error('Dashboard base URL must be an HTTPS origin.')
  }
  return new URL(path, base.origin).toString()
}

export function parseOptimizationRunRevisions(parameters: unknown): OptimizationRunRevisions {
  const parsed = parseJsonObject(parameters)
  const run = objectValue(parsed?.optimization_run)
  const revisionValues = Array.isArray(run?.revisions) ? run.revisions : []
  const revisions = revisionValues.flatMap((value): ReportRevisionReference[] => {
    const candidate = objectValue(value)
    const number = candidate?.number
    const manifest = parseTaskArtifactReference(candidate?.manifest)
    if (!Number.isSafeInteger(number) || Number(number) < 1 || !manifest) return []
    return [{
      number: Number(number),
      milestone: typeof candidate?.milestone === 'string' ? candidate.milestone : undefined,
      published_at: typeof candidate?.published_at === 'string' ? candidate.published_at : undefined,
      manifest,
    }]
  })
  if (revisions.length === 0) {
    throw new Error('Report does not contain durable optimization revisions.')
  }
  const latestRecord = objectValue(run?.latest_revision)
  const latestNumber = latestRecord?.number
  const latestRevisionNumber = Number.isSafeInteger(latestNumber)
    ? Number(latestNumber)
    : Math.max(...revisions.map(revision => revision.number))
  return { latestRevisionNumber, revisions }
}

export function selectReportRevision(
  evidence: OptimizationRunRevisions,
  revisionNumber: number,
): ReportRevisionReference {
  if (!Number.isSafeInteger(revisionNumber) || revisionNumber < 1) {
    throw new Error('Artifact revision must be a positive integer.')
  }
  const revision = evidence.revisions.find(item => item.number === revisionNumber)
  if (!revision) {
    throw new Error(`Report revision ${revisionNumber} was not found.`)
  }
  return revision
}

export function parseReportArtifactManifest(
  value: unknown,
  expectedRevision: number,
): ReportArtifactManifest {
  const manifest = parseJsonObject(value)
  if (!manifest || manifest.revision !== expectedRevision || !Array.isArray(manifest.artifacts)) {
    throw new Error('Artifact manifest does not match the selected Report revision.')
  }
  const artifacts = manifest.artifacts.map(parseArtifactDescriptor)
  if (artifacts.some(artifact => artifact === null)) {
    throw new Error('Artifact manifest contains an invalid descriptor.')
  }
  return { revision: expectedRevision, artifacts: artifacts as ArtifactDescriptor[] }
}

export function selectArtifactDescriptor(
  manifest: ReportArtifactManifest,
  logicalId: string,
): ArtifactDescriptor {
  const matches = manifest.artifacts.filter(artifact => artifact.logical_id === logicalId)
  if (matches.length !== 1) {
    throw new Error(`Artifact ${logicalId} was not found uniquely in Report revision ${manifest.revision}.`)
  }
  return matches[0]
}

export function taskArtifactFilename(reference: TaskArtifactReference): string {
  const prefix = `tasks/${reference.task_id}/`
  if (!reference.object_key.startsWith(prefix)) {
    throw new Error('Artifact object key does not belong to its Task.')
  }
  const filename = reference.object_key.slice(prefix.length)
  if (!filename || filename.startsWith('/') || filename.includes('..')) {
    throw new Error('Artifact filename is invalid.')
  }
  return filename
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error('Browser SHA-256 support is unavailable.')
  }
  const digest = await globalThis.crypto.subtle.digest(
    'SHA-256',
    bytes.slice().buffer as ArrayBuffer,
  )
  return Array.from(new Uint8Array(digest))
    .map(value => value.toString(16).padStart(2, '0'))
    .join('')
}

export async function readTaskArtifact(
  reference: TaskArtifactReference,
  dependencies: ArtifactReadDependencies,
): Promise<Uint8Array> {
  const filename = taskArtifactFilename(reference)
  const ticket = await dependencies.issueTicket({
    operation: 'READ',
    resourceType: 'TASK',
    resourceId: reference.task_id,
    artifactType: 'TASK_ATTACHMENT',
    filename,
    contentType: reference.content_type,
    sizeBytes: reference.size_bytes,
    sha256: reference.sha256,
  })
  if (ticket.method !== 'GET') {
    throw new Error('Artifact ticket did not authorize a read.')
  }
  const ticketUrl = new URL(ticket.url)
  if (ticketUrl.protocol !== 'https:') {
    throw new Error('Artifact ticket URL must use HTTPS.')
  }

  const response = await (dependencies.fetcher ?? fetch)(ticket.url, {
    method: 'GET',
    headers: ticket.requiredHeaders,
  })
  if (!response.ok) {
    throw new Error(`Artifact download failed with HTTP ${response.status}.`)
  }
  const bytes = new Uint8Array(await response.arrayBuffer())
  if (bytes.byteLength !== reference.size_bytes) {
    throw new Error('Artifact size does not match its revision manifest.')
  }
  const digest = dependencies.digest ?? sha256Hex
  if (await digest(bytes) !== reference.sha256.toLowerCase()) {
    throw new Error('Artifact checksum does not match its revision manifest.')
  }
  return bytes
}
