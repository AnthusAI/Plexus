"use client"

import React, { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useAccount } from "@/app/contexts/AccountContext"
import { ScorecardDashboardSkeleton } from "@/components/loading-skeleton"
import DataSetComponent from "@/components/data-sets/DataSetComponent"
import type { Schema } from "@/amplify/data/resource"
import { listDataSetsForBrowse, type AssociatedDataSetFilterType } from "@/components/data-sets/data-set-query"
import { amplifyClient } from "@/utils/amplify-client"
import ScorecardContext from "@/components/ScorecardContext"
import ScoreVersionSelector from "@/components/filters/ScoreVersionSelector"
import DataSourceSelector from "@/components/filters/DataSourceSelector"
import DataSourceVersionSelector from "@/components/filters/DataSourceVersionSelector"

interface AssociatedDataSetsDashboardProps {
  selectedDatasetId?: string
  pathBase?: string
}

type FilterMode = "all" | "byScore" | "bySourceVersion"

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

  const [filterMode, setFilterMode] = useState<FilterMode>("all")
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [selectedScoreVersion, setSelectedScoreVersion] = useState<string | null>(null)
  const [selectedDataSourceId, setSelectedDataSourceId] = useState<string | null>(null)
  const [selectedDataSourceCurrentVersionId, setSelectedDataSourceCurrentVersionId] = useState<string | null>(null)
  const [selectedDataSourceVersion, setSelectedDataSourceVersion] = useState<string | null>(null)

  const resolvedFilter = useMemo<{
    filterType: AssociatedDataSetFilterType
    filterValue: string | null
  }>(() => {
    if (filterMode === "all") {
      return { filterType: "all", filterValue: selectedAccount?.id || null }
    }

    if (filterMode === "byScore") {
      if (selectedScoreVersion) {
        return { filterType: "scoreVersion", filterValue: selectedScoreVersion }
      }
      if (selectedScore) {
        return { filterType: "score", filterValue: selectedScore }
      }
      if (selectedScorecard) {
        return { filterType: "scorecard", filterValue: selectedScorecard }
      }
      return { filterType: "score", filterValue: null }
    }

    if (selectedDataSourceVersion) {
      return { filterType: "dataSourceVersion", filterValue: selectedDataSourceVersion }
    }

    return { filterType: "dataSourceVersion", filterValue: null }
  }, [
    filterMode,
    selectedAccount?.id,
    selectedScorecard,
    selectedScore,
    selectedScoreVersion,
    selectedDataSourceVersion,
  ])

  const loadDataSets = async () => {
    try {
      if (!selectedAccount?.id) {
        setDatasets([])
        setIsLoading(false)
        return
      }

      if (!resolvedFilter.filterValue) {
        setDatasets([])
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      setError(null)

      const items = await listDataSetsForBrowse({
        accountId: selectedAccount.id,
        mode: 'associated',
        associatedFilter: resolvedFilter.filterType,
        associatedFilterValue: resolvedFilter.filterValue,
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
  }, [selectedAccount?.id, resolvedFilter])

  useEffect(() => {
    if (!selectedScore) {
      setSelectedScoreVersion(null)
    }
  }, [selectedScore])

  useEffect(() => {
    if (!selectedDataSourceId) {
      setSelectedDataSourceCurrentVersionId(null)
      setSelectedDataSourceVersion(null)
    }
  }, [selectedDataSourceId])

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

  const handleModeChange = (value: string) => {
    const next = (value || "all") as FilterMode
    setFilterMode(next)
    if (next === "all") {
      setSelectedScorecard(null)
      setSelectedScore(null)
      setSelectedScoreVersion(null)
      setSelectedDataSourceId(null)
      setSelectedDataSourceCurrentVersionId(null)
      setSelectedDataSourceVersion(null)
      return
    }

    if (next === "byScore") {
      setSelectedDataSourceId(null)
      setSelectedDataSourceCurrentVersionId(null)
      setSelectedDataSourceVersion(null)
      return
    }

    setSelectedScorecard(null)
    setSelectedScore(null)
    setSelectedScoreVersion(null)
  }

  if (isLoading) {
    return <ScorecardDashboardSkeleton />
  }

  return (
    <div className="flex h-full min-h-0 gap-3 overflow-hidden p-3">
      <div className={`flex min-h-0 flex-col overflow-hidden ${selectedDataSet ? 'w-1/2' : 'w-full'}`}>
        <div className="mb-3 flex flex-col gap-2">
          <ToggleGroup
            type="single"
            value={filterMode}
            onValueChange={handleModeChange}
            className="justify-start"
          >
            <ToggleGroupItem value="all" variant="outline" size="sm">
              All
            </ToggleGroupItem>
            <ToggleGroupItem value="byScore" variant="outline" size="sm">
              By Score
            </ToggleGroupItem>
            <ToggleGroupItem value="bySourceVersion" variant="outline" size="sm">
              By Source Version
            </ToggleGroupItem>
          </ToggleGroup>

          {filterMode === "byScore" && (
            <div className="flex flex-col gap-2">
              <ScorecardContext
                selectedScorecard={selectedScorecard}
                setSelectedScorecard={setSelectedScorecard}
                selectedScore={selectedScore}
                setSelectedScore={setSelectedScore}
              />
              <ScoreVersionSelector
                scoreId={selectedScore}
                value={selectedScoreVersion}
                onChange={setSelectedScoreVersion}
                placeholder="Select score version (optional)"
                includeAllOption
              />
            </div>
          )}

          {filterMode === "bySourceVersion" && (
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <DataSourceSelector
                accountId={selectedAccount?.id || null}
                value={selectedDataSourceId}
                onChange={(sourceId, source) => {
                  setSelectedDataSourceId(sourceId)
                  setSelectedDataSourceCurrentVersionId(source?.currentVersionId || null)
                  setSelectedDataSourceVersion(null)
                }}
                includeAllOption={false}
              />
              <DataSourceVersionSelector
                dataSourceId={selectedDataSourceId}
                currentVersionId={selectedDataSourceCurrentVersionId}
                value={selectedDataSourceVersion}
                onChange={setSelectedDataSourceVersion}
                includeAllOption={false}
              />
            </div>
          )}

          {filterMode === "byScore" && !resolvedFilter.filterValue && (
            <div className="text-xs text-muted-foreground">
              Select a scorecard or score to view dataset results.
            </div>
          )}
          {filterMode === "bySourceVersion" && !resolvedFilter.filterValue && (
            <div className="text-xs text-muted-foreground">
              Select a data source and a source version to view dataset results.
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                setFilterMode("all")
                setSelectedScorecard(null)
                setSelectedScore(null)
                setSelectedScoreVersion(null)
                setSelectedDataSourceId(null)
                setSelectedDataSourceCurrentVersionId(null)
                setSelectedDataSourceVersion(null)
              }}
              className="bg-card"
            >
              Clear filters
            </Button>
            <Button variant="ghost" onClick={() => loadDataSets()} className="bg-card">
              Refresh
            </Button>
          </div>
        </div>

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
