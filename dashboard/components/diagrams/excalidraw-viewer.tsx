import React from 'react';
import dynamic from "next/dynamic";

// Dynamic import with SSR disabled for Excalidraw
const ExcalidrawWrapper = dynamic(
  () => import("../ui/excalidraw-wrapper"),
  { 
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-[400px] bg-muted/20 rounded-lg border-2 border-dashed border-muted-foreground/20">
        <div className="text-center space-y-2">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted border-t-foreground mx-auto"></div>
          <p className="text-sm text-muted-foreground">Loading diagram...</p>
        </div>
      </div>
    )
  }
);

interface ExcalidrawViewerProps {
  initialData?: any;
  viewModeEnabled?: boolean;
  width?: string | number;
  height?: string | number;
  className?: string;
}

const ExcalidrawViewer: React.FC<ExcalidrawViewerProps> = (props) => {
  return <ExcalidrawWrapper {...props} />;
};

export default ExcalidrawViewer; 