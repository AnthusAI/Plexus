import { useState } from 'react';

interface BlockDetailsHookProps {
  // The ID of the ReportBlock
  blockId: string;
  // Whether logs are available for this block
  hasLogs: boolean;
  // Whether details files are available for this block
  hasDetailsFiles: boolean;
  // The detailsFiles JSON string, if available
  detailsFiles?: string | null;
}

/**
 * Custom hook for managing block details viewing functionality
 */
export function useBlockDetails({ 
  blockId, 
  hasLogs, 
  hasDetailsFiles, 
  detailsFiles 
}: BlockDetailsHookProps) {
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);

  const openDetailsDialog = () => {
    if (hasLogs || hasDetailsFiles) {
      setShowDetailsDialog(true);
    }
  };

  const closeDetailsDialog = () => {
    setShowDetailsDialog(false);
  };

  return {
    showDetailsDialog,
    openDetailsDialog,
    closeDetailsDialog,
    hasDetails: hasLogs || hasDetailsFiles,
    detailsFiles,
    blockId
  };
} 