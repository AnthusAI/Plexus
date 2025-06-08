import React, { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ReloadIcon } from '@radix-ui/react-icons';
// Import AWS Amplify Storage
import { getUrl, downloadData } from 'aws-amplify/storage';

// Define ReportBlock type if @/API is not available
interface ReportBlock {
  id: string;
  name?: string | null;
  position: number;
  type: string;
  output: Record<string, any>;
  log?: string | null;
  attachedFiles?: string[] | null;
}

type DetailFile = {
  name: string;
  path: string;
  url?: string;
};

interface BlockDetailsProps {
  block: ReportBlock;
}

const BlockDetails: React.FC<BlockDetailsProps> = ({ block }) => {
  const [detailFiles, setDetailFiles] = useState<DetailFile[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<DetailFile | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState<boolean>(false);

  const loadDetailFiles = async () => {
    if (!block.attachedFiles || block.attachedFiles.length === 0) return;
    
    setLoading(true);
    try {
      // Convert string array to DetailFile objects
      const files: DetailFile[] = block.attachedFiles.map(filePath => {
        const fileName = filePath.split('/').pop() || 'file';
        return { name: fileName, path: filePath };
      });
      
      // Get signed URLs for each file using Amplify Storage
      const filesWithUrls = await Promise.all(
        files.map(async (file) => {
          try {
            const urlResult = await getUrl({
              path: file.path,
            });
            return { ...file, url: urlResult.url.toString() };
          } catch (err) {
            console.error(`Error getting URL for file ${file.name}:`, err);
            return file;
          }
        })
      );
      
      setDetailFiles(filesWithUrls);
    } catch (err) {
      console.error('Error loading detail files:', err);
    } finally {
      setLoading(false);
    }
  };
  
  const viewTextFile = async (file: DetailFile) => {
    if (!file.url) return;
    
    setSelectedFile(file);
    setDialogOpen(true);
    setFileContent(null);
    
    try {
      // Use Amplify Storage to download the file content
      const downloadResult = await downloadData({
        path: file.path,
      }).result;
      
      // Convert the binary data to text
      const text = await downloadResult.body.text();
      setFileContent(text);
    } catch (error: any) {
      console.error(`Error fetching file ${file.name}:`, error);
      setFileContent(`Error loading file: ${error.message}`);
    }
  };
  
  // Load detail files on first render
  React.useEffect(() => {
    if (block.attachedFiles && block.attachedFiles.length > 0) {
      loadDetailFiles();
    }
  }, [block.attachedFiles]);
  
  if (!block.attachedFiles || block.attachedFiles.length === 0) {
    return null;
  }
  
  return (
    <div className="mt-4">
      <div className="bg-card rounded-lg p-4">
        <div className="mb-3">
          <h3 className="text-sm font-medium">Additional Files</h3>
        </div>
        <div>
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
              <span>Loading files...</span>
            </div>
          ) : detailFiles.length === 0 ? (
            <p className="text-sm text-muted-foreground">No detail files available</p>
          ) : (
            <ul className="space-y-2">
              {detailFiles.map((file, index) => (
                <li key={index} className="flex items-center justify-between">
                  <div className="flex items-center">
                    <Badge variant="outline" className="mr-2">
                      {file.name}
                    </Badge>
                  </div>
                  <div className="flex space-x-2">
                    {file.name.endsWith('.txt') && (
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => viewTextFile(file)}
                        disabled={!file.url}
                      >
                        View
                      </Button>
                    )}
                    <Button 
                      variant="outline" 
                      size="sm" 
                      asChild
                      disabled={!file.url}
                    >
                      <a href={file.url} target="_blank" rel="noopener noreferrer">
                        Download
                      </a>
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>{selectedFile?.name}</DialogTitle>
          </DialogHeader>
          <div className="overflow-auto flex-1">
            {fileContent === null ? (
              <div className="flex items-center justify-center py-8">
                <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
                <span>Loading file content...</span>
              </div>
            ) : (
              <pre className="whitespace-pre-wrap text-sm p-4 bg-muted rounded-md">
                {fileContent}
              </pre>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default BlockDetails; 