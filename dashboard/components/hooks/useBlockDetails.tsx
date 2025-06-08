import React, { useState } from 'react';

export interface BlockDetailsHookProps {
  blockId?: string | null;
  hasLogs?: boolean;
  hasAttachedFiles?: boolean;
  attachedFiles?: string[] | null;
}

/**
 * Custom hook for managing block details viewing functionality
 */
export function useBlockDetails({
  blockId,
  hasLogs = false,
  hasAttachedFiles = false,
  attachedFiles = null
}: BlockDetailsHookProps) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [showFiles, setShowFiles] = useState(false);

  // Open dialog for a specific block
  const openBlockDetails = (id: string) => {
    setSelectedBlockId(id);
    setIsDialogOpen(true);
  };

  // Close dialog
  const closeBlockDetails = () => {
    setIsDialogOpen(false);
    setSelectedBlockId(null);
    setShowLog(false);
    setShowFiles(false);
  };

  // Toggle log visibility
  const toggleLog = () => {
    setShowLog(!showLog);
  };

  // Toggle files visibility
  const toggleFiles = () => {
    setShowFiles(!showFiles);
  };

  return {
    isDialogOpen,
    selectedBlockId,
    showLog,
    showFiles,
    openBlockDetails,
    closeBlockDetails,
    toggleLog,
    toggleFiles
  };
}

export interface BlockDetailsSummary {
  hasLogs: boolean;
  hasDetails: boolean;
  hasAttachedFiles: boolean;
  attachedFiles?: string[] | null;
}

export function useBlockDetailsSummary(block: any): BlockDetailsSummary {
  const [hasLogs, hasAttachedFiles, attachedFiles] = React.useMemo(() => {
    const hasLogs = block && typeof block.log === 'string' && block.log.trim() !== '';
    const hasAttachedFiles = block && Array.isArray(block.attachedFiles) && block.attachedFiles.length > 0;

    if (hasLogs || hasAttachedFiles) {
      return [hasLogs, hasAttachedFiles, block?.attachedFiles || null];
    }
    return [false, false, null];
  }, [block]);

  const summary: BlockDetailsSummary = {
    hasLogs,
    hasDetails: hasLogs || hasAttachedFiles,
    hasAttachedFiles,
    attachedFiles,
  };

  return summary;
} 