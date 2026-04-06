"use client"

import { useEffect, useState } from "react"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { graphqlRequest, handleGraphQLErrors, type GraphQLResponse } from "@/utils/amplify-client"

interface DataSourceVersionOption {
  id: string
  createdAt: string
  note?: string | null
}

interface DataSourceVersionSelectorProps {
  dataSourceId?: string | null
  currentVersionId?: string | null
  value: string | null
  onChange: (value: string | null) => void
  placeholder?: string
  includeAllOption?: boolean
}

type ListDataSourceVersionByDataSourceIdAndCreatedAtData = {
  listDataSourceVersionByDataSourceIdAndCreatedAt: {
    items?: Array<{
      id?: string | null
      createdAt?: string | null
      note?: string | null
    } | null> | null
    nextToken?: string | null
  } | null
}

export default function DataSourceVersionSelector({
  dataSourceId,
  currentVersionId,
  value,
  onChange,
  placeholder = "Select data source version",
  includeAllOption = true,
}: DataSourceVersionSelectorProps) {
  const [versions, setVersions] = useState<DataSourceVersionOption[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!dataSourceId) {
      setVersions([])
      return
    }

    const load = async () => {
      setIsLoading(true)
      try {
        const all: DataSourceVersionOption[] = []
        let nextToken: string | null | undefined = null
        do {
          const response: GraphQLResponse<ListDataSourceVersionByDataSourceIdAndCreatedAtData> = await graphqlRequest(
            `
              query ListDataSourceVersionByDataSourceIdAndCreatedAt(
                $dataSourceId: String!
                $sortDirection: ModelSortDirection
                $limit: Int
                $nextToken: String
              ) {
                listDataSourceVersionByDataSourceIdAndCreatedAt(
                  dataSourceId: $dataSourceId
                  sortDirection: $sortDirection
                  limit: $limit
                  nextToken: $nextToken
                ) {
                  items {
                    id
                    createdAt
                    note
                  }
                  nextToken
                }
              }
            `,
            {
              dataSourceId,
              sortDirection: "DESC",
              limit: 200,
              nextToken: nextToken ?? undefined,
            }
          )
          handleGraphQLErrors(response)
          const result = response.data.listDataSourceVersionByDataSourceIdAndCreatedAt
          const items = Array.isArray(result?.items) ? result.items : []
          all.push(
            ...items
              .filter((item): item is { id: string; createdAt: string; note?: string | null } => (
                !!item && !!item.id && !!item.createdAt
              ))
              .map((item) => ({
                id: item.id,
                createdAt: item.createdAt,
                note: item.note ?? null,
              }))
          )
          nextToken = result?.nextToken
        } while (nextToken)

        setVersions(all)
      } catch (error) {
        console.error("Error loading data source versions:", error)
        setVersions([])
      } finally {
        setIsLoading(false)
      }
    }

    load()
  }, [dataSourceId])

  useEffect(() => {
    if (!value) return
    if (!versions.find((version) => version.id === value)) {
      onChange(null)
    }
  }, [versions, value, onChange])

  const selectValue = value || "__all__"
  const disabled = !dataSourceId || isLoading

  return (
    <Select
      value={selectValue}
      onValueChange={(next) => onChange(next === "__all__" ? null : next)}
      disabled={disabled}
    >
      <SelectTrigger className="w-full h-9 bg-card border-none">
        <SelectValue
          placeholder={!dataSourceId ? "Select a data source first" : isLoading ? "Loading versions..." : placeholder}
        />
      </SelectTrigger>
      <SelectContent className="bg-card border-none">
        {includeAllOption && <SelectItem value="__all__">All Source Versions</SelectItem>}
        {versions.map((version) => (
          <SelectItem key={version.id} value={version.id}>
            {version.id === currentVersionId ? "Current • " : ""}
            {new Date(version.createdAt).toLocaleString()}{" "}
            <span className="text-muted-foreground">({version.id.slice(0, 8)}...)</span>
            {version.note ? <span className="text-muted-foreground"> — {version.note.slice(0, 40)}</span> : null}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
