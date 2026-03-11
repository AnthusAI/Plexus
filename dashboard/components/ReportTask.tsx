import React, { useState, useEffect, useCallback } from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FileBarChart, Clock, Square, Columns2, X } from 'lucide-react'
import { format, formatDistanceToNow } from 'date-fns'
import { Timestamp } from '@/components/ui/timestamp'
import ReactMarkdown from 'react-markdown'
import { BlockRenderer } from './blocks/BlockRegistry'
import { getClient } from '@/utils/amplify-client'
import BlockDetails from './reports/BlockDetails'
import { parseOutputString } from '@/lib/utils'

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
    attachedFiles?: string[];
    dataSet?: {
      id: string;
      name?: string;
      description?: string;
      dataSourceVersion?: {
        id: string;
        dataSource?: {
          id: string;
          name: string;
          key?: string;
        };
      };
    } | null;
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
  attachedFiles?: string[]  // Updated to string array
  dataSet?: {
    id: string;
    name?: string;
    description?: string;
    dataSourceVersion?: {
      id: string;
      dataSource?: {
        id: string;
        name: string;
        key?: string;
      };
    };
  } | null;
}

interface ReportBlockDisplayProps {
  block: any;
  attachedFiles?: string[]; // Updated to string array
  onContentChange: (content: string) => void;
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
  // Helper to transform raw blocks into ReportBlock format
  const transformBlocks = useCallback((rawBlocks: Array<{ type?: string; name?: string; position: number; output?: any; log?: string; config?: any; attachedFiles?: any[]; dataSet?: any }>): ReportBlock[] => {
    return rawBlocks.map(blockProp => {
      const parsedOutput = parseOutputString(blockProp.output);
      const blockTypeToUse = blockProp.type || (typeof parsedOutput === 'object' && parsedOutput?.class) || 'unknown';
      return {
        id: blockProp.name || `block-${blockProp.position}`,
        name: blockProp.name,
        position: blockProp.position,
        type: blockTypeToUse,
        output: typeof parsedOutput === 'object' ? parsedOutput : blockProp.output,
        log: blockProp.log || null,
        config: blockProp.config || (typeof parsedOutput === 'object' ? parsedOutput : {}),
        attachedFiles: Array.isArray(blockProp.attachedFiles) ? blockProp.attachedFiles : [],
        dataSet: blockProp.dataSet || null
      };
    });
  }, []);

  // Initialize from task.data.reportBlocks when available (avoids empty flash for detail view)
  const initialBlocks = task.data?.reportBlocks && task.data.reportBlocks.length > 0
    ? transformBlocks(task.data.reportBlocks)
    : [];

  // Add state for report blocks
  const [reportBlocks, setReportBlocks] = useState<ReportBlock[]>(initialBlocks)
  const [isLoadingBlocks, setIsLoadingBlocks] = useState(false)
  const [blockError, setBlockError] = useState<string | null>(null)

  // Use the shared parsing utility function
  const parseOutput = parseOutputString;

  // Function to fetch report blocks - needed for detail view in dashboard
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
                  attachedFiles
                }
              }
            }
          }
        `,
        variables: { reportId }
      })

      if ('data' in response && response.data?.getReport?.reportBlocks?.items) {
        const blocks = response.data.getReport.reportBlocks.items.map((block: any) => {
          const parsedOutput = parseOutput(block.output);
          return {
            ...block,
            output: parsedOutput,
            config: block.config || (typeof parsedOutput === 'object' ? parsedOutput : {}),
            attachedFiles: Array.isArray(block.attachedFiles) ? block.attachedFiles : []
          };
        })
        setReportBlocks(blocks)
      } else {
        console.warn('No blocks found in API response for report', reportId)
        setReportBlocks([])
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
      fetchReportBlocks(task.data.id);
    }
  }, [variant, task.data?.id]);

  // Sync reportBlocks from task.data when parent passes them (detail view: avoids empty flash before fetch; bare: primary source)
  useEffect(() => {
    if (task.data?.reportBlocks && task.data.reportBlocks.length > 0) {
      setReportBlocks(transformBlocks(task.data.reportBlocks));
    }
  }, [task.data?.id, task.data?.reportBlocks?.length, transformBlocks]);

  // (Bare mode uses the same sync effect above - task.data.reportBlocks is the primary source)


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
  const reportName = task.data?.configName || task.data?.name || '';
  const reportDescription = getValueOrEmpty(task.data?.configDescription);

  // Calculate processing duration if we have both timestamps
  const processingDuration = (() => {
    if (task.data?.createdAt && task.data?.updatedAt) {
      try {
        const createdTime = new Date(task.data.createdAt).getTime();
        const updatedTime = new Date(task.data.updatedAt).getTime();
        const durationMs = updatedTime - createdTime;
        
        if (durationMs > 0) {
          // Convert to human readable format
          const minutes = Math.floor(durationMs / 60000);
          const seconds = Math.floor((durationMs % 60000) / 1000);
          
          if (minutes > 0) {
            return `${minutes}m ${seconds}s`;
          } else {
            return `${seconds}s`;
          }
        }
      } catch (err) {
        console.error('Error calculating processing duration:', err);
      }
    }
    return null;
  })();

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
      
      // Parse the YAML-like content to get block class (first line: "class: X")
      const firstLine = content.split('\n')[0] || '';
      const classMatch = firstLine.match(/class:\s*(\S+)/);
      const blockClass = classMatch ? classMatch[1].trim() : '';

      // Extract name from code fence meta string (e.g. ```block name="Feedback Analysis")
      const meta: string = node?.data?.meta || '';
      const nameFromMeta = meta.match(/name=["']([^"']+)["']/)?.[1] ?? '';

      // Match by type + name when name is present (handles multiple blocks of same type)
      const blockData = (
        nameFromMeta
          ? reportBlocks.find(b => b.type === blockClass && b.name === nameFromMeta)
            ?? reportBlocks.find(b => b.type === blockClass)
          : reportBlocks.find(b => b.type === blockClass)
      ) ?? null;

      if (blockData) {
        // Check if the report is complete
        const complete = isReportComplete(task.status, reportBlocks);
        
        // Add a unique key that includes task.id to force re-render when report data changes
        const blockKey = `${task.id}-block-${blockData.id}-${blockData.position}-${Date.now()}`;
        
        // Make sure attachedFiles is always an array
        const attachedFiles = Array.isArray(blockData.attachedFiles) ? blockData.attachedFiles : [];
        
        // Set up enhanced props for the block when the report is not complete
        const displayName = blockData.name && !blockData.name.startsWith('block_')
          ? blockData.name
          : blockData.type === 'FeedbackAnalysis'
            ? 'Feedback Analysis'
            : blockData.type === 'VectorTopicMemory'
              ? 'Vector Topic Memory'
              : blockData.name ?? undefined;
        const blockProps = {
          id: blockData.id,
          config: {
            ...blockData.config,
            // Force the log UI to be shown during generation
            showLog: !complete && !!blockData.log
          },
          output: blockData.output,
          log: blockData.log || undefined,
          name: displayName,
          position: blockData.position,
          type: blockData.type,
          attachedFiles: attachedFiles,
          // Add a note when the block is generating
          subtitle: !complete ? "Generating..." : undefined,
          // Add any error or warning from the block output if available
          error: blockData.output?.error,
          warning: blockData.output?.warning
        };
        
        return (
          <div
            key={blockKey}
            className="my-4"
            id={blockData.type === 'VectorTopicMemory' ? 'vector-topic-memory' : undefined}
          >
            <BlockRenderer {...blockProps} />
            
            {/* If not using a Block component that handles logs/files, show them directly */}
            {!complete && !attachedFiles.length && blockData.log && (
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
        // No matching block - show placeholder
        const blockLabel = blockClass === 'VectorTopicMemory' ? 'Vector Topic Memory' : blockClass === 'FeedbackAnalysis' ? 'Feedback Analysis' : blockClass || 'Report block';
        return (
          <div className="my-4 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/10 p-4">
            <p className="text-sm text-muted-foreground">
              <strong>{blockLabel}</strong> — Block data not available. Report has {reportBlocks.length} block(s).
            </p>
          </div>
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
        <div className={`space-y-1.5 p-0 flex flex-col items-start w-full max-w-full ${variant === 'detail' ? 'px-1' : ''}`}>
          <div className="flex justify-between items-start w-full max-w-full gap-3 overflow-hidden">
            <div className="flex flex-col pb-1 leading-none min-w-0 flex-1 overflow-hidden">
              {variant === 'detail' && (
                <div className="flex items-center gap-2 mb-2">
                  <FileBarChart className="h-5 w-5 text-muted-foreground" />
                  <span className="text-lg font-semibold text-muted-foreground">Report</span>
                </div>
              )}
              {props.task.name && (
                <div className="font-semibold text-sm truncate">{props.task.name}</div>
              )}
              {props.task.description && (
                <div className={`text-sm text-muted-foreground ${variant === 'detail' ? '' : 'truncate'}`}>
                  {props.task.description}
                </div>
              )}
              {props.task.scorecard && props.task.scorecard.trim() !== '' && (
                <div className="font-semibold text-sm truncate">{props.task.scorecard}</div>
              )}
              {props.task.score && props.task.score.trim() !== '' && (
                <div className="font-semibold text-sm truncate">{props.task.score}</div>
              )}
              {variant !== 'grid' && (
                <div className="text-sm text-muted-foreground">{props.task.type}</div>
              )}
              <Timestamp time={props.task.time} variant="relative" />
              {processingDuration && variant === 'detail' && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  <span>Processing time: {processingDuration}</span>
                </div>
              )}
            </div>
            <div className="flex flex-col items-end flex-shrink-0">
              {variant === 'grid' ? (
                <div className="flex flex-col items-center gap-1">
                  <div className="text-muted-foreground">
                    <FileBarChart className="h-[2.25rem] w-[2.25rem]" strokeWidth={1.25} />
                  </div>
                  <div className="text-xs text-muted-foreground text-center">Report</div>
                </div>
              ) : (
                <>
                  <div className="flex gap-2">
                    {props.controlButtons}
                    {props.onToggleFullWidth && (
                      <button
                        className="h-8 w-8 rounded-md bg-border hover:bg-accent flex items-center justify-center"
                        onClick={props.onToggleFullWidth}
                        disabled={props.isLoading}
                        aria-label={props.isFullWidth ? 'Exit full width' : 'Full width'}
                      >
                        {props.isFullWidth ? 
                          <Columns2 className="h-4 w-4" /> : 
                          <Square className="h-4 w-4" />
                        }
                      </button>
                    )}
                    {props.onClose && (
                      <button
                        className="h-8 w-8 rounded-md bg-border hover:bg-accent flex items-center justify-center"
                        onClick={props.onClose}
                        disabled={props.isLoading}
                        aria-label="Close"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
      renderContent={(props) => (
        <TaskContent {...props} hideTaskStatus={true}>
          <div className={variant === 'detail' ? 'px-3 pb-3 flex flex-col h-full' : ''}>
            {variant === 'detail' && task.data?.output && (
            <div className="bg-background rounded-lg p-3 overflow-y-auto flex-1 min-h-0">
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
          </div>
        </TaskContent>
      )}
    />
  )
}

export default ReportTask
