'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Paperclip, Copy, Eye, Download } from 'lucide-react';
import { CardButton } from '@/components/CardButton';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { downloadData, getUrl } from 'aws-amplify/storage';

export interface TaskOutputDisplayProps {
  /** Universal Code YAML output */
  output?: string;
  /** Array of S3 file keys for attachments */
  attachedFiles?: string[];
  /** Task stdout output */
  stdout?: string;
  /** Task stderr output */
  stderr?: string;
  /** Task command for context */
  command?: string;
  /** Task type for context */
  taskType?: string;
  /** Task variant - controls visibility and defaults. Supports all Task component variants. */
  variant?: 'grid' | 'detail' | 'nested' | 'bare';
  /** Optional className for styling */
  className?: string;
}

interface CompactedTaskOutputEnvelope {
  status?: string;
  output_compacted?: boolean;
  preview?: unknown;
  output_attachment?: string;
  error?: string;
}

function parseCompactedTaskOutputEnvelope(output?: string): CompactedTaskOutputEnvelope | null {
  if (!output || typeof output !== 'string') {
    return null;
  }
  try {
    const parsed = JSON.parse(output) as CompactedTaskOutputEnvelope;
    if (parsed && parsed.output_compacted === true && typeof parsed.output_attachment === 'string') {
      return parsed;
    }
  } catch (_error) {
    return null;
  }
  return null;
}

function formatTaskOutputPreview(preview: unknown): string {
  if (typeof preview === 'string') {
    return preview;
  }
  if (preview && typeof preview === 'object') {
    return JSON.stringify(preview, null, 2);
  }
  return '';
}

/**
 * TaskOutputDisplay Component
 * 
 * Displays Universal Code output and file attachments for tasks.
 * Similar to the ReportBlock Universal Code display but specifically designed for Tasks.
 */
export const TaskOutputDisplay: React.FC<TaskOutputDisplayProps> = ({
  output,
  attachedFiles = [],
  stdout,
  stderr,
  command,
  taskType,
  variant = 'detail',
  className = ''
}) => {
  const compactedOutput = useMemo(() => parseCompactedTaskOutputEnvelope(output), [output]);
  
  // stderr is expanded by default if it has content, collapsed otherwise
  const [showStderr, setShowStderr] = useState(!!stderr);
  const [loadedTaskOutput, setLoadedTaskOutput] = useState<string | null>(null);
  const [taskOutputLoadError, setTaskOutputLoadError] = useState<string | null>(null);
  const [isLoadingTaskOutput, setIsLoadingTaskOutput] = useState(false);
  
  // File viewing state
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [selectedFileContent, setSelectedFileContent] = useState<string | null>(null);
  const [selectedFileUrl, setSelectedFileUrl] = useState<string | null>(null);
  const [selectedFileIsImage, setSelectedFileIsImage] = useState<boolean | null>(null);
  const [selectedFileIsHtml, setSelectedFileIsHtml] = useState<boolean | null>(null);
  const [isLoadingFile, setIsLoadingFile] = useState(false);

  useEffect(() => {
    const attachmentPath = compactedOutput?.output_attachment;
    if (!attachmentPath) {
      setLoadedTaskOutput(null);
      setTaskOutputLoadError(null);
      setIsLoadingTaskOutput(false);
      return;
    }

    let cancelled = false;

    const loadTaskOutput = async () => {
      setIsLoadingTaskOutput(true);
      setTaskOutputLoadError(null);
      try {
        const downloadResult = await downloadData({
          path: attachmentPath,
          options: { bucket: 'taskAttachments' },
        }).result;
        const text = await downloadResult.body.text();
        if (!cancelled) {
          setLoadedTaskOutput(text);
        }
      } catch (error) {
        if (!cancelled) {
          setTaskOutputLoadError(
            error instanceof Error ? error.message : 'Failed to load task output attachment.'
          );
        }
      } finally {
        if (!cancelled) {
          setIsLoadingTaskOutput(false);
        }
      }
    };

    void loadTaskOutput();
    return () => {
      cancelled = true;
    };
  }, [compactedOutput?.output_attachment]);

  // Don't render anything in grid mode
  if (variant === 'grid') {
    return null;
  }

  // Don't render if no output data
  if (!output && (!attachedFiles || attachedFiles.length === 0) && !stdout && !stderr) {
    return null;
  }

  // Utility functions for file type detection
  const isImageFile = (fileName: string): boolean => {
    const imageExtensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'];
    return imageExtensions.some(ext => fileName.toLowerCase().endsWith(ext));
  };

  const isHtmlFile = (fileName: string): boolean => {
    return fileName.toLowerCase().endsWith('.html') || fileName.toLowerCase().endsWith('.htm');
  };

  const handleCopyUniversalCode = async () => {
    const copyText = loadedTaskOutput
      ?? (compactedOutput ? formatTaskOutputPreview(compactedOutput.preview) : output)
      ?? '';
    if (!copyText) return;
    
    try {
      await navigator.clipboard.writeText(copyText);
      toast.success("Task output copied to clipboard");
    } catch (error) {
      console.error('Failed to copy task output:', error);
      toast.error("Failed to copy task output to clipboard");
    }
  };

  const handleCopyStdout = async () => {
    if (!stdout) return;
    
    try {
      await navigator.clipboard.writeText(stdout);
      toast.success("stdout copied to clipboard");
    } catch (error) {
      console.error('Failed to copy stdout:', error);
      toast.error("Failed to copy stdout to clipboard");
    }
  };

  const handleCopyStderr = async () => {
    if (!stderr) return;
    
    try {
      await navigator.clipboard.writeText(stderr);
      toast.success("stderr copied to clipboard");
    } catch (error) {
      console.error('Failed to copy stderr:', error);
      toast.error("Failed to copy stderr to clipboard");
    }
  };

  const fetchFileContent = async (filePath: string) => {
    const fileName = filePath.split('/').pop() || filePath;
    
    // If this file is already selected, toggle it off
    if (selectedFileName === fileName) {
      setSelectedFileContent(null);
      setSelectedFileName(null);
      setSelectedFileUrl(null);
      setSelectedFileIsImage(null);
      setSelectedFileIsHtml(null);
      return;
    }
    
    setIsLoadingFile(true);
    setSelectedFileName(fileName);
    setSelectedFileContent(null);
    setSelectedFileUrl(null);
    setSelectedFileIsImage(null);
    setSelectedFileIsHtml(null);

    try {
      // Determine which storage bucket to use based on file path
      let storageOptions: { path: string; options?: { bucket?: string } } = { path: filePath };
      
      if (filePath.startsWith('tasks/')) {
        // Task attachments are stored in the taskAttachments bucket
        storageOptions = {
          path: filePath,
          options: { bucket: 'taskAttachments' }
        };
      } else if (filePath.startsWith('reportblocks/')) {
        storageOptions = {
          path: filePath,
          options: { bucket: 'reportBlockDetails' }
        };
      } else if (filePath.startsWith('scoreresults/')) {
        storageOptions = {
          path: filePath,
          options: { bucket: 'scoreResultAttachments' }
        };
      }
      
      if (isImageFile(fileName)) {
        const urlResult = await getUrl(storageOptions);
        if (urlResult.url) {
          setSelectedFileUrl(urlResult.url.toString());
          setSelectedFileIsImage(true);
          setSelectedFileIsHtml(false);
        } else {
          throw new Error('Failed to get image URL.');
        }
      } else if (isHtmlFile(fileName)) {
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
      setSelectedFileContent(error instanceof Error ? `Failed to load file: ${error.message}` : 'Failed to load file content.');
      setSelectedFileIsImage(null);
      setSelectedFileIsHtml(null);
    } finally {
      setIsLoadingFile(false);
    }
  };

  const handleDownloadFile = async (filePath: string) => {
    if (!filePath) return;
    
    const fileName = filePath.split('/').pop() || 'download';
    
    try {
      // Determine which storage bucket to use based on file path
      let storageOptions: { path: string; options?: { bucket?: string } } = { path: filePath };
      
      if (filePath.startsWith('tasks/')) {
        // Task attachments are stored in the taskAttachments bucket
        storageOptions = {
          path: filePath,
          options: { bucket: 'taskAttachments' }
        };
      } else if (filePath.startsWith('reportblocks/')) {
        storageOptions = {
          path: filePath,
          options: { bucket: 'reportBlockDetails' }
        };
      } else if (filePath.startsWith('scoreresults/')) {
        storageOptions = {
          path: filePath,
          options: { bucket: 'scoreResultAttachments' }
        };
      }
      
      const urlResult = await getUrl(storageOptions);
      if (urlResult.url) {
        // Create a temporary anchor element to trigger download
        const link = document.createElement('a');
        link.href = urlResult.url.toString();
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        console.error('Failed to get download URL for file.');
        toast.error('Failed to get download URL for file.');
      }
    } catch (error) {
      console.error('Error getting download URL for file from S3:', error);
      toast.error('Error downloading file.');
    }
  };

  const renderUniversalCode = () => {
    if (!output) return null;

    let displayOutput = loadedTaskOutput
      ?? (compactedOutput ? formatTaskOutputPreview(compactedOutput.preview) : output);
    
    if (!compactedOutput && (command || taskType)) {
      const contextHeader = `# ====================================
# Task Output Context
# ====================================
# This Universal Code was generated from a task execution.
${taskType ? `# Task Type: ${taskType}` : ''}
${command ? `# Command: ${command}` : ''}
# 
# The structured output below contains the results and context from the task execution.

`;
      displayOutput = contextHeader + output;
    }

    return (
      <div className="my-3">
        <div className="flex flex-row justify-between items-center mb-3">
          <h4 className="text-base font-medium">Task Output</h4>
          <CardButton 
            icon={Copy} 
            onClick={handleCopyUniversalCode}
            label="Copy"
            aria-label="Copy task output to clipboard"
          />
        </div>
        {compactedOutput && (
          <div className="mb-2 rounded bg-muted/50 px-2 py-2 text-xs text-muted-foreground">
            <div>Attachment: {compactedOutput.output_attachment}</div>
            {compactedOutput.status && <div>Status: {compactedOutput.status}</div>}
            {compactedOutput.error && <div>Error: {compactedOutput.error}</div>}
          </div>
        )}
        <div className="w-full overflow-hidden">
          <pre className="whitespace-pre-wrap text-xs bg-card text-foreground overflow-y-auto overflow-x-auto font-mono max-h-[400px] px-2 py-2 max-w-full rounded">
            {isLoadingTaskOutput ? 'Loading task output attachment...' : displayOutput}
          </pre>
        </div>
        {taskOutputLoadError && (
          <p className="mt-2 text-xs text-red-500">
            Failed to load task output attachment: {taskOutputLoadError}
          </p>
        )}
      </div>
    );
  };

  const renderAttachments = () => {
    if (!attachedFiles || attachedFiles.length === 0) return null;

    return (
      <div className="my-3">
        <div className="flex flex-row justify-between items-center mb-3">
          <h4 className="text-base font-medium">Attached Files ({attachedFiles.length})</h4>
        </div>
        <div className="bg-muted/50 py-2 px-0 rounded-sm">
          <div className="space-y-1">
            {attachedFiles.map((filePath, index) => {
              const fileName = filePath.split('/').pop() || `file_${index}`;
              return (
                <div key={index} className="flex flex-col -mx-1">
                  <div className={`flex justify-between items-center ${index % 2 === 0 ? 'bg-card-selected' : 'bg-card'} rounded-sm p-1 w-full`}>
                    <span className="text-sm truncate flex-1">{fileName}</span>
                    <div className="flex space-x-2">
                      <CardButton 
                        icon={Eye} 
                        onClick={() => fetchFileContent(filePath)}
                        label={selectedFileName === fileName ? "Hide" : "View"}
                        aria-label={selectedFileName === fileName ? `Hide ${fileName}` : `View ${fileName}`}
                      />
                      <CardButton 
                        icon={Download} 
                        onClick={() => handleDownloadFile(filePath)}
                        label="Download"
                        aria-label={`Download ${fileName}`}
                      />
                    </div>
                  </div>
                  
                  {/* Show file content directly under this item */}
                  {selectedFileName === fileName && (
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
                          {selectedFileIsImage === null && selectedFileIsHtml === null && selectedFileContent && (
                            <p className="text-sm text-red-500 px-2 py-2 bg-card rounded">{selectedFileContent}</p>
                          )}
                          {/* Fallback for no content, no error message, and not explicitly an image or text */}
                          {selectedFileIsImage === null && selectedFileIsHtml === null && !selectedFileContent && (
                            <p className="text-sm text-muted-foreground px-2 py-2 bg-card rounded">Preview not available or file is empty.</p>
                          )}
                          {!selectedFileContent && selectedFileIsImage === true && !selectedFileUrl && (
                            <p className="text-sm text-red-500 px-2 py-2 bg-card rounded">Could not load image preview.</p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  };

  const renderStdout = () => {
    if (!stdout) return null;

    return (
      <div className="my-3">
        <div className="flex flex-row justify-between items-center mb-3">
          <h4 className="text-base font-medium">Standard Output</h4>
          <CardButton 
            icon={Copy} 
            onClick={handleCopyStdout}
            label="Copy"
            aria-label="Copy stdout to clipboard"
          />
        </div>
        <div className="w-full overflow-hidden">
          <pre className="whitespace-pre-wrap text-xs bg-card text-foreground overflow-y-auto overflow-x-auto font-mono max-h-[300px] px-2 py-2 max-w-full rounded">
            {stdout}
          </pre>
        </div>
      </div>
    );
  };

  const renderStderr = () => {
    if (!stderr) return null;

    return (
      <div className="my-3">
        <div className="flex flex-row justify-between items-center mb-3">
          <button
            onClick={() => setShowStderr(!showStderr)}
            className="flex items-center gap-2 text-base font-medium text-destructive hover:text-destructive/80"
          >
            <span>Standard Error</span>
            <span className="text-xs text-muted-foreground">
              {showStderr ? '(click to collapse)' : '(click to expand)'}
            </span>
          </button>
          {showStderr && (
            <CardButton 
              icon={Copy} 
              onClick={handleCopyStderr}
              label="Copy"
              aria-label="Copy stderr to clipboard"
            />
          )}
        </div>
        {showStderr && (
          <div className="w-full overflow-hidden">
            <pre className="whitespace-pre-wrap text-xs bg-card overflow-y-auto overflow-x-auto font-mono max-h-[300px] px-2 py-2 max-w-full rounded text-destructive">
              {stderr}
            </pre>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Sections in order: Universal Code, Attachments, Stdout, Stderr */}
      {renderUniversalCode()}
      {renderAttachments()}
      {renderStdout()}
      {renderStderr()}
    </div>
  );
};
