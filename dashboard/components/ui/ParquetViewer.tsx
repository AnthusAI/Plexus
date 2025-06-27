import React, { useState, useEffect } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Terminal, Loader2 } from 'lucide-react'
import { downloadData } from 'aws-amplify/storage'

interface ParquetViewerProps {
  filePath: string
  fileName?: string
  hideFileInfo?: boolean
}

interface ParquetData {
  columns: string[]
  rows: Record<string, any>[]
  totalRows: number
  metadata?: any
}

const ParquetViewer: React.FC<ParquetViewerProps> = ({ filePath, fileName, hideFileInfo = false }) => {
  const [data, setData] = useState<ParquetData | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadParquetFile = async () => {
      setIsLoading(true)
      setError(null)
      
      try {
        // Dynamic import of hyparquet
        const { parquetReadObjects, parquetMetadataAsync, parquetSchema } = await import('hyparquet')
        const { compressors } = await import('hyparquet-compressors')
        
        // Determine which storage bucket to use based on file path
        let storageOptions: { path: string; options?: { bucket?: string } } = { path: filePath }
        
        if (filePath.startsWith('datasources/')) {
          // Data source files are stored in the default attachments bucket
          storageOptions = { path: filePath }
        } else if (filePath.startsWith('datasets/')) {
          // Dataset files are stored in the default attachments bucket
          storageOptions = { path: filePath }
        } else if (filePath.startsWith('reportblocks/')) {
          storageOptions = {
            path: filePath,
            options: { bucket: 'reportBlockDetails' }
          }
        } else if (filePath.startsWith('scoreresults/')) {
          storageOptions = {
            path: filePath,
            options: { bucket: 'scoreResultAttachments' }
          }
        }
        
        // Download the file data directly instead of using a URL
        const downloadResult = await downloadData(storageOptions).result
        const arrayBuffer = await (downloadResult.body as any).arrayBuffer()
        
        // Get metadata first to understand the file structure
        const metadata = await parquetMetadataAsync(arrayBuffer)
        const schema = parquetSchema(metadata)
        const totalRows = Number(metadata.num_rows)
        
        // Get column names
        const columns = schema.children.map((child: any) => child.element.name)
        
        // Read a sample of the data (first 100 rows for preview)
        const sampleSize = Math.min(100, totalRows)
        const rows = await parquetReadObjects({
          file: arrayBuffer,
          compressors,
          rowStart: 0,
          rowEnd: sampleSize
        })
        
        setData({
          columns,
          rows,
          totalRows,
          metadata: {
            numRows: totalRows,
            numColumns: columns.length,
            schema: schema
          }
        })
        
      } catch (err) {
        console.error('Error loading Parquet file:', err)
        setError(err instanceof Error ? err.message : 'Failed to load Parquet file')
      } finally {
        setIsLoading(false)
      }
    }

    if (filePath) {
      loadParquetFile()
    } else {
      setError('File path is not provided')
      setIsLoading(false)
    }
  }, [filePath])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 bg-background">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        <span className="text-muted-foreground">Loading Parquet file...</span>
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive" className="mx-4 my-4 bg-background">
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error Loading Parquet File</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!data) {
    return (
      <Alert variant="default" className="mx-4 my-4 bg-background">
        <Terminal className="h-4 w-4" />
        <AlertTitle>No Data</AlertTitle>
        <AlertDescription>No data could be loaded from the Parquet file.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="h-full flex flex-col bg-background">
      {/* File info */}
      {!hideFileInfo && (
        <div className="bg-muted/50 p-3 mx-4 mt-4 rounded-md flex-shrink-0">
          <h4 className="font-medium text-sm mb-2">
            {fileName || 'Parquet File'} Preview
          </h4>
          <div className="text-xs text-muted-foreground space-y-1">
            <div>Total Rows: {data.totalRows.toLocaleString()}</div>
            <div>Columns: {data.columns.length}</div>
            <div>Showing: {data.rows.length} rows</div>
          </div>
        </div>
      )}

      {/* Data table - scrollable */}
      <div className={`flex-1 mx-4 overflow-hidden min-h-0 ${hideFileInfo ? 'mt-4 mb-4' : 'my-4'}`}>
        <div className="h-full overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                {data.columns.map((column, index) => (
                  <th key={index} className="px-3 text-left font-medium text-muted-foreground border-r-2 border-muted last:border-r-0">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-background">
              {data.rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-t-2 border-muted hover:bg-muted/25">
                  {data.columns.map((column, colIndex) => (
                    <td key={colIndex} className="px-3 py-2 border-r-2 border-muted last:border-r-0 max-w-[200px] truncate">
                      {row[column] !== null && row[column] !== undefined 
                        ? String(row[column]) 
                        : <span className="text-muted-foreground italic">null</span>
                      }
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Show message if there are more rows */}
      {data.totalRows > data.rows.length && (
        <div className="text-xs text-muted-foreground text-center p-2 mx-4 mb-4 bg-muted/25 rounded-md flex-shrink-0">
          Showing first {data.rows.length} of {data.totalRows.toLocaleString()} total rows
        </div>
      )}
    </div>
  )
}

export default ParquetViewer 