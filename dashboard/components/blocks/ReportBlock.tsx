"use client"

import React, { useState } from 'react'
import { ScrollText, Download, Paperclip, AlertTriangle, AlertCircle, Code, Eye, MessageSquareCode, Copy, Database, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { downloadData, getUrl } from 'aws-amplify/storage';
import { CardButton } from '@/components/CardButton';
import { toast } from 'sonner';
import { DropdownMenuItem, DropdownMenu, DropdownMenuContent } from '@/components/ui/dropdown-menu';

// Define DetailFile locally, ensure it includes 'path'
// Export DetailFile to be used in other components
export interface DetailFile {
  name: string;
  path: string; // S3 key for the file
  description?: string;
  size?: number;
  type?: string;
  [key: string]: any; 
}

/**
 * Props for all report block components
 */
export interface ReportBlockProps {
  /** The block's configuration from the markdown */
  config: Record<string, any>
  /** The block's output data from the backend */
  output: string | Record<string, any>
  /** Optional log messages from the block's execution */
  log?: string
  /** The block's name if specified */
  name?: string
  /** The block's position in the report */
  position: number
  /** The block's type */
  type: string
  /** Child components */
  children?: React.ReactNode
  /** Optional className for styling */
  className?: string
  /** The block's unique identifier */
  id: string
  /** Array of file paths for attached files */
  attachedFiles?: string[] | null
  /** Optional title to override the name */
  title?: string
  /** Optional subtitle for additional context */
  subtitle?: string
  /** Whether to show the title header section */
  showTitle?: boolean
  /** Optional notes for the report block */
  notes?: string
  /** Optional error message to display */
  error?: string  
  /** Optional warning message to display */
  warning?: string
  /** Optional date range for the report block */
  dateRange?: {
    start: string;
    end: string;
  }
  /** Associated dataset information */
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

/**
 * Interface for block component classes
 * Each specialized block type should implement this interface
 */
export interface BlockComponent extends React.FC<ReportBlockProps> {
  /** The block class name this component handles */
  blockClass: string
}

/**
 * ReportBlock component serves as the base renderer for all block types.
 * Provides common functionality for title, logs, file attachments, and error/warning messages.
 * Specialized block types should extend this component.
 */
const ReportBlock: BlockComponent = ({ 
  children, 
  className = '',
  output,
  name,
  log,
  config,
  position,
  id,
  attachedFiles,
  title,
  subtitle,
  showTitle = true,
  notes,
  error,
  warning,
  dateRange,
  dataSet
}) => {
  // State for inline log display
  const [showLog, setShowLog] = useState(false);
  const [logText, setLogText] = useState<string | null>(null);
  const [isLoadingLog, setIsLoadingLog] = useState(false);

  // State for attached files display
  const [showAttachedFiles, setShowAttachedFiles] = useState(false);
  const [selectedFileContent, setSelectedFileContent] = useState<string | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  
  // State for raw output display
  const [showRawOutput, setShowRawOutput] = useState(false);
  const [selectedFileUrl, setSelectedFileUrl] = useState<string | null>(null);
  const [selectedFileIsImage, setSelectedFileIsImage] = useState<boolean | null>(null);
  const [selectedFileIsHtml, setSelectedFileIsHtml] = useState<boolean | null>(null);
  
  // State to track if we should use the wide layout
  const [isWideLayout, setIsWideLayout] = useState(false);
  
  // Effect to update layout on mount and window resize
  React.useEffect(() => {
    const updateLayoutMode = () => {
      setIsWideLayout(window.innerWidth >= 768); // 768px is typical md breakpoint
    };
    
    // Initial check
    updateLayoutMode();
    
    // Add resize listener
    window.addEventListener('resize', updateLayoutMode);
    
    // Cleanup
    return () => window.removeEventListener('resize', updateLayoutMode);
  }, []);

  // Convert string array of file paths to DetailFile objects
  const parsedAttachedFiles = React.useMemo(() => {
    if (Array.isArray(attachedFiles) && attachedFiles.length > 0) {
      return attachedFiles.map(filePath => {
        const fileName = filePath.split('/').pop() || 'file';
        return {
          name: fileName,
          path: filePath
        };
      });
    }
    return [];
  }, [attachedFiles]);

  const logFile = React.useMemo(() => {
    return parsedAttachedFiles.find(f => f.name === 'log.txt');
  }, [parsedAttachedFiles]);

  const hasAttachedFiles = parsedAttachedFiles.length > 0;
  const hasLog = !!log || !!logFile;

  const imageExtensions = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'webp'];
  const isImageFile = (fileName: string): boolean => {
    if (!fileName) return false;
    const extension = fileName.split('.').pop()?.toLowerCase();
    return !!extension && imageExtensions.includes(extension);
  };

  const isHtmlFile = (fileName: string): boolean => {
    if (!fileName) return false;
    const extension = fileName.split('.').pop()?.toLowerCase();
    return !!extension && ['html', 'htm'].includes(extension);
  };

  const fetchLogFileContent = React.useCallback(async () => {
    if (!logFile || !logFile.path) return;
    setIsLoadingLog(true);
    try {
      // Determine which storage bucket to use based on file path
      let storageOptions: { path: string; options?: { bucket?: string } } = { path: logFile.path };
      
      if (logFile.path.startsWith('reportblocks/')) {
        // Report block files are stored in the reportBlockDetails bucket
        storageOptions = {
          path: logFile.path,
          options: { bucket: 'reportBlockDetails' }
        };
      } else if (logFile.path.startsWith('scoreresults/')) {
        // Score result files are stored in the scoreResultAttachments bucket
        storageOptions = {
          path: logFile.path,
          options: { bucket: 'scoreResultAttachments' }
        };
      }
      
      const downloadResult = await downloadData(storageOptions).result;
      const text = await downloadResult.body.text();
      setLogText(text);
    } catch (error) {
      console.error('Error fetching log content from S3:', error);
      setLogText('Failed to load log content.');
    } finally {
      setIsLoadingLog(false);
    }
  }, [logFile]);

  const fetchFileContent = React.useCallback(async (file: DetailFile) => {
    // If this file is already selected, toggle it off
    if (selectedFileName === file.name) {
      setSelectedFileContent(null);
      setSelectedFileName(null);
      setSelectedFileUrl(null);
      setSelectedFileIsImage(null);
      setSelectedFileIsHtml(null);
      return;
    }
    
    setIsLoadingFile(true);
    setSelectedFileName(file.name);
    setSelectedFileContent(null); // Reset previous content
    setSelectedFileUrl(null);     // Reset previous URL
    setSelectedFileIsImage(null); // Reset previous type
    setSelectedFileIsHtml(null);  // Reset previous HTML type

    try {
      // Determine which storage bucket to use based on file path
      let storageOptions: { path: string; options?: { bucket?: string } } = { path: file.path };
      
      if (file.path.startsWith('reportblocks/')) {
        // Report block files are stored in the reportBlockDetails bucket
        storageOptions = {
          path: file.path,
          options: { bucket: 'reportBlockDetails' }
        };
      } else if (file.path.startsWith('scoreresults/')) {
        // Score result files are stored in the scoreResultAttachments bucket
        storageOptions = {
          path: file.path,
          options: { bucket: 'scoreResultAttachments' }
        };
      }
      
      if (isImageFile(file.name)) {
        const urlResult = await getUrl(storageOptions);
        if (urlResult.url) {
          setSelectedFileUrl(urlResult.url.toString());
          setSelectedFileIsImage(true);
          setSelectedFileIsHtml(false);
        } else {
          throw new Error('Failed to get image URL.');
        }
      } else if (isHtmlFile(file.name)) {
        const downloadResult = await downloadData(storageOptions).result;
        const text = await downloadResult.body.text();
        setSelectedFileContent(text);
        setSelectedFileIsHtml(true);
        setSelectedFileIsImage(false);
      } else {
        const downloadResult = await downloadData(storageOptions).result;
        const text = await downloadResult.body.text();
        setSelectedFileContent(text);
        setSelectedFileIsImage(false);
        setSelectedFileIsHtml(false);
      }
    } catch (error) {
      console.error('Error processing file from S3:', error);
      setSelectedFileContent( error instanceof Error ? `Failed to load file: ${error.message}` : 'Failed to load file content.');
      setSelectedFileIsImage(null); // Indicates an error or unknown type
      setSelectedFileIsHtml(null);  // Indicates an error or unknown type
    } finally {
      setIsLoadingFile(false);
    }
  }, [selectedFileName]);

  const toggleShowLog = () => {
    const newShowLogState = !showLog;
    setShowLog(newShowLogState);
    if (newShowLogState && !logText && logFile && !isLoadingLog) {
      fetchLogFileContent();
    }
  };

  const toggleShowRawOutput = () => {
    setShowRawOutput(!showRawOutput);
  };

  const toggleShowAttachedFiles = () => {
    const newShowAttachedFilesState = !showAttachedFiles;
    setShowAttachedFiles(newShowAttachedFilesState);
    // Reset selected file when hiding
    if (!newShowAttachedFilesState) {
      setSelectedFileContent(null);
      setSelectedFileName(null);
      setSelectedFileUrl(null);
      setSelectedFileIsImage(null);
      setSelectedFileIsHtml(null);
    }
  };

  const handleDownloadFile = async (file: DetailFile) => {
    if (!file || !file.path) return;
    try {
      // Determine which storage bucket to use based on file path
      let storageOptions: { path: string; options?: { bucket?: string } } = { path: file.path };
      
      if (file.path.startsWith('reportblocks/')) {
        // Report block files are stored in the reportBlockDetails bucket
        storageOptions = {
          path: file.path,
          options: { bucket: 'reportBlockDetails' }
        };
      } else if (file.path.startsWith('scoreresults/')) {
        // Score result files are stored in the scoreResultAttachments bucket
        storageOptions = {
          path: file.path,
          options: { bucket: 'scoreResultAttachments' }
        };
      }
      
      const urlResult = await getUrl(storageOptions);
      if (urlResult.url) {
        window.open(urlResult.url.toString(), '_blank');
      } else {
        console.error('Failed to get download URL for file.');
      }
    } catch (error) {
      console.error('Error getting download URL for file from S3:', error);
    }
  };

  const handleDownloadLog = async () => {
    if (!logFile || !logFile.path) return;
    try {
      // Determine which storage bucket to use based on file path
      let storageOptions: { path: string; options?: { bucket?: string } } = { path: logFile.path };
      
      if (logFile.path.startsWith('reportblocks/')) {
        // Report block files are stored in the reportBlockDetails bucket
        storageOptions = {
          path: logFile.path,
          options: { bucket: 'reportBlockDetails' }
        };
      } else if (logFile.path.startsWith('scoreresults/')) {
        // Score result files are stored in the scoreResultAttachments bucket
        storageOptions = {
          path: logFile.path,
          options: { bucket: 'scoreResultAttachments' }
        };
      }
      
      const urlResult = await getUrl(storageOptions);
      if (urlResult.url) {
        window.open(urlResult.url.toString(), '_blank');
      } else {
        console.error('Failed to get download URL for log.');
      }
    } catch (error) {
      console.error('Error getting download URL for log from S3:', error);
    }
  };

  const formattedDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch (e) {
      return dateStr;
    }
  };

  // Extract error and warning from output if not provided directly
  const outputObject = (output && typeof output === 'object') ? output as Record<string, any> : {};
  const outputError = outputObject.error || (Array.isArray(outputObject.errors) && outputObject.errors.length > 0 ? outputObject.errors[0] : undefined);
  const displayError = error || outputError;
  const displayWarning = warning || outputObject.warning;
  
  // Extract date range from output if not provided directly
  const displayDateRange = dateRange || outputObject.date_range;

  // Render the log details
  const renderLogDetails = () => {
    if (!showLog) return null;
    
    return (
      <div className={`my-3 bg-card p-3 overflow-hidden rounded-lg ${isWideLayout ? "w-full" : "@[30rem]:w-[350px]"}`}>
        <div className="flex flex-row justify-between items-center mb-3">
          <h4 className="text-base font-medium">Log</h4>
          {logFile && (
            <CardButton 
              icon={Download} 
              onClick={handleDownloadLog}
              label="Download"
              aria-label="Download log file"
            />
          )}
        </div>
        <div className="w-full overflow-hidden">
          {isLoadingLog && <p className="text-sm text-muted-foreground">Loading log content...</p>}
          {!isLoadingLog && logText && (
            <pre className="whitespace-pre-wrap text-xs bg-card text-foreground overflow-y-auto overflow-x-auto font-mono max-h-[300px] px-2 py-2 max-w-full">
              {logText}
            </pre>
          )}
          {!isLoadingLog && !logText && log && (
            <pre className="whitespace-pre-wrap text-xs bg-card text-foreground overflow-y-auto overflow-x-auto font-mono max-h-[300px] px-2 py-2 max-w-full">
              {log}
            </pre>
          )}
          {!isLoadingLog && !logText && !log && (
            <p className="text-sm text-muted-foreground">Log content is empty or could not be loaded.</p>
          )}
        </div>
      </div>
    );
  };
  
  // Render the file attachment details
  const renderFileDetails = () => {
    if (!showAttachedFiles) return null;
    
    return (
      <div className={`my-3 bg-card p-3 overflow-visible rounded-lg ${isWideLayout ? "w-full" : "@[30rem]:w-[350px]"}`}>
        <div className="flex flex-row justify-between items-center mb-3">
          <h4 className="text-base font-medium">Attached Files</h4>
        </div>
        
        <div className="flex flex-col space-y-4 w-full overflow-visible">
          {/* File list */}
          <div className="bg-muted/50 py-2 px-0 rounded-sm">
            <div className="space-y-1">
              {parsedAttachedFiles.map((file, index) => (
                <div key={index} className="flex flex-col -mx-1">
                  <div className={`flex justify-between items-center ${index % 2 === 0 ? 'bg-card-selected' : 'bg-card'} rounded-sm p-1 w-full`}>
                    <span className="text-sm truncate flex-1">{file.name}</span>
                    <div className="flex space-x-2">
                      <CardButton 
                        icon={Eye} 
                        onClick={() => fetchFileContent(file)}
                        label={selectedFileName === file.name ? "Hide" : "View"}
                        aria-label={selectedFileName === file.name ? `Hide ${file.name}` : `View ${file.name}`}
                      />
                      <CardButton 
                        icon={Download} 
                        onClick={() => handleDownloadFile(file)}
                        label="Download"
                        aria-label={`Download ${file.name}`}
                      />
                    </div>
                  </div>
                  
                  {/* Show file content directly under this item */}
                  {selectedFileName === file.name && (
                    <div className="w-full overflow-hidden mt-2 bg-card rounded">
                      {isLoadingFile && <p className="text-sm text-muted-foreground px-2 py-2">Loading...</p>}
                      {!isLoadingFile && (
                        <>
                          {selectedFileIsImage === true && selectedFileUrl && (
                            <div className="p-2 flex justify-center items-center bg-card rounded">
                              <img 
                                src={selectedFileUrl} 
                                alt={selectedFileName || 'Attached image'} 
                                className="w-full h-auto object-contain"
                              />
                            </div>
                          )}
                          {selectedFileIsHtml === true && selectedFileContent && (
                            <div className="p-2 bg-card rounded">
                              <iframe 
                                srcDoc={selectedFileContent}
                                title={selectedFileName || 'HTML content'}
                                className="w-full h-[300px] border-0"
                                sandbox="allow-scripts allow-same-origin" 
                              />
                            </div>
                          )}
                          {selectedFileIsImage === false && selectedFileIsHtml === false && selectedFileContent && (
                            <pre className="whitespace-pre-wrap text-xs overflow-y-auto overflow-x-auto font-mono max-h-[200px] px-2 py-2 bg-card text-foreground max-w-full rounded">
                              {selectedFileContent}
                            </pre>
                          )}
                          {/* Error display or specific messages */}
                          {selectedFileIsImage === null && selectedFileIsHtml === null && selectedFileContent && ( // Error message for either type
                            <p className="text-sm text-red-500 px-2 py-2 bg-card rounded">{selectedFileContent}</p>
                          )}
                          {/* Fallback for no content, no error message, and not explicitly an image or text, or if it's an image but URL failed silently */}
                          {selectedFileIsImage === null && selectedFileIsHtml === null && !selectedFileContent && (
                            <p className="text-sm text-muted-foreground px-2 py-2 bg-card rounded">Preview not available or file is empty.</p>
                          )}
                          {!selectedFileContent && selectedFileIsImage === true && !selectedFileUrl && ( // Image detected, but URL fetch failed and no error message set
                            <p className="text-sm text-red-500 px-2 py-2 bg-card rounded">Could not load image preview.</p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Render the raw output details using CodeDisplay component
  const renderRawOutput = () => {
    if (!showRawOutput) return null;
    
    // Determine output format and content
    let displayOutput: string;
    let outputType: 'YAML' | 'JSON';
    let description: string;
    
    if (typeof output === 'string') {
      // New format: output is already YAML string with comments
      displayOutput = output;
      outputType = "YAML";
      description = "Structured YAML code with contextual information for humans, AI models, and other code";
    } else if (output && typeof output === 'object' && 'rawOutput' in output && typeof output.rawOutput === 'string') {
      // New format: rawOutput field contains YAML string with comments
      displayOutput = output.rawOutput;
      outputType = "YAML";
      description = "Structured YAML code with contextual information for humans, AI models, and other code";
    } else {
      // Legacy format: output is object, convert to JSON
      displayOutput = JSON.stringify(output, null, 2);
      outputType = "JSON";
      description = "Legacy JSON code output from the report block execution";
    }
    
    // Add original configuration to universal code snippet
    if (config && Object.keys(config).length > 0) {
      const formatValue = (value: any, indent: string = ''): string => {
        if (value === null || value === undefined) return 'null';
        if (typeof value === 'string') return value;
        if (typeof value === 'number' || typeof value === 'boolean') return String(value);
        if (Array.isArray(value)) {
          if (value.length === 0) return '[]';
          return '\n' + value.map(item => `${indent}  - ${formatValue(item, indent + '  ')}`).join('\n');
        }
        if (typeof value === 'object') {
          const entries = Object.entries(value);
          if (entries.length === 0) return '{}';
          return '\n' + entries.map(([k, v]) => `${indent}  ${k}: ${formatValue(v, indent + '  ')}`).join('\n');
        }
        return String(value);
      };
      
      const configYaml = `
# ====================================
# Report Block Configuration
# ====================================
# This is the original configuration that was used to generate the output above.
# It shows the exact parameters, prompts, and settings that created the results.

${Object.entries(config).map(([key, value]) => `${key}: ${formatValue(value)}`).join('\n')}`;
      
      displayOutput = displayOutput + '\n\n' + configYaml;
    }
    
    return (
      <div className={`my-3 bg-card p-3 overflow-hidden rounded-lg ${isWideLayout ? "w-full" : "@[30rem]:w-[350px]"}`}>
        <div className="flex flex-row justify-between items-center mb-3">
          <h4 className="text-base font-medium">Universal Code ({outputType})</h4>
          <CardButton 
            icon={Copy} 
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(displayOutput);
                toast.success("Universal Code copied to clipboard");
              } catch (error) {
                console.error('Failed to copy code:', error);
                toast.error("Failed to copy code to clipboard");
              }
            }}
            label="Copy"
            aria-label="Copy code to clipboard"
          />
        </div>
        <div className="w-full overflow-hidden">
          <pre className="whitespace-pre-wrap text-xs bg-card text-foreground overflow-y-auto overflow-x-auto font-mono max-h-[400px] px-2 py-2 max-w-full rounded">
            {displayOutput}
          </pre>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2">
        <div className="@container">
          <div className="flex @[30rem]:flex-row flex-col @[30rem]:justify-between @[30rem]:items-start">
            <div className="@[30rem]:max-w-[60%]">
              {showTitle && (
                <h3 className="text-xl font-semibold">
                  {title || name || 'Report'} 
                </h3>
              )}
              {subtitle && (
                <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>
              )}
              {displayDateRange && (
                <p className="text-sm text-muted-foreground mt-1">
                  {formattedDate(displayDateRange.start)} to {formattedDate(displayDateRange.end)}
                </p>
              )}
              {dataSet && (
                <div className="flex items-center gap-2 mt-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  <div className="flex items-center gap-1 text-sm">
                    <span className="text-muted-foreground">Dataset:</span>
                    <a
                      href={`/datasets/${dataSet.id}`}
                      className="text-foreground hover:text-primary hover:underline font-medium"
                      title={dataSet.description || `View dataset: ${dataSet.name || dataSet.id}`}
                    >
                      {dataSet.name || dataSet.id}
                    </a>
                    <ExternalLink className="h-3 w-3 text-muted-foreground" />
                    {dataSet.dataSourceVersion?.dataSource?.name && (
                      <>
                        <span className="text-muted-foreground mx-1">•</span>
                        <span className="text-muted-foreground">Source:</span>
                        <a
                          href={`/data-sources/${dataSet.dataSourceVersion.dataSource.id}`}
                          className="text-foreground hover:text-primary hover:underline"
                          title={`View data source: ${dataSet.dataSourceVersion.dataSource.name}`}
                        >
                          {dataSet.dataSourceVersion.dataSource.name}
                        </a>
                        <ExternalLink className="h-3 w-3 text-muted-foreground" />
                      </>
                    )}
                  </div>
                </div>
              )}
              {notes && (
                <div className="text-sm text-muted-foreground mt-2 max-w-prose">
                  {notes}
                </div>
              )}
            </div>
            <div className="w-full @[30rem]:w-auto @[30rem]:flex-shrink-0 flex @[30rem]:flex-row flex-col @[30rem]:items-start space-y-2 @[30rem]:space-y-0 @[30rem]:space-x-2 mt-2 @[30rem]:mt-0">
              {hasLog && (
                <div className="w-full @[30rem]:w-auto">
                  <Button 
                    variant="secondary"
                    size="sm"
                    onClick={toggleShowLog}
                    className="h-8 bg-card hover:bg-card/90 border-0 w-full"
                  >
                    <ScrollText className="mr-2 h-4 w-4" />
                    {showLog ? "Hide Log" : "Log"}
                  </Button>
                  
                  {/* Only render inline (below the button) in narrow layout */}
                  {showLog && !isWideLayout && renderLogDetails()}
                </div>
              )}
              
              {hasAttachedFiles && (
                <div className="w-full @[30rem]:w-auto">
                  <Button 
                    variant="secondary"
                    size="sm"
                    onClick={toggleShowAttachedFiles}
                    className="h-8 bg-card hover:bg-card/90 border-0 w-full"
                  >
                    <Paperclip className="mr-2 h-4 w-4" />
                    {showAttachedFiles ? "Hide Files" : "Files"}
                  </Button>
                  
                  {/* Only render inline (below the button) in narrow layout */}
                  {showAttachedFiles && !isWideLayout && renderFileDetails()}
                </div>
              )}
              
              {/* Raw Output Button - Always available */}
              <div className="w-full @[30rem]:w-auto">
                <Button 
                  variant="secondary"
                  size="sm"
                  onClick={toggleShowRawOutput}
                  className="h-8 bg-card hover:bg-card/90 border-0 w-full"
                >
                  <MessageSquareCode className="mr-2 h-4 w-4" />
                  {showRawOutput ? "Hide Code" : "Code"}
                </Button>
                
                {/* Only render inline (below the button) in narrow layout */}
                {showRawOutput && !isWideLayout && renderRawOutput()}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* In wider layouts, display details at the top, above the content */}
      {isWideLayout && (
        <div className="mt-2">
          {showLog && renderLogDetails()}
          {showAttachedFiles && renderFileDetails()}
          {showRawOutput && renderRawOutput()}
        </div>
      )}

      {/* Display error message if present */}
      {displayError && (
        <div className="mt-4 bg-red-600 text-white p-3 rounded-md w-full">
          <div className="flex items-start gap-2">
            <AlertCircle size={18} className="mt-0.5 flex-shrink-0" />
            <p className="text-sm font-medium">{displayError}</p>
          </div>
        </div>
      )}
      
      {/* Display warning message if present */}
      {!displayError && displayWarning && (
        <div className="mt-4 bg-false text-foreground p-3 rounded-md w-full">
          <div className="flex items-start gap-2">
            <AlertTriangle size={18} className="mt-0.5 flex-shrink-0" />
            <p className="text-sm font-medium">{displayWarning}</p>
          </div>
        </div>
      )}

      {/* Content Area */}
      {children ? (
        // Render custom content if provided
        children
      ) : (
        // Default content rendering - just show raw output in a card
        <div className={`w-full min-w-0 max-w-full ${className}`}>
          <div className="bg-card p-4 rounded-md mt-4">
            <h4 className="text-base font-medium mb-3">Configuration</h4>
            {config && (
              <div className="bg-muted/50 p-3 rounded-sm">
                <pre className="text-xs whitespace-pre-wrap overflow-x-auto font-mono">
                  {JSON.stringify(config, null, 2)}
                </pre>
              </div>
            )}
            
            {output && Object.keys(output).length > 0 && (
              <div className="mt-4">
                <h4 className="text-base font-medium mb-3">Output</h4>
                <div className="bg-muted/50 p-3 rounded-sm">
                  <pre className="text-xs whitespace-pre-wrap overflow-x-auto font-mono">
                    {JSON.stringify(output, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// Set the blockClass to indicate this is the default block handler
ReportBlock.blockClass = 'default'

export default ReportBlock 