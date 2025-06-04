import React, { useState, useEffect } from 'react';
import { downloadData } from 'aws-amplify/storage';
// import { Skeleton } from '@/components/ui/skeleton'; // Removed Skeleton import
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Terminal } from 'lucide-react';

interface FileContentViewerProps {
  filePath: string;
}

const FileContentViewer: React.FC<FileContentViewerProps> = ({ filePath }) => {
  const [content, setContent] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isJson, setIsJson] = useState<boolean>(false); // Keep track if it's JSON for potential specific styling

  useEffect(() => {
    const fetchFileContent = async () => {
      setIsLoading(true);
      setError(null);
      try {
        // Determine which storage bucket to use based on file path
        let storageOptions: { path: string; options?: { bucket?: string } } = { path: filePath };
        
        if (filePath.startsWith('scoreresults/')) {
          // Score result files are stored in the scoreResultAttachments bucket
          storageOptions = {
            path: filePath,
            options: { bucket: 'scoreResultAttachments' }
          };
        } else if (filePath.startsWith('reportblocks/')) {
          // Report block files are stored in the reportBlockDetails bucket
          storageOptions = {
            path: filePath,
            options: { bucket: 'reportBlockDetails' }
          };
        } else if (filePath.startsWith('attachments/')) {
          // These files are in the default attachments bucket
          storageOptions = { path: filePath };
        }
        
        const downloadResult = await downloadData(storageOptions).result;
        const fileText = await downloadResult.body.text();
        
        if (filePath.endsWith('.json')) {
          setIsJson(true);
          try {
            const parsedJson = JSON.parse(fileText);
            setContent(JSON.stringify(parsedJson, null, 2));
          } catch (jsonError) {
            setContent(fileText); // Show raw text
            setError('Failed to parse JSON content. Displaying raw text.');
            console.error('JSON parsing error for '+filePath, jsonError);
          }
        } else {
          setIsJson(false);
          setContent(fileText);
        }
      } catch (e) {
        console.error(`Error fetching file content for ${filePath}:`, e);
        setError(`Failed to load file: ${filePath}. Error: ${(e as Error).message}`);
        setContent(null);
      } finally {
        setIsLoading(false);
      }
    };

    if (filePath) {
      fetchFileContent();
    } else {
      setError('File path is not provided.');
      setIsLoading(false);
      setContent(null);
    }
  }, [filePath]);

  if (isLoading) {
    return (
      <div className="p-4 text-muted-foreground">
        Loading file content...
      </div>
    );
  }

  // If there's an error and no content could be loaded at all
  if (error && content === null) {
    return (
      <Alert variant="destructive" className="m-4">
        <Terminal className="h-4 w-4" />
        <AlertTitle>Error Loading File</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  
  // If content is loaded (partially or fully), display it, possibly with a non-blocking error
  return (
    <div className="p-1">
      {error && content !== null && (
        // Non-destructive alert for errors like JSON parsing failure where raw content is still shown
        <Alert variant="default" className="mb-2 bg-yellow-50 border-yellow-300 text-yellow-700">
          <Terminal className="h-4 w-4" />
          <AlertTitle>Notice</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {content !== null && (
        <pre className="text-sm bg-muted p-3 rounded-md overflow-x-auto whitespace-pre-wrap break-words">
          <code>{content}</code>
        </pre>
      )}
      {content === null && !error && !isLoading && (
        // Case where there's no content, no error, no loading (e.g. empty file)
        <Alert variant="default" className="m-4">
            <Terminal className="h-4 w-4" />
            <AlertTitle>Empty File</AlertTitle>
            <AlertDescription>The file content is empty or could not be displayed.</AlertDescription>
        </Alert>
      )}
    </div>
  );
};

export default FileContentViewer; 