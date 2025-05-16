import React, { useState } from 'react';
import { ReportBlock } from '@/API';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ReloadIcon } from '@radix-ui/react-icons';
import { Storage } from 'aws-amplify';

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
    if (!block.detailsFiles) return;
    
    setLoading(true);
    try {
      let files: DetailFile[] = [];
      try {
        files = JSON.parse(block.detailsFiles);
      } catch (err) {
        console.error('Error parsing detailsFiles JSON:', err);
        return;
      }
      
      // Get pre-signed URLs for each file
      const filesWithUrls = await Promise.all(
        files.map(async (file) => {
          try {
            const url = await Storage.get(file.path, { level: 'protected' });
            return { ...file, url };
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
      const response = await fetch(file.url);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const text = await response.text();
      setFileContent(text);
    } catch (err) {
      console.error(`Error fetching file ${file.name}:`, err);
      setFileContent(`Error loading file: ${err.message}`);
    }
  };
  
  // Load detail files on first render
  React.useEffect(() => {
    if (block.detailsFiles) {
      loadDetailFiles();
    }
  }, [block.detailsFiles]);
  
  if (!block.detailsFiles) {
    return null;
  }
  
  return (
    <div className="mt-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Additional Files</CardTitle>
        </CardHeader>
        <CardContent>
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
        </CardContent>
        <CardFooter>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={loadDetailFiles}
            disabled={loading}
          >
            {loading ? (
              <>
                <ReloadIcon className="mr-2 h-4 w-4 animate-spin" />
                Refreshing
              </>
            ) : (
              "Refresh Files"
            )}
          </Button>
        </CardFooter>
      </Card>
      
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