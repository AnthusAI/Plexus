"use client"

import { useEffect, useState } from "react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { graphqlRequest, handleGraphQLErrors } from "@/utils/amplify-client"

interface ScoreVersionOption {
  id: string
  createdAt: string
  isFeatured: string
}

interface ScoreVersionSelectorProps {
  scoreId?: string | null
  value: string | null
  onChange: (value: string | null) => void
  placeholder?: string
  includeAllOption?: boolean
}

export default function ScoreVersionSelector({
  scoreId,
  value,
  onChange,
  placeholder = "Select score version",
  includeAllOption = true,
}: ScoreVersionSelectorProps) {
  const [versions, setVersions] = useState<ScoreVersionOption[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!scoreId) {
      setVersions([])
      return
    }

    const load = async () => {
      setIsLoading(true)
      try {
        const response = await graphqlRequest<any>(
          `
            query ListScoreVersionByScoreIdAndCreatedAt(
              $scoreId: String!
              $sortDirection: ModelSortDirection
              $limit: Int
              $nextToken: String
            ) {
              listScoreVersionByScoreIdAndCreatedAt(
                scoreId: $scoreId
                sortDirection: $sortDirection
                limit: $limit
                nextToken: $nextToken
              ) {
                items {
                  id
                  createdAt
                  isFeatured
                }
                nextToken
              }
            }
          `,
          {
            scoreId,
            sortDirection: "DESC",
            limit: 200,
          }
        )
        handleGraphQLErrors(response)
        const items = (response.data?.listScoreVersionByScoreIdAndCreatedAt?.items || []) as any[]
        setVersions(
          items
            .filter((item) => item?.id && item?.createdAt)
            .map((item) => ({
              id: item.id,
              createdAt: item.createdAt,
              isFeatured: item.isFeatured,
            }))
        )
      } catch (error) {
        console.error("Error loading score versions:", error)
        setVersions([])
      } finally {
        setIsLoading(false)
      }
    }

    load()
  }, [scoreId])

  useEffect(() => {
    if (!value) return
    if (!versions.find((version) => version.id === value)) {
      onChange(null)
    }
  }, [versions, value, onChange])

  const disabled = !scoreId || isLoading
  const selectValue = value || "__all__"

  return (
    <Select
      value={selectValue}
      onValueChange={(next) => onChange(next === "__all__" ? null : next)}
      disabled={disabled}
    >
      <SelectTrigger className="w-full h-9 bg-card border-none">
        <SelectValue
          placeholder={!scoreId ? "Select a score first" : isLoading ? "Loading score versions..." : placeholder}
        />
      </SelectTrigger>
      <SelectContent className="bg-card border-none">
        {includeAllOption && <SelectItem value="__all__">All Score Versions</SelectItem>}
        {versions.map((version) => (
          <SelectItem key={version.id} value={version.id}>
            {version.isFeatured === "true" ? "⭐ " : ""}
            {new Date(version.createdAt).toLocaleString()}{" "}
            <span className="text-muted-foreground">({version.id.slice(0, 8)}...)</span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
