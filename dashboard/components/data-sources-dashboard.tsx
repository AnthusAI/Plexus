"use client"

import React, { useState, useEffect, useRef } from "react"
import { Button } from "./ui/button"
import { amplifyClient } from "@/utils/amplify-client"
import type { Schema } from "@/amplify/data/resource"
import { Plus } from "lucide-react"
import ScorecardContext from "@/components/ScorecardContext"
import DataSourceComponent from "./data-sources/DataSourceComponent"
import DataSetComponent from "./data-sets/DataSetComponent"
import { cn } from "@/lib/utils"
import { useAccount } from "@/app/contexts/AccountContext"
import { ScorecardDashboardSkeleton } from "./loading-skeleton"
import { motion, AnimatePresence } from 'framer-motion'


export default function DataSourcesDashboard() {
  const { selectedAccount } = useAccount()
  const [dataSources, setDataSources] = useState<Schema['DataSource']['type'][]>([])
  const [dataSets, setDataSets] = useState<Schema['DataSet']['type'][]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedDataSource, setSelectedDataSource] = useState<Schema['DataSource']['type'] | null>(null)
  const [selectedDataSet, setSelectedDataSet] = useState<Schema['DataSet']['type'] | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [leftPanelWidth, setLeftPanelWidth] = useState(40)
  const [dataSourcePanelWidth, setDataSourcePanelWidth] = useState(50)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [isDataSetFullWidth, setIsDataSetFullWidth] = useState(false)
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  const [dataSetAnimationComplete, setDataSetAnimationComplete] = useState(false)
  
  // Track when we previously had a dataset to handle proper close animations
  const previouslyHadDataSet = useRef<boolean>(false)

  // Monitor viewport width for responsive layout
  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 768) // md breakpoint
    }
    
    checkViewportWidth() // Initial check
    window.addEventListener('resize', checkViewportWidth)
    
    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  // Auto-set full width on narrow viewports when data source is selected
  useEffect(() => {
    if (isNarrowViewport && selectedDataSource) {
      setIsFullWidth(true)
    } else if (!isNarrowViewport && selectedDataSource) {
      setIsFullWidth(false)
    }
  }, [isNarrowViewport, selectedDataSource])

  // Fetch data sources
  const fetchDataSources = async () => {
    try {
      if (!selectedAccount?.id) {
        setDataSources([])
        setIsLoading(false)
        return
      }

      console.log('=== FETCHING DATA SOURCES ===')
      // Fetch real data sources for the selected account
      const result = await amplifyClient.DataSource.list({
        filter: { accountId: { eq: selectedAccount.id } }
      })

      console.log('Raw data sources from database:', result.data.map(ds => ({
        id: ds.id,
        name: ds.name,
        attachedFiles: ds.attachedFiles,
        attachedFilesLength: ds.attachedFiles?.length || 0
      })))

      // Sort by updatedAt descending manually
      const sortedData = [...result.data].sort((a, b) => 
        new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      )
      setDataSources(sortedData)
      
      setIsLoading(false)
    } catch (error) {
      console.error('Error fetching data sources:', error)
      setError(error as Error)
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchDataSources()
  }, [selectedAccount])

  // Fetch datasets for a specific data source
  const fetchDataSets = async (dataSourceId: string) => {
    try {
      // Fetch datasets associated with this data source
      const result = await amplifyClient.DataSet.list({
        filter: { 
          accountId: { eq: selectedAccount?.id || '' }
          // Note: You may need to add a GSI for dataSourceVersionId if you want to filter by it
        }
      })

      // Filter datasets that belong to this data source and sort by createdAt descending
      const filteredDataSets = result.data
        .filter(dataSet => {
          // For now, we'll use a simple approach - you may need to adjust this
          // based on how you want to associate datasets with data sources
          return dataSet.accountId === selectedAccount?.id
        })
        .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())

      setDataSets(filteredDataSets)
    } catch (error) {
      console.error('Error fetching datasets:', error)
      setDataSets([])
    }
  }

  // Handle data source selection
  const handleSelectDataSource = (dataSource: Schema['DataSource']['type'] | null) => {
    setSelectedDataSource(dataSource)
    setSelectedDataSet(null) // Clear any selected dataset when switching data sources
    
    // Load datasets for the selected data source
    if (dataSource && selectedAccount?.id) {
      fetchDataSets(dataSource.id)
    } else {
      setDataSets([])
    }
  }

  // Handle dataset selection
  const handleSelectDataSet = (dataSet: Schema['DataSet']['type'] | null) => {
    setSelectedDataSet(dataSet)
    // Reset animation state when selecting a new dataset
    setDataSetAnimationComplete(false)
  }
  
  // Track when we have a dataset
  useEffect(() => {
    if (selectedDataSet) {
      previouslyHadDataSet.current = true
    }
  }, [selectedDataSet])
  
  // Clear the flag when data source changes
  useEffect(() => {
    return () => {
      previouslyHadDataSet.current = false
    }
  }, [selectedDataSource])

  // Handle data source deletion
  const handleDeleteDataSource = async (dataSource: Schema['DataSource']['type']) => {
    if (!confirm(`Are you sure you want to delete "${dataSource.name}"? This action cannot be undone.`)) {
      return
    }

    try {
      await amplifyClient.DataSource.delete({ id: dataSource.id })
      // Refresh the data sources list
      await fetchDataSources()
      // If we're currently viewing the deleted data source, close it
      if (selectedDataSource?.id === dataSource.id) {
        handleCloseDataSource()
      }
    } catch (error) {
      console.error('Error deleting data source:', error)
      alert('Failed to delete data source. Please try again.')
    }
  }

  // Handle data source loading
  const handleLoadDataSource = (dataSource: Schema['DataSource']['type']) => {
    // TODO: Implement load functionality
    console.log('Load data source:', dataSource)
    alert('Load functionality will be implemented soon.')
  }

  // Handle data source duplication
  const handleDuplicateDataSource = async (dataSource: Schema['DataSource']['type']) => {
    console.log('Duplicate button clicked for:', dataSource.name)
    if (!selectedAccount?.id) {
      console.error('No selected account ID')
      alert('No account selected. Please try again.')
      return
    }

    try {
      console.log('Creating duplicate with data:', {
        name: `${dataSource.name} copy`,
        key: dataSource.key ? `${dataSource.key}-copy` : undefined,
        accountId: selectedAccount.id
      })
      
      // Prepare the data, only including non-null fields
      const createData: any = {
        name: `${dataSource.name} copy`,
        accountId: selectedAccount.id,
      }
      
      // Only add optional fields if they have values
      if (dataSource.key && dataSource.key.trim()) {
        createData.key = `${dataSource.key.trim()}-copy`
      }
      if (dataSource.description && dataSource.description.trim()) {
        createData.description = dataSource.description.trim()
      }
      if (dataSource.yamlConfiguration && dataSource.yamlConfiguration.trim()) {
        createData.yamlConfiguration = dataSource.yamlConfiguration.trim()
      }
      if (dataSource.attachedFiles && dataSource.attachedFiles.length > 0) {
        createData.attachedFiles = [...dataSource.attachedFiles]
      }
      if (dataSource.scorecardId) {
        createData.scorecardId = dataSource.scorecardId
      }
      if (dataSource.scoreId) {
        createData.scoreId = dataSource.scoreId
      }
      if (dataSource.currentVersionId) {
        createData.currentVersionId = dataSource.currentVersionId
      }
      
      console.log('Final create data:', createData)
      
      const duplicatedDataSource = await amplifyClient.DataSource.create(createData)

      console.log('Duplicate creation result:', duplicatedDataSource)

      // Refresh the data sources list
      await fetchDataSources()
      console.log('Data sources refreshed')
      
      // Navigate to the duplicated data source
      if (duplicatedDataSource.data) {
        console.log('Navigating to duplicated data source:', duplicatedDataSource.data.id)
        handleSelectDataSource(duplicatedDataSource.data)
      } else {
        console.warn('No data in duplicate result')
      }
    } catch (error) {
      console.error('Error duplicating data source:', error)
      console.error('Error details:', JSON.stringify(error, null, 2))
      alert('Failed to duplicate data source. Please try again.')
    }
  }

  // Handle creating a new data source
  const handleCreate = () => {
    if (!selectedAccount?.id) return

    const blankDataSource = {
      id: '',
      name: '',
      key: '',
      description: '',
      yamlConfiguration: '',
      attachedFiles: [],
      accountId: selectedAccount.id,
      scorecardId: null,
      scoreId: null,
      currentVersionId: null,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    } as unknown as Schema['DataSource']['type']

    handleSelectDataSource(blankDataSource)
  }

  // Handle closing the selected data source
  const handleCloseDataSource = () => {
    setSelectedDataSource(null)
    setSelectedDataSet(null)
    setDataSets([])
    setIsFullWidth(false)
  }

  // Handle closing the selected dataset
  const handleCloseDataSet = () => {
    setSelectedDataSet(null)
    setIsDataSetFullWidth(false)
    setDataSetAnimationComplete(false)
  }

  // Handle drag for resizing panels (grid/data source)
  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.pageX
    const startWidth = leftPanelWidth

    const handleDrag = (e: MouseEvent) => {
      const delta = e.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 30), 70)
      setLeftPanelWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
  }

  // Handle drag for resizing data source/dataset panels
  const handleDataSourceDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.pageX
    const startWidth = dataSourcePanelWidth

    const handleDrag = (e: MouseEvent) => {
      const delta = e.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 30), 70)
      setDataSourcePanelWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="text-red-500 mb-2">
          Error loading data sources: {error.message}
        </div>
      </div>
    )
  }

  if (isLoading) {
    return <ScorecardDashboardSkeleton />
  }

  return (
    <div className="@container flex flex-col h-full p-3 overflow-hidden">


      <div className="flex flex-1 min-h-0">
        {/* Left panel - grid content */}
        <motion.div 
          className="h-full overflow-auto overflow-x-visible"
          animate={{
            width: selectedDataSource && !isNarrowViewport && (isFullWidth || selectedDataSet) 
              ? 0 
              : selectedDataSource && !isNarrowViewport && !isFullWidth && !selectedDataSet 
                ? `${leftPanelWidth}%`
                : '100%'
          }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            flexShrink: 0,
            overflow: selectedDataSource && !isNarrowViewport && (isFullWidth || selectedDataSet) ? 'hidden' : 'auto'
          }}
        >
          {/* Grid content or selected content for mobile */}
          <div className="@container space-y-3 overflow-visible">
            {isNarrowViewport && (selectedDataSource || selectedDataSet) ? (
              // Mobile full-screen view
              <div className="h-full">
                {selectedDataSet ? (
                  // For mobile, render immediately since there's no sliding animation
                  <DataSetComponent
                    variant="detail"
                    dataSet={selectedDataSet}
                    onClose={handleCloseDataSet}
                    isFullWidth={isDataSetFullWidth}
                    onToggleFullWidth={() => setIsDataSetFullWidth(!isDataSetFullWidth)}
                  />
                ) : selectedDataSource ? (
                  <DataSourceComponent
                    variant="detail"
                    dataSource={selectedDataSource}
                    isFullWidth={isFullWidth}
                    onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                    onClose={handleCloseDataSource}
                    onSave={async (savedDataSource?: Schema['DataSource']['type']) => {
                      await fetchDataSources()
                      if (savedDataSource && selectedDataSource?.id === '') {
                        handleCloseDataSource()
                      }
                    }}
                    onDelete={handleDeleteDataSource}
                    onLoad={handleLoadDataSource}
                    onDuplicate={handleDuplicateDataSource}
                    dataSets={dataSets}
                    onDataSetSelect={handleSelectDataSet}
                    selectedDataSetId={undefined}
                    accountId={selectedAccount?.id}
                  />
                ) : null}
              </div>
            ) : (
              // Grid view
              <>
                <div className="flex justify-end">
                  <Button 
                    onClick={handleCreate} 
                    variant="ghost" 
                    className="bg-card hover:bg-accent text-muted-foreground"
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    New Data Source
                  </Button>
                </div>
                <div className="@container">
                  <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-3">
                    {dataSources.map(dataSource => (
                      <DataSourceComponent
                        key={dataSource.id}
                        variant="grid"
                        dataSource={dataSource}
                        isSelected={selectedDataSource?.id === dataSource.id}
                        onClick={() => handleSelectDataSource(dataSource)}
                      />
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        </motion.div>

        {/* Divider for split view */}
        {selectedDataSource && !isNarrowViewport && !isFullWidth && !selectedDataSet && (
          <div
            className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
            onMouseDown={handleDragStart}
          >
            <div className="absolute inset-0 rounded-full transition-colors duration-150 
              group-hover:bg-accent" />
          </div>
        )}

        {/* Right panel - data source and dataset detail views */}
        <AnimatePresence>
          {selectedDataSource && !isNarrowViewport && (
            <>
              {selectedDataSet ? (
                // When dataset is selected, show DataSource and DataSet side by side
                <motion.div
                  key="split-view"
                  initial={{ x: 0 }}
                  animate={{ x: 0 }}
                  exit={{ x: 0 }}
                  className="flex h-full overflow-hidden w-full"
                >
                  {/* Data source panel - slides from right to left, keeps same width */}
                  <motion.div 
                    key="datasource-in-split"
                    initial={{ x: isFullWidth ? 0 : `${100 - leftPanelWidth}%` }}
                    animate={{ 
                      x: isDataSetFullWidth ? '-100%' : 0,
                      width: isDataSetFullWidth ? '0%' : `${dataSourcePanelWidth}%`,
                      opacity: isDataSetFullWidth ? 0 : 1
                    }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    className="h-full overflow-hidden flex-1"
                  >
                    <DataSourceComponent
                      variant="detail"
                      dataSource={selectedDataSource}
                      isFullWidth={false}
                      onClose={handleCloseDataSource}
                      onSave={async (savedDataSource?: Schema['DataSource']['type']) => {
                        await fetchDataSources()
                        if (savedDataSource && selectedDataSource?.id === '') {
                          handleCloseDataSource()
                        }
                      }}
                      onDelete={handleDeleteDataSource}
                      onLoad={handleLoadDataSource}
                      onDuplicate={handleDuplicateDataSource}
                      dataSets={dataSets}
                      onDataSetSelect={handleSelectDataSet}
                      selectedDataSetId={selectedDataSet.id}
                      accountId={selectedAccount?.id}
                    />
                  </motion.div>
                  
                  {/* Divider between DataSource and DataSet */}
                  {!isNarrowViewport && (
                    <motion.div
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ 
                        opacity: isDataSetFullWidth ? 0 : 1, 
                        width: isDataSetFullWidth ? 0 : 12 
                      }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.3 }}
                      className="relative cursor-col-resize flex-shrink-0 group"
                      onMouseDown={handleDataSourceDragStart}
                    >
                      <div className="absolute inset-0 rounded-full transition-colors duration-150 
                        group-hover:bg-accent" />
                    </motion.div>
                  )}
                  
                  {/* Dataset panel - slides in from right */}
                  <motion.div 
                    key={`dataset-${selectedDataSet.id}`}
                    initial={{ x: '100%', opacity: 0 }}
                    animate={{ 
                      x: 0, 
                      opacity: 1,
                      width: isDataSetFullWidth ? '100%' : `${100 - dataSourcePanelWidth}%`
                    }}
                    exit={{ x: '100%', opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    onAnimationComplete={() => setDataSetAnimationComplete(true)}
                    className="h-full overflow-hidden"
                  >
                    {dataSetAnimationComplete ? (
                      <DataSetComponent
                        variant="detail"
                        dataSet={selectedDataSet}
                        onClose={handleCloseDataSet}
                        isFullWidth={isDataSetFullWidth}
                        onToggleFullWidth={() => setIsDataSetFullWidth(!isDataSetFullWidth)}
                      />
                    ) : (
                      <div className="h-full w-full bg-card flex items-center justify-center">
                        <div className="text-muted-foreground">Loading dataset...</div>
                      </div>
                    )}
                  </motion.div>
                </motion.div>
              ) : (
                // When no dataset is selected, show normal data source view
                <motion.div
                  key={`datasource-${selectedDataSource.id}-solo`}
                  initial={{ 
                    x: previouslyHadDataSet.current ? '-50%' : '100%', 
                    opacity: previouslyHadDataSet.current ? 1 : 0,
                    width: isFullWidth ? '100%' : `${100 - leftPanelWidth}%`
                  }}
                  animate={{ 
                    x: 0, 
                    opacity: 1,
                    width: isFullWidth ? '100%' : `${100 - leftPanelWidth}%`
                  }}
                  exit={{ x: '100%', opacity: 0 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  onAnimationComplete={() => {
                    // Reset the flag after animation completes
                    if (previouslyHadDataSet.current) {
                      previouslyHadDataSet.current = false
                    }
                  }}
                  className="h-full overflow-hidden"
                >
                  <DataSourceComponent
                    variant="detail"
                    dataSource={selectedDataSource}
                    isFullWidth={isFullWidth}
                    onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
                    onClose={handleCloseDataSource}
                    onSave={async (savedDataSource?: Schema['DataSource']['type']) => {
                      await fetchDataSources()
                      if (savedDataSource && selectedDataSource?.id === '') {
                        handleCloseDataSource()
                      }
                    }}
                    onDelete={handleDeleteDataSource}
                    onLoad={handleLoadDataSource}
                    onDuplicate={handleDuplicateDataSource}
                    dataSets={dataSets}
                    onDataSetSelect={handleSelectDataSet}
                    selectedDataSetId={undefined}
                    accountId={selectedAccount?.id}
                  />
                </motion.div>
              )}
            </>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}