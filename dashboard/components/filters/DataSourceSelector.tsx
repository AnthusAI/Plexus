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
import { ASSOCIATED_DATASET_SCAFFOLD_DESCRIPTION } from "@/components/data-sources/constants"

export interface DataSourceOption {
  id: string
  name: string
  key?: string | null
  currentVersionId?: string | null
}

interface DataSourceSelectorProps {
  accountId?: string | null
  value: string | null
  onChange: (value: string | null, source: DataSourceOption | null) => void
  placeholder?: string
  includeAllOption?: boolean
}

export default function DataSourceSelector({
  accountId,
  value,
  onChange,
  placeholder = "Select data source",
  includeAllOption = true,
}: DataSourceSelectorProps) {
  const [sources, setSources] = useState<DataSourceOption[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!accountId) {
      setSources([])
      return
    }

    const load = async () => {
      setIsLoading(true)
      try {
        const all: DataSourceOption[] = []
        let nextToken: string | null | undefined = null

        do {
          const response: Awaited<ReturnType<typeof graphqlRequest<any>>> = await graphqlRequest<any>(
            `
              query ListDataSourceByAccountIdAndName(
                $accountId: String!
                $sortDirection: ModelSortDirection
                $limit: Int
                $nextToken: String
              ) {
                listDataSourceByAccountIdAndName(
                  accountId: $accountId
                  sortDirection: $sortDirection
                  limit: $limit
                  nextToken: $nextToken
                ) {
                  items {
                    id
                    name
                    key
                    description
                    currentVersionId
                  }
                  nextToken
                }
              }
            `,
            {
              accountId,
              sortDirection: "ASC",
              limit: 200,
              nextToken: nextToken ?? undefined,
            }
          )
          handleGraphQLErrors(response)
          const result: { items?: any[]; nextToken?: string | null } | undefined = response.data?.listDataSourceByAccountIdAndName
          const items = (result?.items || []) as any[]
          all.push(
            ...items
              .filter(
                (item) =>
                  item?.id &&
                  item?.name &&
                  (item.description || "").trim() !== ASSOCIATED_DATASET_SCAFFOLD_DESCRIPTION
              )
              .map((item) => ({
                id: item.id,
                name: item.name,
                key: item.key ?? null,
                currentVersionId: item.currentVersionId ?? null,
              }))
          )
          nextToken = result?.nextToken
        } while (nextToken)

        setSources(all)
      } catch (error) {
        console.error("Error loading data sources:", error)
        setSources([])
      } finally {
        setIsLoading(false)
      }
    }

    load()
  }, [accountId])

  useEffect(() => {
    if (!value) return
    const found = sources.find((source) => source.id === value)
    if (!found) {
      onChange(null, null)
    }
  }, [sources, value, onChange])

  const selectValue = value || "__all__"
  const disabled = !accountId || isLoading

  return (
    <Select
      value={selectValue}
      onValueChange={(next) => {
        if (next === "__all__") {
          onChange(null, null)
          return
        }
        const found = sources.find((source) => source.id === next) || null
        onChange(next, found)
      }}
      disabled={disabled}
    >
      <SelectTrigger className="w-full h-9 bg-card border-none">
        <SelectValue
          placeholder={!accountId ? "Select an account first" : isLoading ? "Loading data sources..." : placeholder}
        />
      </SelectTrigger>
      <SelectContent className="bg-card border-none">
        {includeAllOption && <SelectItem value="__all__">All Data Sources</SelectItem>}
        {sources.map((source) => (
          <SelectItem key={source.id} value={source.id}>
            {source.name}
            {source.key ? <span className="text-muted-foreground"> ({source.key})</span> : null}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
