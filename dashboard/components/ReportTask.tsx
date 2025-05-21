import React, { useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FileBarChart, Clock } from 'lucide-react'
import { format, formatDistanceToNow } from 'date-fns'
import { Timestamp } from '@/components/ui/timestamp'
import ReactMarkdown from 'react-markdown'
import { BlockRenderer } from './blocks/BlockRegistry'
import { getClient } from '@/utils/amplify-client'
import BlockDetails from './reports/BlockDetails'

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
    detailsFiles?: string | null;
  }>;
}

// Props for the ReportTask component
export interface ReportTaskProps extends BaseTaskProps<ReportTaskData> {
  isSelected?: boolean;
}

// Add interface for report blocks
interface ReportBlock {
  id: string
  name?: string | null
  position: number
  type: string
  output: Record<string, any>
  log?: string | null
  config?: Record<string, any>  // Add config field
  detailsFiles?: string | null  // Add detailsFiles field
}

const ReportTask: React.FC<ReportTaskProps> = ({ 
  variant, 
  task, 
  onClick, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  isSelected
}) => {
  // Add state for report blocks
  const [reportBlocks, setReportBlocks] = useState<ReportBlock[]>([])
  const [isLoadingBlocks, setIsLoadingBlocks] = useState(false)
  const [blockError, setBlockError] = useState<string | null>(null)

  // Add a function to parse output if it's a string
  const parseOutput = (output: any): Record<string, any> => {
    if (typeof output === 'string') {
      try {
        return JSON.parse(output);
      } catch (err) {
        console.error('Failed to parse output string:', err);
        return { error: 'Failed to parse output', raw: output };
      }
    }
    
    if (output && typeof output === 'object') {
      return output;
    }
    
    return {};
  };

  // Function to fetch report blocks
  const fetchReportBlocks = async (reportId: string) => {
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
                  detailsFiles
                }
              }
            }
          }
        `,
        variables: { reportId }
      })

      if ('data' in response && response.data?.getReport?.reportBlocks?.items) {
        const blocks = response.data.getReport.reportBlocks.items.map((block: any) => ({
          ...block,
          output: JSON.parse(block.output),
          config: {}  // Add empty config object by default
        }))
        console.log(`Fetched ${blocks.length} blocks directly from API`);
        setReportBlocks(blocks)
      } else {
        console.log('No blocks found in API response')
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
      console.log('Fetching blocks for report:', task.data.id);
      fetchReportBlocks(task.data.id);
    }
  }, [variant, task.data?.id]);

  // Add a new effect to monitor task.data.reportBlocks and update reportBlocks state when it changes
  useEffect(() => {
    if ((variant === 'detail' || variant === 'bare') && task.data?.reportBlocks && task.data.reportBlocks.length > 0) {
      
      const transformedBlocks = task.data.reportBlocks.map(blockProp => {
        const parsedOutput = parseOutput(blockProp.output);
        
        const blockTypeToUse = blockProp.type || parsedOutput.class || 'unknown';

        return {
          id: blockProp.name || `block-${blockProp.position}`,
          name: blockProp.name,
          position: blockProp.position,
          type: blockTypeToUse, 
          output: parsedOutput,
          log: blockProp.log || null,
          config: blockProp.config || parsedOutput,
          detailsFiles: blockProp.detailsFiles || null
        };
      });
      setReportBlocks(transformedBlocks);
    }
  }, [variant, task.data?.reportBlocks]);

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
  const reportName = task.data?.configName || task.data?.name || 'Report';
  const reportDescription = getValueOrEmpty(task.data?.configDescription);

  // Add render count for debugging
  const renderCount = React.useRef(0);
  renderCount.current++;

  // Log only essential info for real-time tracking
  console.log(`ReportTask render #${renderCount.current} - Blocks: ${reportBlocks.length}`);

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

  // Add a function to determine if the report is complete
  const isReportComplete = (taskStatus?: string, blocks: ReportBlock[] = []): boolean => {
    // Check if the task itself is complete
    if (taskStatus === 'COMPLETED') {
      return true;
    }
    
    // If the task status is explicitly FAILED, it's done but not successful
    if (taskStatus === 'FAILED') {
      return true;
    }
    
    // Check if any blocks are still in a pending state
    const hasPendingBlocks = blocks.some(block => {
      // Check for pending_execution status in the output
      if (block.output && typeof block.output === 'object') {
        if (block.output.status === 'pending_execution') {
          return true;
        }
      }
      
      // Check log messages for processing indicators
      if (block.log && typeof block.log === 'string') {
        if (block.log.includes('Processing...') || block.log.includes('Waiting') || block.log.includes('pending')) {
          return true;
        }
      }
      
      return false;
    });

    // If we have blocks but none are pending, consider it complete
    if (blocks.length > 0 && !hasPendingBlocks) {
      return true;
    }
    
    // If task is explicitly RUNNING or PENDING, it's not complete
    if (taskStatus === 'RUNNING' || taskStatus === 'PENDING') {
      return false;
    }

    // Default to false (not complete) if we can't determine clearly
    return false;
  };

  // Update the customCodeBlockRenderer function to handle incomplete reports better
  const customCodeBlockRenderer = ({ node, inline, className, children, ...props }: any) => {
    // If it's an inline code block, render normally
    if (inline) {
      return <code className={className} {...props}>{children}</code>;
    }
    
    // For block code, find the corresponding block and use its output
    const match = /language-(\w+)/.exec(className || '');
    const language = match ? match[1] : '';
    
    const childrenText = String(children).trim();
    
    // Check if this is a report block by looking for the language-block class
    if (language === 'block') {
      const content = childrenText;
      
      // Parse the YAML-like content
      const lines = content.split('\n');
      const blockConfig: Record<string, any> = {};
      
      lines.forEach(line => {
        const parts = line.split(':');
        if (parts.length >= 2) {
          const key = parts[0].trim();
          const value = parts.slice(1).join(':').trim();
          if (key) {
            blockConfig[key] = value;
          }
        }
      });
      
      // Try to match blocks by class/type and then by position if available
      const blockData = reportBlocks.find(block => {
        // Primary match: if markdown has a name, it must match block.name
        if (blockConfig.name && block.name === blockConfig.name) {
          return true;
        }
        // Secondary match: if markdown does not have a name, match by class/type AND (position if available in markdown OR it's the only one of its type)
        if (!blockConfig.name && block.type === blockConfig.class) {
          if (blockConfig.position) {
            return block.position.toString() === blockConfig.position;
          }
          // If no position in markdown, and no name, it implies we might be looking for *any* block of this type.
          // This could be ambiguous if there are multiple. For now, let's assume if no name/position, it's the first one.
          // A more robust solution might involve ensuring markdown provides enough info or a different matching strategy.
          return true; // Matches the first block of this type if no name/position specified in markdown
        }
        
        // Fallback: if markdown only has class, and no name, and block.type matches.
        // This is similar to the above but explicit.
        if (!blockConfig.name && !blockConfig.position && block.type === blockConfig.class) {
            return true;
        }

        return false;
      });
      
      if (blockData) {
        // Log when we successfully find a block to render
        
        // Check if the report is complete
        const complete = isReportComplete(task.status, reportBlocks);
        
        // Add a unique key that includes task.id to force re-render when report data changes
        const blockKey = `${task.id}-block-${blockData.id}-${blockData.position}-${Date.now()}`;
        
        // Set up enhanced props for the block when the report is not complete
        const blockProps = {
          id: blockData.id,
          config: {
            ...blockData.config,
            // Force the log UI to be shown during generation
            showLog: !complete && !!blockData.log
          },
          output: blockData.output,
          log: blockData.log || undefined,
          name: blockData.name || blockConfig.name || undefined,
          position: blockData.position,
          type: blockData.type,
          detailsFiles: blockData.detailsFiles,
          // Add a note when the block is generating
          subtitle: !complete ? "Generating..." : undefined,
          // Add any error or warning from the block output if available
          error: blockData.output?.error,
          warning: blockData.output?.warning
        };
        
        return (
          <div key={blockKey} className="my-4">
            <BlockRenderer {...blockProps} />
            
            {/* If not using a Block component that handles logs/files, show them directly */}
            {!complete && !blockData.detailsFiles && blockData.log && (
              <div className="mt-2 p-2 bg-muted/20 rounded text-xs text-muted-foreground">
                <details open>
                  <summary className="cursor-pointer font-medium">Processing Log</summary>
                  <pre className="whitespace-pre-wrap mt-2">{blockData.log}</pre>
                </details>
              </div>
            )}
          </div>
        );
      } else {
        // Log when we can't find the requested block
        
        // Instead of showing a loading placeholder, return an empty div
        // This prevents flickering while still reserving space for the block
        return <div className="my-2"></div>;
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

  // Content for bare variant
  const bareContent = (
    <div className="prose dark:prose-invert max-w-none">
      <ReactMarkdown
        components={{
          p: ({node, ...props}) => <p className="mb-2" {...props} />,
          strong: ({node, ...props}) => <strong className="font-semibold" {...props} />,
          ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-2" {...props} />,
          li: ({node, ...props}) => <li className="mb-1" {...props} />,
          h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-2 mb-2" {...props} />,
          h2: ({node, ...props}) => <h2 className="text-xl font-bold mt-2 mb-2" {...props} />,
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
        {task.data?.output || ''}
      </ReactMarkdown>
    </div>
  );

  if (variant === 'bare') {
    if (!task.data?.output && (!task.data?.reportBlocks || task.data.reportBlocks.length === 0)) {
      return <div className="text-muted-foreground">No report content available.</div>;
    }
    return bareContent;
  }

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
      isSelected={isSelected}
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
            <div className="bg-background rounded-lg p-3 mx-3 mb-3 overflow-y-auto flex-1 min-h-0">
              <div className="prose dark:prose-invert max-w-none">
                <ReactMarkdown
                  components={{
                    p: ({node, ...props}) => <p className="mb-2" {...props} />,
                    strong: ({node, ...props}) => <strong className="font-semibold" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-2" {...props} />,
                    li: ({node, ...props}) => <li className="mb-1" {...props} />,
                    h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-2 mb-2" {...props} />,
                    h2: ({node, ...props}) => <h2 className="text-xl font-bold mt-2 mb-2" {...props} />,
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
