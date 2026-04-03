"use client"

import React, { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useAccount } from "@/app/contexts/AccountContext"
import { ScorecardDashboardSkeleton } from "@/components/loading-skeleton"
import DataSetComponent from "@/components/data-sets/DataSetComponent"
import type { Schema } from "@/amplify/data/resource"
import { listDataSetsForBrowse, type AssociatedDataSetFilterType } from "@/components/data-sets/data-set-query"
import { amplifyClient } from "@/utils/amplify-client"

interface AssociatedDataSetsDashboardProps {
  selectedDatasetId?: string
  pathBase?: string
}

export default function AssociatedDataSetsDashboard({
  selectedDatasetId,
  pathBase = '/lab/datasets',
}: AssociatedDataSetsDashboardProps = {}) {
  const { selectedAccount } = useAccount()
  const router = useRouter()

  const [datasets, setDatasets] = useState<Schema['DataSet']['type'][]>([])
  const [selectedDataSet, setSelectedDataSet] = useState<Schema['DataSet']['type'] | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [associatedFilter, setAssociatedFilter] = useState<AssociatedDataSetFilterType>('all')
  const [filterValue, setFilterValue] = useState('')

  const normalizedFilterValue = useMemo(() => filterValue.trim(), [filterValue])
  const requiresFilterValue = associatedFilter !== 'all'

  const loadDataSets = async () => {
    try {
      if (!selectedAccount?.id) {
        setDatasets([])
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      setError(null)

      if (requiresFilterValue && !normalizedFilterValue) {
        setDatasets([])
        return
      }

      const items = await listDataSetsForBrowse({
        accountId: selectedAccount.id,
        mode: 'associated',
        associatedFilter,
        associatedFilterValue: normalizedFilterValue || null,
      })

      setDatasets(items)
    } catch (err) {
      console.error('Error loading datasets:', err)
      setError(err instanceof Error ? err.message : 'Failed to load datasets')
      setDatasets([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadDataSets()
  }, [selectedAccount?.id, associatedFilter, normalizedFilterValue])

  useEffect(() => {
    if (!selectedDatasetId) {
      setSelectedDataSet(null)
      return
    }

    const fromList = datasets.find((dataset) => dataset.id === selectedDatasetId)
    if (fromList) {
      setSelectedDataSet(fromList)
      return
    }

    const loadSelected = async () => {
      try {
        const response = await amplifyClient.DataSet.get({ id: selectedDatasetId })
        setSelectedDataSet(response.data)
      } catch {
        setSelectedDataSet(null)
      }
    }

    loadSelected()
  }, [selectedDatasetId, datasets])

  const handleSelectDataSet = (dataset: Schema['DataSet']['type']) => {
    setSelectedDataSet(dataset)
    router.push(`${pathBase}/${dataset.id}`)
  }

  const handleCloseDataSet = () => {
    setSelectedDataSet(null)
    router.push('/lab/datasets')
  }

  if (isLoading) {
    return <ScorecardDashboardSkeleton />
  }

  const filterLabel =
    associatedFilter === 'all'
      ? 'All (account)'
      : associatedFilter === 'scorecard'
        ? 'Scorecard ID'
        : associatedFilter === 'score'
          ? 'Score ID'
          : associatedFilter === 'scoreVersion'
            ? 'Score Version ID'
            : 'Data Source Version ID'

  return (
    <div className="flex h-full min-h-0 gap-3 overflow-hidden p-3">
      <div className={`flex min-h-0 flex-col overflow-hidden ${selectedDataSet ? 'w-1/2' : 'w-full'}`}>
        <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center">
          <Select
            value={associatedFilter}
            onValueChange={(value) => {
              setAssociatedFilter(value as AssociatedDataSetFilterType)
              setFilterValue('')
            }}
          >
            <SelectTrigger className="w-full md:w-[260px] bg-card border-0">
              <SelectValue placeholder="Choose filter" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All (account)</SelectItem>
              <SelectItem value="scorecard">Scorecard ID</SelectItem>
              <SelectItem value="score">Score ID</SelectItem>
              <SelectItem value="scoreVersion">Score Version ID</SelectItem>
              <SelectItem value="dataSourceVersion">Data Source Version ID</SelectItem>
            </SelectContent>
          </Select>
          {requiresFilterValue && (
            <Input
              value={filterValue}
              onChange={(event) => setFilterValue(event.target.value)}
              placeholder={`Enter ${filterLabel}`}
              className="w-full md:max-w-[420px]"
            />
          )}
          <Button variant="ghost" onClick={() => loadDataSets()} className="bg-card">
            Refresh
          </Button>
        </div>
        {requiresFilterValue && !normalizedFilterValue && (
          <div className="mb-3 text-xs text-muted-foreground">
            Enter a value for <span className="font-medium">{filterLabel}</span> to run this indexed filter.
          </div>
        )}

        {error ? (
          <div className="text-sm text-red-500">Error loading datasets: {error}</div>
        ) : (
          <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-auto @[600px]:grid-cols-2 @[1000px]:grid-cols-3">
            {datasets.map((dataset) => (
              <DataSetComponent
                key={dataset.id}
                variant="grid"
                dataSet={dataset}
                isSelected={selectedDataSet?.id === dataset.id}
                onClick={() => handleSelectDataSet(dataset)}
              />
            ))}
          </div>
        )}
      </div>

      {selectedDataSet && (
        <div className="w-1/2 min-h-0 overflow-hidden">
          <DataSetComponent
            variant="detail"
            dataSet={selectedDataSet}
            onClose={handleCloseDataSet}
          />
        </div>
      )}
    </div>
  )
}
