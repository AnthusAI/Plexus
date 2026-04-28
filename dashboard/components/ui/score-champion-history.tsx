"use client"

import * as React from "react"
import { Crown, History } from "lucide-react"
import { generateClient } from "aws-amplify/api"

import type { GraphQLResult } from "@aws-amplify/api"
import { Timestamp } from "@/components/ui/timestamp"
import { cn } from "@/lib/utils"

const getClient = (() => {
  let client: any
  return () => (client ??= generateClient())
})()

interface ScoreChampionHistoryProps {
  scoreId: string
  className?: string
}

interface VersionRecord {
  id: string
  scoreId: string
  note?: string | null
  isFeatured?: string | null
  parentVersionId?: string | null
  createdAt: string
  updatedAt: string
  metadata?: Record<string, any> | null
}

interface ScoreResponse {
  getScore?: {
    id: string
    name?: string | null
    championVersionId?: string | null
  } | null
}

interface VersionPageResponse {
  listScoreVersionByScoreIdAndCreatedAt?: {
    items: VersionRecord[]
    nextToken?: string | null
  } | null
}

interface ChampionHistoryEntry {
  versionId: string
  versionNote?: string | null
  enteredAt?: string | null
  exitedAt?: string | null
  previousChampionVersionId?: string | null
  nextChampionVersionId?: string | null
  transitionId?: string | null
  inferred?: boolean
}

function getChampionEntries(version: VersionRecord): ChampionHistoryEntry[] {
  const entries = version.metadata?.championHistory
  if (!Array.isArray(entries)) return []
  return entries.map((entry) => ({
    versionId: version.id,
    versionNote: version.note,
    enteredAt: typeof entry?.enteredAt === "string" ? entry.enteredAt : null,
    exitedAt: typeof entry?.exitedAt === "string" ? entry.exitedAt : null,
    previousChampionVersionId: typeof entry?.previousChampionVersionId === "string" ? entry.previousChampionVersionId : null,
    nextChampionVersionId: typeof entry?.nextChampionVersionId === "string" ? entry.nextChampionVersionId : null,
    transitionId: typeof entry?.transitionId === "string" ? entry.transitionId : null,
    inferred: Boolean(entry?.inferred),
  }))
}

export function ScoreChampionHistory({ scoreId, className }: ScoreChampionHistoryProps) {
  const [scoreName, setScoreName] = React.useState<string>("Score")
  const [championVersionId, setChampionVersionId] = React.useState<string | null>(null)
  const [entries, setEntries] = React.useState<ChampionHistoryEntry[]>([])
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false

    const loadHistory = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const scoreResponse = await getClient().graphql({
          query: `
            query GetScoreForChampionHistory($id: ID!) {
              getScore(id: $id) {
                id
                name
                championVersionId
              }
            }
          `,
          variables: { id: scoreId },
        }) as GraphQLResult<ScoreResponse>

        const score = scoreResponse.data?.getScore
        if (!score) {
          throw new Error("Score not found")
        }

        const allVersions: VersionRecord[] = []
        let nextToken: string | null | undefined = null
        do {
          const versionResponse = await getClient().graphql({
            query: `
              query ListScoreVersionsForChampionHistory($scoreId: String!, $nextToken: String) {
                listScoreVersionByScoreIdAndCreatedAt(scoreId: $scoreId, sortDirection: DESC, limit: 100, nextToken: $nextToken) {
                  items {
                    id
                    scoreId
                    note
                    isFeatured
                    parentVersionId
                    createdAt
                    updatedAt
                    metadata
                  }
                  nextToken
                }
              }
            `,
            variables: { scoreId, nextToken },
          }) as GraphQLResult<VersionPageResponse>

          const page = versionResponse.data?.listScoreVersionByScoreIdAndCreatedAt
          allVersions.push(...(page?.items ?? []))
          nextToken = page?.nextToken
        } while (nextToken)

        const historyEntries = allVersions
          .flatMap(getChampionEntries)
          .sort((a, b) => {
            const aTime = a.enteredAt ? new Date(a.enteredAt).getTime() : 0
            const bTime = b.enteredAt ? new Date(b.enteredAt).getTime() : 0
            return bTime - aTime
          })

        if (!cancelled) {
          setScoreName(score.name || "Score")
          setChampionVersionId(score.championVersionId || null)
          setEntries(historyEntries)
        }
      } catch (loadError) {
        if (!cancelled) {
          console.error("Failed to load champion history:", loadError)
          setError("Failed to load champion history.")
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    loadHistory()
    return () => {
      cancelled = true
    }
  }, [scoreId])

  return (
    <div className={cn("h-full min-h-0 flex flex-col bg-background p-3", className)}>
      <div className="flex items-center justify-between gap-3 pb-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-foreground" />
          <div>
            <div className="text-sm font-semibold">Champion History</div>
            <div className="text-xs text-muted-foreground">{scoreName}</div>
          </div>
        </div>
        {championVersionId && (
          <div className="text-xs text-muted-foreground">
            Current champion: <span className="font-mono">{championVersionId}</span>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto space-y-2">
        {isLoading && Array.from({ length: 5 }).map((_, index) => (
          <div key={`history-skeleton-${index}`} className="bg-card p-3 rounded-md">
            <div className="h-4 w-48 rounded bg-muted animate-pulse mb-2" />
            <div className="h-3 w-72 rounded bg-muted animate-pulse" />
          </div>
        ))}

        {!isLoading && error && (
          <div className="bg-card p-3 rounded-md text-sm text-destructive">{error}</div>
        )}

        {!isLoading && !error && entries.length === 0 && (
          <div className="bg-card p-3 rounded-md text-sm text-muted-foreground">
            No champion history metadata has been recorded yet. Future promotions will populate this log.
          </div>
        )}

        {!isLoading && !error && entries.map((entry) => (
          <div key={`${entry.versionId}-${entry.transitionId || entry.enteredAt || "legacy"}`} className="bg-card p-3 rounded-md">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-medium">
                  {entry.versionId === championVersionId && <Crown className="h-4 w-4 text-muted-foreground" />}
                  <span className="font-mono truncate">{entry.versionId}</span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground truncate">
                  {entry.versionNote || "No note"}
                </div>
              </div>
              <div className="shrink-0 text-right text-xs text-muted-foreground">
                {entry.inferred ? "Legacy inferred range" : "Recorded range"}
              </div>
            </div>
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              <div className="bg-background p-2 rounded">
                <div className="text-muted-foreground">Entered production</div>
                {entry.enteredAt ? <Timestamp time={entry.enteredAt} variant="relative" className="text-xs" /> : <div>Unknown</div>}
              </div>
              <div className="bg-background p-2 rounded">
                <div className="text-muted-foreground">Exited production</div>
                {entry.exitedAt ? <Timestamp time={entry.exitedAt} variant="relative" className="text-xs" /> : <div>Current / open</div>}
              </div>
              <div className="bg-background p-2 rounded">
                <div className="text-muted-foreground">Replaced</div>
                <div className="font-mono truncate">{entry.previousChampionVersionId || "None recorded"}</div>
              </div>
              <div className="bg-background p-2 rounded">
                <div className="text-muted-foreground">Replaced by</div>
                <div className="font-mono truncate">{entry.nextChampionVersionId || "None recorded"}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
