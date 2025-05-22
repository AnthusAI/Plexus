import React, { useState } from 'react';

export interface BlockDetailsHookProps {
  blockId?: string | null;
  hasLogs?: boolean;
  hasAttachedFiles?: boolean;
  attachedFiles?: string | null;
}

/**
 * Custom hook for managing block details viewing functionality
 */
export function useBlockDetails(props: BlockDetailsHookProps) {
  const {
    blockId,
    hasLogs,
    hasAttachedFiles,
    attachedFiles
  }: BlockDetailsHookProps = props;

  const [showDetailsDialog, setShowDetailsDialog] = useState(false);

  const openDetailsDialog = () => {
    if (hasLogs || hasAttachedFiles) {
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
    hasDetails: hasLogs || hasAttachedFiles,
    attachedFiles,
    blockId
  };
}

export interface BlockDetailsSummary {
  hasLogs: boolean;
  hasDetails: boolean;
  hasAttachedFiles: boolean;
  attachedFiles?: string | null;
}

export function useBlockDetailsSummary(block: any): BlockDetailsSummary {
  const [hasLogs, hasAttachedFiles, attachedFiles] = React.useMemo(() => {
    const hasLogs = block && typeof block.log === 'string' && block.log.trim() !== '';
    const hasAttachedFiles = block && typeof block.attachedFiles === 'string' && block.attachedFiles.trim() !== '';

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