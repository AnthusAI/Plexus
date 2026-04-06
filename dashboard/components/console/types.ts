export type ConsoleArtifactKind = 'none' | 'activity' | 'board' | 'report'

export interface ConsoleArtifactPayload {
  title?: string
  reportId?: string
}

export interface ConsoleArtifactState {
  kind: ConsoleArtifactKind
  payload: ConsoleArtifactPayload | null
  isOpen: boolean
  width: number
}

export interface ConsoleSessionListItem {
  sessionId: string
  title: string
  lastMessage: string
  lastActivityAt: string
  hasAttention: boolean
}
