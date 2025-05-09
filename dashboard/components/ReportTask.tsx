import React, { useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FileBarChart, Clock } from 'lucide-react'
import { format, formatDistanceToNow } from 'date-fns'
import { Timestamp } from '@/components/ui/timestamp'
import ReactMarkdown from 'react-markdown'
import { BlockRenderer } from './blocks/BlockRegistry'
import { getClient } from '@/utils/amplify-client'

// Define the data structure for report tasks
export interface ReportTaskData {
  id: string;
  title: string; // Required by BaseTaskData
  name?: string | null;
  configName?: string | null;
  configDescription?: string | null;
  createdAt?: string | null;
  /** 
   * Last updated timestamp of the report - used for displaying the "last updated" time 
   * This is preferred over task.time when available
   */
  updatedAt?: string | null;
  /** 
   * Markdown content of the report - shown in detail view 
   */
  output?: string | null;
  /**
   * Report blocks data from the backend
   */
  reportBlocks?: Array<{
    type: string;
    config: Record<string, any>;
    output: Record<string, any>;
    log?: string;
    name?: string;
    position: number;
  }>;
}

// Props for the ReportTask component
export interface ReportTaskProps extends BaseTaskProps<ReportTaskData> {}

// Add interface for report blocks
interface ReportBlock {
  id: string
  name?: string | null
  position: number
  type: string
  output: Record<string, any>
  log?: string | null
  config?: Record<string, any>  // Add config field
}

const ReportTask: React.FC<ReportTaskProps> = ({ 
  variant, 
  task, 
  onClick, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
  // Add state for report blocks
  const [reportBlocks, setReportBlocks] = useState<ReportBlock[]>([])
  const [isLoadingBlocks, setIsLoadingBlocks] = useState(false)
  const [blockError, setBlockError] = useState<string | null>(null)

  // Function to fetch report blocks
  const fetchReportBlocks = async (reportId: string) => {
    console.log('Starting to fetch blocks for report:', reportId)
    setIsLoadingBlocks(true)
    setBlockError(null)
    try {
      const response = await getClient().graphql({
        query: `
          query GetReportBlocks($reportId: ID!) {
            getReport(id: $reportId) {
              reportBlocks {
                items {
                  id
                  name
                  position
                  type
                  output
                  log
                }
              }
            }
          }
        `,
        variables: { reportId }
      })

      console.log('Received response for report blocks:', response)

      if ('data' in response && response.data?.getReport?.reportBlocks?.items) {
        const blocks = response.data.getReport.reportBlocks.items.map((block: any) => ({
          ...block,
          output: JSON.parse(block.output),
          config: {}  // Add empty config object by default
        }))
        console.log('Found blocks:', blocks)
        setReportBlocks(blocks)
      } else {
        console.log('No blocks found in response')
      }
    } catch (err: any) {
      console.error('Error fetching report blocks:', err)
      setBlockError(err.message || 'Failed to load report blocks')
    } finally {
      setIsLoadingBlocks(false)
    }
  }

  // Fetch blocks when report is selected and we're in detail view
  useEffect(() => {
    if (variant === 'detail' && task.data?.id) {
      console.log('Effect triggered - fetching blocks for report:', task.data.id)
      fetchReportBlocks(task.data.id)
    }
  }, [variant, task.data?.id])

  // Format the timestamp for detail view display
  const formattedDetailTimestamp = task.data?.updatedAt 
    ? format(new Date(task.data.updatedAt), 'MMM d, yyyy h:mm a')
    : '';

  // Helper to check if a value exists and is not empty
  const getValueOrEmpty = (value: string | null | undefined): string => {
    return value && value.trim() !== '' ? value : '';
  };

  // Explicitly set the name and description in the correct order
  // name = Report name (from report.name)
  // description = Report configuration description
  const reportName = task.data?.configName || 'Report';
  const reportDescription = getValueOrEmpty(task.data?.configDescription);

  // Create a properly typed data object
  const reportData: ReportTaskData = {
    id: task.data?.id || task.id,
    title: task.data?.title || reportName,
    name: task.data?.name || null,
    configName: task.data?.configName || null,
    configDescription: task.data?.configDescription || null,
    createdAt: task.data?.createdAt || null,
    updatedAt: task.data?.updatedAt || null,
    output: task.data?.output || null,
    reportBlocks: task.data?.reportBlocks || []
  };

  // Update the customCodeBlockRenderer function to extract data correctly
  const customCodeBlockRenderer = ({ node, inline, className, children, ...props }: any) => {
    // If it's an inline code block, render normally
    if (inline) {
      return <code className={className} {...props}>{children}</code>;
    }
    
    // For block code, find the corresponding block and use its output
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    
    console.log('Processing code block:', {
      language,
      className,
      children: String(children).trim(),
      availableBlocks: reportBlocks
    });
    
    // Check if this is a report block by looking for the language-block class
    if (language === 'block') {
      const content = String(children).trim();
      
      // Parse the YAML-like content
      const lines = content.split('\n');
      const blockConfig: Record<string, any> = {};
      
      lines.forEach(line => {
        const [key, value] = line.split(':').map(s => s.trim());
        if (key && value) {
          blockConfig[key] = value;
        }
      });
      
      console.log('Parsed block config:', blockConfig);
      
      // Find the corresponding block data from reportBlocks
      const blockData = reportBlocks.find(block => {
        console.log('Checking block:', {
          blockType: block.type,
          configClass: blockConfig.class,
          matches: block.type === blockConfig.class
        });
        return block.type === blockConfig.class;
      });
      
      if (blockData) {
        console.log('Found matching block:', blockData);
        
        return (
          <BlockRenderer
            key={blockData.id}
            config={blockData.config || {}}
            output={blockData.output}
            log={blockData.log || undefined}
            name={blockData.name || blockConfig.name || undefined}
            position={blockData.position}
            type={blockData.type}
          />
        );
      }
    }
    
    // If not a report block or no matching block found, render as normal code block with proper wrapping
    return (
      <div className="w-full min-w-0 max-w-full overflow-x-auto">
        <code className="bg-muted px-1 py-0.5 rounded block w-full min-w-0 max-w-full whitespace-pre-wrap break-all" {...props}>
          {children}
        </code>
      </div>
    );
  };

  return (
    <Task 
      variant={variant} 
      task={{
        ...task,
        // Explicitly set name and description in the right order
        name: reportName, 
        description: reportDescription,
        // Empty scorecard and score to prevent automatic generation
        scorecard: '',
        score: '',
        // Use properly typed data object
        data: reportData
      }}
      onClick={onClick} 
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <FileBarChart className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} hideTaskStatus={true}>
          {variant === 'detail' && task.data?.output && (
            <div className="prose dark:prose-invert max-w-none overflow-y-auto flex-1 min-h-0">
              <ReactMarkdown
                components={{
                  p: ({node, ...props}) => <p className="mb-2" {...props} />,
                  strong: ({node, ...props}) => <strong className="font-semibold" {...props} />,
                  ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-2" {...props} />,
                  li: ({node, ...props}) => <li className="mb-1" {...props} />,
                  h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-4 mb-2" {...props} />,
                  h2: ({node, ...props}) => <h2 className="text-xl font-bold mt-4 mb-2" {...props} />,
                  h3: ({node, ...props}) => <h3 className="text-lg font-bold mt-3 mb-1" {...props} />,
                  h4: ({node, ...props}) => <h4 className="text-base font-bold mt-2 mb-1" {...props} />,
                  code: ({node, className, children, ...props}: any) => {
                    const match = /language-(\w+)/.exec(className || '');
                    const language = match ? match[1] : '';
                    
                    if (language === 'block') {
                      return customCodeBlockRenderer({ node, className, children, ...props });
                    }
                    
                    return (
                      <div className="w-full min-w-0 max-w-full overflow-x-auto">
                        <code className="bg-muted px-1 py-0.5 rounded block whitespace-pre-wrap break-all" {...props}>
                          {children}
                        </code>
                      </div>
                    );
                  },
                  pre: ({node, children, ...props}: any) => (
                    <div className="w-full min-w-0 max-w-full overflow-x-auto">
                      <div className="w-full min-w-0 max-w-full" {...props}>{children}</div>
                    </div>
                  ),
                }}
              >
                {task.data.output}
              </ReactMarkdown>
            </div>
          )}
          {variant === 'detail' && !task.data?.output && (
            <div className="text-muted-foreground">
              No report content available.
            </div>
          )}
        </TaskContent>
      )}
    />
  )
}

export default ReportTask
