import { formatAmplifyError, getClient } from '@/utils/amplify-client'
import type {
  ArtifactReadTicket,
  ArtifactTransferReadRequest,
} from '@/lib/report-artifacts'

type TicketMutationClient = {
  mutations: {
    createArtifactTransferTickets: (input: {
      requests: ArtifactTransferReadRequest[]
    }) => Promise<unknown>
  }
}

function parseHeaders(value: unknown): Record<string, string> {
  const parsed = typeof value === 'string' ? JSON.parse(value) : value
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Artifact ticket headers were malformed.')
  }
  const entries = Object.entries(parsed)
  if (!entries.every(([key, item]) => typeof key === 'string' && typeof item === 'string')) {
    throw new Error('Artifact ticket headers were malformed.')
  }
  return Object.fromEntries(entries) as Record<string, string>
}

export async function issueTaskArtifactReadTicket(
  request: ArtifactTransferReadRequest,
  client: TicketMutationClient = getClient() as unknown as TicketMutationClient,
): Promise<ArtifactReadTicket> {
  let response: any
  try {
    response = await client.mutations.createArtifactTransferTickets({ requests: [request] })
  } catch (error) {
    throw new Error(`Artifact authorization failed: ${formatAmplifyError(error)}`)
  }
  if (response?.errors?.length) {
    throw new Error(`Artifact authorization failed: ${formatAmplifyError(response)}`)
  }
  const tickets = Array.isArray(response?.data)
    ? response.data
    : response?.data?.createArtifactTransferTickets
  const ticket = Array.isArray(tickets) ? tickets[0] : null
  if (!ticket || ticket.method !== 'GET' || typeof ticket.url !== 'string') {
    throw new Error('Artifact authorization returned a malformed read ticket.')
  }
  const url = new URL(ticket.url)
  if (url.protocol !== 'https:') {
    throw new Error('Artifact authorization returned an unsafe read URL.')
  }
  return {
    method: 'GET',
    url: ticket.url,
    requiredHeaders: parseHeaders(ticket.requiredHeaders ?? {}),
  }
}
