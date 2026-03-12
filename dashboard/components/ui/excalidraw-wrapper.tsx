"use client";

import React from 'react';
import { Excalidraw } from "@excalidraw/excalidraw";
import "@excalidraw/excalidraw/index.css";

// Use proper type imports that are actually exported
interface ExcalidrawWrapperProps {
  initialData?: any; // Using any for now to avoid import issues
  viewModeEnabled?: boolean;
  width?: string | number;
  height?: string | number;
  className?: string;
  onMount?: (api: any) => void;
}

const ExcalidrawWrapper: React.FC<ExcalidrawWrapperProps> = ({
  initialData,
  viewModeEnabled = true,
  width = "100%",
  height = "400px",
  className = "",
  onMount,
}) => {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [containerDimensions, setContainerDimensions] = React.useState({ width: 800, height: 400 });

  // Monitor container size changes
  React.useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setContainerDimensions({
          width: rect.width,
          height: rect.height
        });
      }
    };

    // Initial measurement
    updateDimensions();

    // Set up ResizeObserver for container size changes
    const resizeObserver = new ResizeObserver(updateDimensions);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    // Fallback for window resize
    window.addEventListener('resize', updateDimensions);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateDimensions);
    };
  }, []);

  React.useEffect(() => {
    // Add CSS to hide UI elements and completely disable interaction
    const style = document.createElement('style');
    style.textContent = `
      .excalidraw-container .excalidraw-button,
      .excalidraw-container .excalidraw-menu,
      .excalidraw-container .excalidraw-hamburger-menu,
      .excalidraw-container .excalidraw-main-menu,
      .excalidraw-container .Island,
      .excalidraw-container .ToolIcon,
      .excalidraw-container .App-menu,
      .excalidraw-container .App-toolbar,
      .excalidraw .App-menu,
      .excalidraw .App-toolbar,
      .excalidraw .Island {
        display: none !important;
      }
      .excalidraw-container .excalidraw {
        --ui-menu-width: 0px;
        margin: 0 !important;
        padding: 0 !important;
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 100% !important;
      }
      .excalidraw-container .excalidraw .App-canvas {
        cursor: default !important;
        pointer-events: none !important;
        margin: 0 !important;
        padding: 0 !important;
      }
      .excalidraw-container canvas {
        pointer-events: none !important;
        touch-action: none !important;
        margin: 0 !important;
        padding: 0 !important;
      }
      .excalidraw-container .excalidraw {
        pointer-events: none !important;
        user-select: none !important;
        -webkit-user-select: none !important;
        -moz-user-select: none !important;
        -ms-user-select: none !important;
      }
    `;
    document.head.appendChild(style);
    
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  // Calculate responsive scaling and positioning based on container width
  const scaleData = React.useMemo(() => {
    if (!initialData || !initialData.elements) return null;
    
    const elements = initialData.elements;
    if (elements.length === 0) return null;
    
    // Calculate content bounds
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    
    elements.forEach((element: any) => {
      if (element.x !== undefined && element.y !== undefined) {
        minX = Math.min(minX, element.x);
        minY = Math.min(minY, element.y);
        maxX = Math.max(maxX, element.x + (element.width || 0));
        maxY = Math.max(maxY, element.y + (element.height || 0));
      }
    });
    
    if (minX === Infinity) return null;
    
    const contentWidth = maxX - minX;
    const contentHeight = maxY - minY;
    
    // Add padding to prevent touching edges
    const padding = 20;
    
    // Always scale based on container width to ensure it fills the horizontal space
    const scale = (containerDimensions.width - (padding * 2)) / contentWidth;
    
    // Calculate the actual scaled dimensions
    const scaledWidth = contentWidth * scale;
    const scaledHeight = contentHeight * scale;
    
    // If content doesn't fill the available width, center it
    const availableWidth = containerDimensions.width - (2 * padding);
    const extraSpace = availableWidth - scaledWidth;
    
    // Determine if we're width or height constrained
    const scaleByWidth = (containerDimensions.width - (2 * padding)) / contentWidth;
    const scaleByHeight = (containerDimensions.height - (2 * padding)) / contentHeight;
    // Use tolerance for floating point comparison
    const tolerance = 0.0001;
    const isHeightConstrained = Math.abs(scale - scaleByHeight) < tolerance && scaleByHeight < scaleByWidth;
    
    // Always center the diagram for this use case
    const scrollX = extraSpace > 0 ? padding + (extraSpace / 2) : padding;
      
    // For dynamic height, position at top padding (container fits content exactly)
    const scrollY = padding;
    
    return {
      scale,
      scrollX,
      scrollY,
      scaledHeight,
      scaledWidth,
      padding,
    };
  }, [initialData, containerDimensions.width, containerDimensions.height]);

  // Prepare initial data with responsive scaling
  const processedInitialData = React.useMemo(() => {
    if (!initialData || !scaleData) return initialData;
    
    // Normalize the elements by translating them to start at (0,0)
    const elements = initialData.elements;
    if (!elements || elements.length === 0) return initialData;
    
    // Find the bounds again to get minX and minY
    let minX = Infinity, minY = Infinity;
    elements.forEach((element: any) => {
      if (element.x !== undefined && element.y !== undefined) {
        minX = Math.min(minX, element.x);
        minY = Math.min(minY, element.y);
      }
    });
    
    // Translate all elements to start at origin (0,0)
    const normalizedElements = elements.map((element: any) => {
      if (element.x !== undefined && element.y !== undefined) {
        return {
          ...element,
          x: element.x - minX,
          y: element.y - minY
        };
      }
      return element;
    });
    
    // Now position the normalized content
    const padding = 20;
    
    // Calculate the actual bounds of normalized elements
    let normalizedMinX = Infinity, normalizedMaxX = -Infinity;
    let normalizedMinY = Infinity, normalizedMaxY = -Infinity;
    
    normalizedElements.forEach((el: any) => {
      if (el.x !== undefined && el.y !== undefined) {
        normalizedMinX = Math.min(normalizedMinX, el.x);
        normalizedMinY = Math.min(normalizedMinY, el.y);
        // Handle different element types - some have width/height, some have x2/y2
        if (el.width !== undefined) {
          normalizedMaxX = Math.max(normalizedMaxX, el.x + el.width);
        } else if (el.x2 !== undefined) {
          normalizedMaxX = Math.max(normalizedMaxX, Math.max(el.x, el.x2));
        } else {
          normalizedMaxX = Math.max(normalizedMaxX, el.x);
        }
        
        if (el.height !== undefined) {
          normalizedMaxY = Math.max(normalizedMaxY, el.y + el.height);
        } else if (el.y2 !== undefined) {
          normalizedMaxY = Math.max(normalizedMaxY, Math.max(el.y, el.y2));
        } else {
          normalizedMaxY = Math.max(normalizedMaxY, el.y);
        }
      }
    });
    
    const normalizedContentWidth = normalizedMaxX - normalizedMinX;
    const normalizedContentHeight = normalizedMaxY - normalizedMinY;
    
    // If content doesn't fill the available width, center it
    const scaledWidth = normalizedContentWidth * scaleData.scale;
    const availableWidth = containerDimensions.width - (2 * padding);
    const extraSpace = availableWidth - scaledWidth;
    
    // Determine if we're width or height constrained
    const scaleByWidth = (containerDimensions.width - (2 * padding)) / normalizedContentWidth;
    const scaleByHeight = (containerDimensions.height - (2 * padding)) / normalizedContentHeight;
    // Use tolerance for floating point comparison
    const tolerance = 0.0001;
    const isHeightConstrained = Math.abs(scaleData.scale - scaleByHeight) < tolerance && scaleByHeight < scaleByWidth;
    
    // Always center the diagram for this use case
    const scrollX = extraSpace > 0 ? padding + (extraSpace / 2) : padding;
      
    // For dynamic height, position at top padding (container fits content exactly)
    const scrollY = padding;
    
    return {
      ...initialData,
      elements: normalizedElements,
      appState: {
        ...initialData.appState,
        zoom: { value: scaleData.scale },
        scrollX,
        scrollY,
        zenModeEnabled: true,
        // Disable all interactions
        activeTool: { type: "selection" },
        isResizing: false,
        isRotating: false,
        isDragging: false,
      }
    };
  }, [initialData, scaleData, containerDimensions.width]);

  // Calculate dynamic height based on content aspect ratio and scaled width
  const dynamicHeight = React.useMemo(() => {
    if (scaleData && scaleData.scaledHeight) {
      // Use the scaled content height plus padding on top and bottom
      return scaleData.scaledHeight + (scaleData.padding * 2);
    }
    // Fallback to provided height or default
    return typeof height === 'string' && height.includes('px') ? parseInt(height) : (typeof height === 'number' ? height : 400);
  }, [scaleData, height]);

  return (
    <div 
      ref={containerRef}
      className={`excalidraw-container bg-background ${className}`}
      style={{ 
        width, 
        height: `${dynamicHeight}px`,
        overflow: 'hidden',
        position: 'relative',
        pointerEvents: 'none',
        userSelect: 'none'
      }}
    >
      <Excalidraw
        key={`${containerDimensions.width}-${containerDimensions.height}`}
        initialData={processedInitialData}
        viewModeEnabled={true}
        UIOptions={{
          canvasActions: {
            export: false,
            loadScene: false,
            saveAsImage: false,
            saveToActiveFile: false,
            clearCanvas: false,
            changeViewBackgroundColor: false,
            toggleTheme: false,
          },
          tools: {
            image: false,
          },
          dockedSidebarBreakpoint: 0,
        }}
        zenModeEnabled={true}
        gridModeEnabled={false}
        theme="light"
        detectScroll={false}
        handleKeyboardGlobally={false}
      />
    </div>
  );
};

export default ExcalidrawWrapper; 