import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MoreHorizontal, X, Square, Columns2, FileStack, ChevronDown, ChevronUp, Award, FileCode, Minimize, Maximize, ArrowDownWideNarrow, Expand, Shrink, TestTube, FlaskConical, FlaskRound, TestTubes } from 'lucide-react'
import { CardButton } from '@/components/CardButton'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import * as Popover from '@radix-ui/react-popover'
import {
  DropdownMenu as ShadcnDropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { generateClient } from 'aws-amplify/api'
import { toast } from 'sonner'
import { ScoreVersionHistory } from './score-version-history'
import type { GraphQLResult } from '@aws-amplify/api'
import Editor, { Monaco } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import { parse as parseYaml, stringify as stringifyYaml } from 'yaml'
import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import type { editor } from 'monaco-editor'
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions } from '@/lib/monaco-theme'
import { TestScoreDialog } from '@/components/scorecards/test-score-dialog'

const client = generateClient();

export interface ScoreData {
  id: string
  name: string
  description: string
  type: string
  order: number
  externalId?: string
  key?: string
  icon?: React.ReactNode
  configuration?: string // YAML configuration string
  championVersionId?: string // ID of the champion version
}

interface ScoreVersion {
  id: string
  scoreId: string
  configuration: string // YAML string
  isFeatured: boolean
  isChampion?: boolean
  note?: string
  createdAt: string
  updatedAt: string
  user?: {
    name: string
    avatar: string
    initials: string
  }
}

interface ScoreVersionRecord {
  scoreId: string
  score: {
    name: string
    order: number
    type: string
    // ... other score fields
  }
  versions: ScoreVersion[]
}

interface GetScoreVersionsResponse {
  listScoreVersions: {
    items: ScoreVersion[]
  }
}

interface CreateScoreVersionResponse {
  createScoreVersion: ScoreVersion
}

// Add a new interface for the secondary index query response
interface GetScoreVersionsByScoreIdResponse {
  listScoreVersionByScoreIdAndCreatedAt: {
    items: ScoreVersion[]
  }
}

interface GetScoreResponse {
  getScore: {
    id: string
    name: string
    externalId?: string
    championVersionId?: string
  }
}

interface ScoreComponentProps extends React.HTMLAttributes<HTMLDivElement> {
  score: ScoreData
  variant?: 'grid' | 'detail'
  isSelected?: boolean
  onClick?: () => void
  onClose?: () => void
  onToggleFullWidth?: () => void
  isFullWidth?: boolean
  onSave?: () => void
  exampleItems?: Array<{
    id: string
    displayValue: string
  }>
}

interface DetailContentProps {
  score: ScoreData
  isFullWidth: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onEditChange?: (changes: Partial<ScoreData>) => void
  onSave?: () => void
  onCancel?: () => void
  hasChanges?: boolean
  versions?: ScoreVersion[]
  championVersionId?: string
  selectedVersionId?: string
  onVersionSelect?: (version: ScoreVersion) => void
  onToggleFeature?: (versionId: string) => void
  onPromoteToChampion?: (versionId: string) => void
  versionNote: string
  onNoteChange: (note: string) => void
  resetEditingCounter: number
  forceExpandHistory?: boolean
  exampleItems?: Array<{
    id: string
    displayValue: string
  }>
}

const GridContent = React.memo(({ 
  score,
  isSelected 
}: { 
  score: ScoreData
  isSelected?: boolean
}) => {
  // Pre-compute all displayed values in a single operation before rendering
  // This ensures React renders them in the same cycle
  const displayData = React.useMemo(() => ({
    name: score.name,
    description: score.description || ''
  }), [score.name, score.description]);
  
  return (
    <div className="flex justify-between items-start">
      <div className="space-y-2 min-h-[4.5rem]">
        <div className="font-medium">{displayData.name}</div>
        <div className="text-sm">{displayData.description}</div>
      </div>
      {score.icon && (
        <div className="text-muted-foreground">
          {score.icon}
        </div>
      )}
    </div>
  )
})

// Enhance ResizableEditorContainer with better drag handle
const ResizableEditorContainer = ({ 
  height,
  onHeightChange,
  children,
  isFullscreen = false
}: { 
  height: number,
  onHeightChange: (newHeight: number) => void,
  children: React.ReactNode,
  isFullscreen?: boolean
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isResizing, setIsResizing] = useState(false);
  
  // Double-click handler to toggle between compact and expanded sizes
  const handleDoubleClick = () => {
    const newHeight = height < 500 ? 500 : 200;
    if (containerRef.current) {
      containerRef.current.style.height = `${newHeight}px`;
      onHeightChange(newHeight);
    }
  };
  
  return (
    <div 
      ref={containerRef}
      className={cn(
        "relative bg-background rounded-lg",
        isResizing && "border border-accent",
        isFullscreen ? "h-full overflow-hidden" : "resize-y overflow-auto"
      )}
      style={!isFullscreen ? { 
        height: `${height}px`,
        minHeight: '150px',
        maxHeight: '80vh'
      } : { 
        height: isFullscreen ? 'calc(100% - 40px)' : `${height}px` 
      }}
      onMouseDown={() => setIsResizing(true)}
      onMouseUp={() => setIsResizing(false)}
      onMouseLeave={() => setIsResizing(false)}
    >
      {children}
      {!isFullscreen && (
        <div 
          className={cn(
            "absolute bottom-0 left-0 right-0 h-4 cursor-ns-resize hover:bg-accent/30",
            isResizing && "bg-accent/30"
          )}
          onDoubleClick={handleDoubleClick}
        >
          <div className="flex justify-center items-center h-full">
            <div className="w-10 h-1.5 rounded-full bg-muted-foreground/50"></div>
          </div>
        </div>
      )}
    </div>
  );
};

const DetailContent = React.memo(({
  score,
  isFullWidth,
  onToggleFullWidth,
  onClose,
  onEditChange,
  onSave,
  onCancel,
  hasChanges,
  versions,
  championVersionId,
  selectedVersionId,
  onVersionSelect,
  onToggleFeature,
  onPromoteToChampion,
  versionNote,
  onNoteChange,
  resetEditingCounter,
  forceExpandHistory,
  exampleItems = [],
}: DetailContentProps) => {
  // Get the current version's configuration
  const currentVersion = versions?.find(v => 
    v.id === (selectedVersionId || championVersionId)
  )
  
  // Parse YAML configuration if available, otherwise create default YAML
  const defaultYaml = stringifyYaml({
    name: score.name,
    externalId: score.externalId,
    key: score.key
  })
  
  // Track the current configuration in local state
  const [currentConfig, setCurrentConfig] = React.useState(currentVersion?.configuration || defaultYaml)
  
  // Track if we're currently editing to prevent useEffect from overriding changes
  const [isEditing, setIsEditing] = React.useState(false)
  
  // Let ScoreVersionHistory component handle its own featured filtering with smart defaults
  
  // Reset isEditing when resetEditingCounter changes
  React.useEffect(() => {
    setIsEditing(false);
  }, [resetEditingCounter])
  
  // Update currentConfig when score or version changes, but only if we're not editing
  React.useEffect(() => {
    if (!isEditing) {
      setCurrentConfig(currentVersion?.configuration || defaultYaml);
    }
  }, [currentVersion, defaultYaml, score, isEditing])
  
  // Update currentConfig when score.configuration changes (from parent component)
  React.useEffect(() => {
    if (score.configuration && !isEditing) {
      setCurrentConfig(score.configuration);
    }
  }, [score.configuration, isEditing])
  
  // Parse current configuration for form fields
  const parsedConfig = React.useMemo(() => {
    try {
      const parsed = parseYaml(currentConfig);
      
      // Handle all possible external ID formats: externalId, external_id, and id
      // Important: Check for the presence of the field in the parsed object, not just in the string
      const externalIdValue = parsed.externalId !== undefined ? 
        parsed.externalId : 
        (parsed.external_id !== undefined ? parsed.external_id : 
         (parsed.id !== undefined ? parsed.id : score.externalId));
      
      return {
        ...parsed,
        // Ensure we always have externalId in our parsed config regardless of format in YAML
        externalId: externalIdValue
      };
    } catch (error) {
      console.error('Error parsing YAML:', error)
      return { 
        name: score.name, 
        externalId: score.externalId,
        key: score.key
      }
    }
  }, [currentConfig, score])

  // Handle form field changes
  const handleFormChange = (field: string, value: string) => {
    
    // Set editing flag to prevent useEffect from overriding our changes
    setIsEditing(true);
    
    // Update the form field in the parent component
    onEditChange?.({ [field]: value });
    
    // Also update the YAML directly in our local state
    try {
      const parsed = parseYaml(currentConfig);
      
      // Check which format is being used for external ID by examining the parsed object
      // This is more reliable than string matching in the YAML
      const hasExternalId = 'externalId' in parsed;
      const hasExternalUnderscoreId = 'external_id' in parsed;
      const hasSimpleId = 'id' in parsed && !hasExternalId && !hasExternalUnderscoreId;

      
      // Update the field
      if (field === 'externalId') {
        if (hasExternalUnderscoreId) {
          parsed.external_id = value;
          // Remove other formats if they exist
          if ('externalId' in parsed) delete parsed.externalId;
          if ('id' in parsed) delete parsed.id;
        } else if (hasSimpleId) {
          parsed.id = value;
          // Remove other formats if they exist
          if ('externalId' in parsed) delete parsed.externalId;
          if ('external_id' in parsed) delete parsed.external_id;
        } else {
          // Default to externalId format if no format is detected
          parsed.externalId = value;
          // Remove other formats if they exist
          if ('external_id' in parsed) delete parsed.external_id;
          if ('id' in parsed) delete parsed.id;
        }
      } else {
        parsed[field] = value;
      }
      
      // Update the configuration
      const updatedYaml = stringifyYaml(parsed);
      setCurrentConfig(updatedYaml);
      
      // Also pass the updated configuration to the parent
      onEditChange?.({ configuration: updatedYaml });
    } catch (error) {
      console.error('Error updating YAML from form field:', error);
    }
  };

  // Handle note changes
  const handleNoteChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    // Call the parent's onNoteChange handler
    onNoteChange?.(e.target.value);
  };

  // Create a ref to store the Monaco instance
  const monacoRef = useRef<Monaco | null>(null);
  
  // Set up Monaco theme watcher
  useEffect(() => {
    if (!monacoRef.current) return
    
    const cleanup = setupMonacoThemeWatcher(monacoRef.current)
    return cleanup
  }, [monacoRef.current])

  // Add state for editor height with localStorage persistence
  const [editorHeight, setEditorHeight] = useState(() => {
    // Try to get saved height from localStorage
    if (typeof window !== 'undefined') {
      const savedHeight = localStorage.getItem('monaco-editor-height');
      if (savedHeight) {
        const parsed = parseInt(savedHeight, 10);
        if (!isNaN(parsed) && parsed >= 150) {
          return parsed;
        }
      }
    }
    return 350; // Default to medium height
  });
  
  // Save height to localStorage when it changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('monaco-editor-height', editorHeight.toString());
    }
  }, [editorHeight]);
  
  // Add editor instance ref
  const editorInstanceRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  
  // Handle height change
  const handleHeightChange = useCallback((newHeight: number) => {
    setEditorHeight(newHeight);
    
    // Update editor layout immediately
    if (editorInstanceRef.current) {
      editorInstanceRef.current.layout();
    }
  }, []);

  // Add state for editor fullscreen mode
  const [isEditorFullscreen, setIsEditorFullscreen] = useState(false);

  // Add state to detect if we're on an iPad/mobile device
  const [isMobileDevice, setIsMobileDevice] = React.useState(false);
  
  // Add state for test score dialog
  const [isTestDialogOpen, setIsTestDialogOpen] = React.useState(false);
  
  // Detect mobile devices on component mount
  React.useEffect(() => {
    const checkMobileDevice = () => {
      const userAgent = navigator.userAgent.toLowerCase();
      const isIPad = /ipad/.test(userAgent) || 
                    (/macintosh/.test(userAgent) && 'ontouchend' in document);
      const isTablet = /tablet|ipad|playbook|silk|android(?!.*mobile)/i.test(userAgent);
      const isMobile = /iphone|ipod|android|blackberry|opera mini|opera mobi|skyfire|maemo|windows phone|palm|iemobile|symbian|symbianos|fennec/i.test(userAgent);
      
      setIsMobileDevice(isIPad || isTablet || isMobile);
    };
    
    checkMobileDevice();
  }, []);

  const handleTestScore = () => {
    setIsTestDialogOpen(true);
  };

  const handleTestScoreWithItem = (itemId: string) => {
    console.log('Testing score with item:', { scoreId: score.id, scoreName: score.name, itemId });
    // TODO: Implement actual test logic
    toast.success(`Testing score "${score.name}" with selected item`);
  };

  const closeTestScoreDialog = () => {
    setIsTestDialogOpen(false);
  };

  return (
    <div className={cn(
      "w-full flex flex-col min-h-0 h-full",
      isEditorFullscreen && "absolute inset-0 z-10 bg-background p-4 rounded-lg"
    )}>
      {/* Hide the header section when in fullscreen mode */}
      {!isEditorFullscreen && (
        <div className="flex justify-between items-start w-full">
          <div className="space-y-2 flex-1">
            <Input
              value={parsedConfig.name || ''}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
                handleFormChange('name', e.target.value)
              }
              onFocus={() => setIsEditing(true)}
              className="text-lg font-semibold bg-background border-0 px-2 h-auto w-full
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md"
              placeholder="Score Name"
            />
            <div className="flex gap-2 w-full">
              <Input
                value={parsedConfig.key || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
                  handleFormChange('key', e.target.value)
                }
                onFocus={() => setIsEditing(true)}
                className="font-mono bg-background border-0 px-2 h-auto flex-1
                         focus-visible:ring-0 focus-visible:ring-offset-0 
                         placeholder:text-muted-foreground rounded-md"
                placeholder="score-key"
              />
              <Input
                value={parsedConfig.externalId || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => 
                  handleFormChange('externalId', e.target.value)
                }
                onFocus={() => setIsEditing(true)}
                className="font-mono bg-background border-0 px-2 h-auto flex-1
                         focus-visible:ring-0 focus-visible:ring-offset-0 
                         placeholder:text-muted-foreground rounded-md"
                placeholder="External ID"
              />
            </div>
            <textarea
              value={versionNote}
              onChange={handleNoteChange}
              placeholder="Add a note about this version..."
              className="w-full px-2 py-1.5 rounded-md bg-background border-0 text-sm resize-none
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground"
              rows={2}
            />
          </div>
          <div className="flex gap-2 ml-4">
            <ShadcnDropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                  aria-label="More options"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleTestScore}>
                  <TestTube className="mr-2 h-4 w-4" />
                  Test
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => {
                  console.log('Evaluate Accuracy clicked');
                  toast.success('Evaluate Accuracy action triggered');
                }}>
                  <FlaskConical className="mr-2 h-4 w-4" />
                  Evaluate Accuracy
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => {
                  console.log('Evaluate Consistency clicked');
                  toast.success('Evaluate Consistency action triggered');
                }}>
                  <FlaskRound className="mr-2 h-4 w-4" />
                  Evaluate Consistency
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => {
                  console.log('Evaluate Alignment clicked');
                  toast.success('Evaluate Alignment action triggered');
                }}>
                  <TestTubes className="mr-2 h-4 w-4" />
                  Evaluate Alignment
                </DropdownMenuItem>
              </DropdownMenuContent>
            </ShadcnDropdownMenu>
            {onToggleFullWidth && (
              <CardButton
                icon={isFullWidth ? Columns2 : Square}
                onClick={onToggleFullWidth}
                aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
              />
            )}
            {onClose && (
              <CardButton
                icon={X}
                onClick={onClose}
                aria-label="Close"
              />
            )}
          </div>
        </div>
      )}

      {/* Configuration Label with Fullscreen Toggle */}
      <div className={cn(
        "mt-6 flex items-center justify-between",
        isEditorFullscreen && "mt-0 mb-2"
      )}>
        <div className="flex items-center gap-2">
          {!isEditorFullscreen && (
            <>
              <FileCode className="h-4 w-4 text-foreground" />
              <span className="text-sm font-medium">Configuration</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isEditorFullscreen && (
            <ShadcnDropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                  aria-label="More options"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleTestScore}>
                  <TestTube className="mr-2 h-4 w-4" />
                  Test
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => {
                  console.log('Evaluate Accuracy clicked');
                  toast.success('Evaluate Accuracy action triggered');
                }}>
                  <FlaskConical className="mr-2 h-4 w-4" />
                  Evaluate Accuracy
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => {
                  console.log('Evaluate Consistency clicked');
                  toast.success('Evaluate Consistency action triggered');
                }}>
                  <FlaskRound className="mr-2 h-4 w-4" />
                  Evaluate Consistency
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => {
                  console.log('Evaluate Alignment clicked');
                  toast.success('Evaluate Alignment action triggered');
                }}>
                  <TestTubes className="mr-2 h-4 w-4" />
                  Evaluate Alignment
                </DropdownMenuItem>
              </DropdownMenuContent>
            </ShadcnDropdownMenu>
          )}
          <CardButton
            icon={isEditorFullscreen ? Shrink : Expand}
            onClick={() => setIsEditorFullscreen(!isEditorFullscreen)}
            aria-label={isEditorFullscreen ? 'Exit fullscreen' : 'Fullscreen editor'}
          />
        </div>
      </div>

      {/* YAML Editor - Make it flex to fill available space */}
      <div className={cn(
        "flex-1 flex flex-col min-h-0",
        isEditorFullscreen ? "mt-2" : "mt-2"
      )} style={{ transition: 'none' }}>
                  {!isEditorFullscreen ? (
          // Normal mode: flexible height container
          <div className="flex-1 bg-background rounded-lg overflow-hidden relative min-h-[300px]">
            <Editor
              height="100%"
              defaultLanguage="yaml"
              value={currentConfig}
              key={`editor-${selectedVersionId || championVersionId}`}
              onMount={(editor, monaco) => {
                // Store the editor instance
                editorInstanceRef.current = editor;
                
                // Store the Monaco instance
                monacoRef.current = monaco;
                
                // Apply our custom theme when the editor mounts
                defineCustomMonacoThemes(monaco);
                applyMonacoTheme(monaco);
                
                // Force immediate layout to ensure correct sizing
                editor.layout();
                
                // Add error handling for iPad-specific issues
                window.addEventListener('error', (event) => {
                  if (event.message === 'Canceled: Canceled' || 
                      event.error?.message === 'Canceled: Canceled') {
                    event.preventDefault();
                    return true; // Prevent the error from propagating
                  }
                  return false;
                });
              }}
              onChange={(value) => {
                if (!value) return;
                
                try {
                  // Set editing flag to prevent useEffect from overriding our changes
                  setIsEditing(true);
                  
                  // Parse YAML to validate it and get values for form
                  const parsed = parseYaml(value)
                  
                  // Extract external ID from all possible formats
                  const externalIdValue = parsed.externalId !== undefined ? 
                    parsed.externalId : 
                    (parsed.external_id !== undefined ? parsed.external_id : 
                     (parsed.id !== undefined ? parsed.id : undefined));

                  
                  // Update our local state
                  setCurrentConfig(value);
                  
                  // Pass the updated configuration to the parent
                  onEditChange?.({
                    name: parsed.name,
                    externalId: externalIdValue !== undefined ? String(externalIdValue) : undefined,
                    key: parsed.key,
                    description: parsed.description,
                    configuration: value // Store the original YAML string
                  });
                } catch (error) {
                  // Handle cancellation errors gracefully
                  if (error instanceof Error && 
                      (error.message === 'Canceled' || error.message === 'Canceled: Canceled')) {
                    return; // Just ignore the error
                  }
                  
                  // Ignore other parse errors while typing
                }
              }}
              options={getCommonMonacoOptions(isMobileDevice)}
            />
          </div>
        ) : (
          // Fullscreen mode: use the old resizable container
          <ResizableEditorContainer 
            height={800}
            onHeightChange={handleHeightChange}
            isFullscreen={isEditorFullscreen}
          >
          <Editor
            height="100%"
            defaultLanguage="yaml"
            value={currentConfig}
            key={`editor-${selectedVersionId || championVersionId}`}
            onMount={(editor, monaco) => {
              // Store the editor instance
              editorInstanceRef.current = editor;
              
              // Store the Monaco instance
              monacoRef.current = monaco;
              
              // Apply our custom theme when the editor mounts
              defineCustomMonacoThemes(monaco);
              applyMonacoTheme(monaco);
              
              // Force immediate layout to ensure correct sizing
              editor.layout();
              
              // Add error handling for iPad-specific issues
              window.addEventListener('error', (event) => {
                if (event.message === 'Canceled: Canceled' || 
                    event.error?.message === 'Canceled: Canceled') {
                  event.preventDefault();
                  return true; // Prevent the error from propagating
                }
                return false;
              });
            }}
            onChange={(value) => {
              if (!value) return;
              
              try {
                // Set editing flag to prevent useEffect from overriding our changes
                setIsEditing(true);
                
                // Parse YAML to validate it and get values for form
                const parsed = parseYaml(value)
                
                // Extract external ID from all possible formats
                const externalIdValue = parsed.externalId !== undefined ? 
                  parsed.externalId : 
                  (parsed.external_id !== undefined ? parsed.external_id : 
                   (parsed.id !== undefined ? parsed.id : undefined));

                
                // Update our local state
                setCurrentConfig(value);
                
                // Pass the updated configuration to the parent
                onEditChange?.({
                  name: parsed.name,
                  externalId: externalIdValue !== undefined ? String(externalIdValue) : undefined,
                  key: parsed.key,
                  description: parsed.description,
                  configuration: value // Store the original YAML string
                });
              } catch (error) {
                // Handle cancellation errors gracefully
                if (error instanceof Error && 
                    (error.message === 'Canceled' || error.message === 'Canceled: Canceled')) {
                  return; // Just ignore the error
                }
                
                // Ignore other parse errors while typing
              }
            }}
            options={getCommonMonacoOptions(isMobileDevice)}
          />
          </ResizableEditorContainer>
        )}
      </div>

      {/* Action buttons - show in both normal and fullscreen modes */}
      {hasChanges && (
        <div className={cn(
          "mt-4 space-y-4",
          isEditorFullscreen && "mt-4"
        )}>
          <div className={cn(
            "flex gap-2",
            isEditorFullscreen ? "flex-row items-end" : "justify-end"
          )}>
            {isEditorFullscreen && (
              <textarea
                value={versionNote}
                onChange={(e) => onNoteChange(e.target.value)}
                placeholder="Add a note about this version..."
                className="flex-1 px-3 py-2 rounded-md bg-background border border-input text-sm resize-none h-10
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2
                         placeholder:text-muted-foreground"
                rows={1}
              />
            )}
            <div className="flex gap-2">
              <Button className="bg-card hover:bg-card/80 text-card-foreground shadow-none border-0" onClick={() => {
                setIsEditing(false); // Reset editing flag
                onCancel?.();
              }}>Cancel</Button>
              <Button onClick={() => {
                setIsEditing(false); // Reset editing flag
                if (isEditorFullscreen) {
                  setIsEditorFullscreen(false); // Exit fullscreen after save
                }
                onSave?.();
              }}>Save Changes</Button>
            </div>
          </div>
        </div>
      )}

      {/* Version history - hide in fullscreen mode */}
      {!isEditorFullscreen && versions && (
        <div className="mt-6 overflow-hidden flex-shrink-0">
          <ScoreVersionHistory
            versions={versions}
            championVersionId={championVersionId}
            selectedVersionId={selectedVersionId}
            onVersionSelect={onVersionSelect}
            onToggleFeature={onToggleFeature}
            onPromoteToChampion={onPromoteToChampion}
            forceExpanded={forceExpandHistory}
          />
        </div>
      )}

      {/* Test Score Dialog */}
      <TestScoreDialog
        isOpen={isTestDialogOpen}
        onClose={closeTestScoreDialog}
        onTest={handleTestScoreWithItem}
        scoreName={score.name}
        exampleItems={exampleItems}
      />
    </div>
  )
})

export function ScoreComponent({
  score,
  variant = 'grid',
  isSelected,
  onClick,
  onClose,
  onToggleFullWidth,
  isFullWidth = false,
  onSave,
  exampleItems = [],
  className,
  ...props
}: ScoreComponentProps) {
  const [editedScore, setEditedScore] = React.useState<ScoreData>(score)
  const [hasChanges, setHasChanges] = React.useState(false)
  const [versions, setVersions] = React.useState<ScoreVersion[]>([])
  const [championVersionId, setChampionVersionId] = React.useState<string>()
  const [selectedVersionId, setSelectedVersionId] = React.useState<string>()
  const [versionNote, setVersionNote] = React.useState('')
  const [resetEditingCounter, setResetEditingCounter] = React.useState(0)
  const [forceExpandHistory, setForceExpandHistory] = React.useState(false)
  

  
  // Ensure editedScore is updated when score prop changes
  React.useEffect(() => {
    setEditedScore(score)
    setVersionNote('') // Reset note when score changes
    setHasChanges(false) // Reset changes flag when score changes
    setResetEditingCounter(prev => prev + 1) // Signal to DetailContent to reset editing state
    setForceExpandHistory(false) // Reset expansion when score changes
  }, [score])
  
  // Fetch versions when score changes
  React.useEffect(() => {
    const fetchVersions = async () => {
      try {
        
        // First, get the score details to get the championVersionId
        const scoreResponse = await client.graphql({
          query: `
            query GetScore($id: ID!) {
              getScore(id: $id) {
                id
                name
                externalId
                championVersionId
              }
            }
          `,
          variables: {
            id: String(score.id)
          }
        }) as GraphQLResult<GetScoreResponse>;
        
        let championId: string | undefined;
        
        if ('data' in scoreResponse && scoreResponse.data?.getScore) {
          const scoreData = scoreResponse.data.getScore;
          championId = scoreData?.championVersionId;
          
          if (championId) {
            setChampionVersionId(championId);
          }
        }
        
        // Then fetch all versions using the secondary index query
        // This query uses the GSI on scoreId with createdAt as sort key
        // which correctly returns all versions for a score
        const response = await client.graphql({
          query: `
            query GetScoreVersionsByScoreId($scoreId: String!, $sortDirection: ModelSortDirection) {
              listScoreVersionByScoreIdAndCreatedAt(
                scoreId: $scoreId,
                sortDirection: $sortDirection
              ) {
                items {
                  id
                  scoreId
                  configuration
                  isFeatured
                  note
                  createdAt
                  updatedAt
                }
              }
            }
          `,
          variables: {
            scoreId: String(score.id), // Explicitly convert to string
            sortDirection: "DESC" // Newest first
          }
        }) as GraphQLResult<GetScoreVersionsByScoreIdResponse>;
        
        if ('data' in response && response.data?.listScoreVersionByScoreIdAndCreatedAt?.items) {
          const versionItems = response.data.listScoreVersionByScoreIdAndCreatedAt.items;
          setVersions(versionItems);
          
          // Sort versions by createdAt in descending order
          const sortedVersions = [...versionItems].sort(
            (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          );
          
          // Find champion version or use the most recent one if no champion exists
          const champion = championId 
            ? versionItems.find(v => v.id === championId) 
            : null;
            
          if (champion) {
            // Automatically select the champion version
            handleVersionSelect(champion);
          } else if (sortedVersions.length > 0) {
            // If no champion exists but we have versions, select the most recent one
            // but don't automatically set it as champion
            handleVersionSelect(sortedVersions[0]);
            
            // Only set the most recent version as champion if there are no champions at all
            // AND there are no existing versions (this is the first version)
            if (!championId && sortedVersions.length === 1) {
              setChampionVersionId(sortedVersions[0].id);
              
              // Update the Score record to set this as the champion version
              try {
                await client.graphql({
                  query: `
                    mutation UpdateScoreChampion($input: UpdateScoreInput!) {
                      updateScore(input: $input) {
                        id
                        championVersionId
                      }
                    }
                  `,
                  variables: {
                    input: {
                      id: String(score.id),
                      championVersionId: String(sortedVersions[0].id),
                    }
                  }
                });

              } catch (error) {
                console.error('Error setting initial champion version:', error);
              }
            }
          }
        }
      } catch (error) {
        console.error('Error fetching versions:', error);
      }
    };
    fetchVersions();
  }, [score])

  const handleEditChange = (changes: Partial<ScoreData>) => {
    
    // Always update the editedScore state with the changes
    setEditedScore(prev => {
      // Create updated state with the changes
      const updated = { ...prev, ...changes };
      
      // Mark that we have unsaved changes
      setHasChanges(true);
      
      // If we're changing fields other than the note, reset onlyNoteChanged flag
      if ('name' in changes || 'key' in changes || 'externalId' in changes || 
          'description' in changes || 'configuration' in changes) {
        // Mark field changes detected
      }
      
      // If we're directly setting the configuration (from the YAML editor or form field handler),
      // we don't need to regenerate it
      if (changes.configuration) {
        return updated;
      }
      
      // Otherwise, we need to update the YAML configuration to match the form fields
      try {
        // Get current configuration or create default
        let currentConfig;
        try {
          currentConfig = prev.configuration ? parseYaml(prev.configuration) : {};
        } catch (e) {
          currentConfig = {};
        }
        
        // Check if using external_id format
        const usesUnderscoreFormat = prev.configuration && 
          prev.configuration.includes('external_id:') && 
          !prev.configuration.includes('externalId:');
        
        // Create updated config
        const updatedConfig = { ...currentConfig };
        
        // Update name if changed
        if (changes.name !== undefined) {
          updatedConfig.name = changes.name;
        }
        
        // Update key if changed
        if (changes.key !== undefined) {
          updatedConfig.key = changes.key;
        }
        
        // Update description if changed
        if (changes.description !== undefined) {
          updatedConfig.description = changes.description;
        }
        
        // Update external ID with the appropriate format
        if (changes.externalId !== undefined) {
          if (usesUnderscoreFormat) {
            updatedConfig.external_id = changes.externalId;
            // Remove camelCase if exists
            if ('externalId' in updatedConfig) {
              delete updatedConfig.externalId;
            }
          } else {
            updatedConfig.externalId = changes.externalId;
            // Remove snake_case if exists
            if ('external_id' in updatedConfig) {
              delete updatedConfig.external_id;
            }
          }
        }
        
        // Update the configuration
        updated.configuration = stringifyYaml(updatedConfig);
      } catch (error) {
        console.error('Error updating YAML configuration:', error);
      }
      
      return updated;
    });
  };

  const handleCancel = () => {
    setEditedScore(score)
    setVersionNote('') // Reset note on cancel
    setHasChanges(false)
    setSelectedVersionId(undefined) // Reset selection to champion
    setResetEditingCounter(prev => prev + 1) // Signal to DetailContent to reset editing state
  }

  const handleVersionSelect = (version: ScoreVersion) => {
    setSelectedVersionId(version.id)
    setVersionNote(version.note || '')
    
    // Signal to DetailContent to reset editing state
    setResetEditingCounter(prev => prev + 1)
    
    try {
      // Parse the YAML configuration to extract all fields
      const config = parseYaml(version.configuration)
      
      // Extract external ID from either format
      const externalIdValue = config.externalId !== undefined ? 
        config.externalId : 
        (config.external_id !== undefined ? config.external_id : 
         (config.id !== undefined ? config.id : undefined));

      
      // Update the editedScore with values from the YAML configuration
      // This ensures we're using the YAML as the source of truth
      setEditedScore(prev => {
        const updated = {
          ...prev,
          // Use values from YAML, falling back to previous values if not present
          name: config.name !== undefined ? config.name : prev.name,
          // Support all three formats for external ID
          externalId: externalIdValue !== undefined ? String(externalIdValue) : prev.externalId,
          key: config.key !== undefined ? config.key : prev.key,
          description: config.description !== undefined ? config.description : prev.description,
          // Store the complete configuration for the editor
          configuration: version.configuration
        };
        return updated;
      })
      
      // Reset hasChanges since we just loaded a version
      setHasChanges(false);
      
      // Remove toast notification for simply viewing a version
      // We only want notifications for actions that change state
    } catch (error) {
      console.error('Error parsing version YAML:', error)
      toast.error('Error loading version configuration')
    }
  }

  const handleToggleFeature = async (versionId: string) => {
    try {
      const version = versions.find(v => v.id === versionId);
      if (!version) return;

      // Enable API call to persist the feature status
      const response = await client.graphql({
        query: `
          mutation UpdateScoreVersion($input: UpdateScoreVersionInput!) {
            updateScoreVersion(input: $input) {
              id
              isFeatured
            }
          }
        `,
        variables: {
          input: {
            id: String(versionId),
            isFeatured: !version.isFeatured
          }
        }
      });

      // Update local state regardless of response
      // This ensures UI is updated even if we can't verify the response format
      setVersions(prev => prev.map(v => 
        v.id === versionId ? { ...v, isFeatured: !v.isFeatured } : v
      ));

      toast.success('Version feature status updated');
    } catch (error) {
      console.error('Error toggling feature:', error);
      toast.error('Failed to update version feature status');
    }
  };

  // Handle note changes and set hasChanges to true
  const handleNoteChange = (note: string) => {
    setVersionNote(note);
    
    // Set hasChanges to true when note is changed
    setHasChanges(true);
  };

  const handleSave = async () => {
    try {
      // Signal to DetailContent to reset editing state
      setResetEditingCounter(prev => prev + 1)
      
      // Update the Score record with the new values
      await client.graphql({
        query: `
          mutation UpdateScore($input: UpdateScoreInput!) {
            updateScore(input: $input) {
              id
              name
              externalId
              key
            }
          }
        `,
        variables: {
          input: {
            id: String(score.id),
            name: editedScore.name,
            externalId: editedScore.externalId,
            key: editedScore.key,
          }
        }
      });

      // Check if we're editing an existing version or creating a new one
      const isEditingExistingVersion = selectedVersionId && versions.some(v => v.id === selectedVersionId);
      
      // Create a new version with the current configuration
      let configurationYaml = editedScore.configuration;
      
      // If no configuration exists, create one based on current values
      if (!configurationYaml) {
        // Check if we should use external_id or externalId format
        // Default to external_id for new configurations as it's more standard
        configurationYaml = stringifyYaml({
          name: editedScore.name,
          external_id: editedScore.externalId,
          key: editedScore.key,
          description: editedScore.description
        });
      } else {
        // Ensure the configuration has the latest values
        try {
          const parsed = parseYaml(configurationYaml);
          
          // Determine which format to use for external ID by examining the parsed object
          const hasExternalId = 'externalId' in parsed;
          const hasExternalUnderscoreId = 'external_id' in parsed;
          const hasSimpleId = 'id' in parsed && !hasExternalId && !hasExternalUnderscoreId;

          
          // Update the external ID field using the same format that was in the original YAML
          if (hasSimpleId) {
            // Using simple id format
            parsed.id = editedScore.externalId;
          } else if (hasExternalUnderscoreId) {
            // Using snake_case format
            parsed.external_id = editedScore.externalId;
          } else {
            // Using camelCase format (default)
            parsed.externalId = editedScore.externalId;
          }
          
          // Update other fields
          parsed.name = editedScore.name;
          parsed.key = editedScore.key;
          if (editedScore.description) parsed.description = editedScore.description;
          
          // Update the configuration
          configurationYaml = stringifyYaml(parsed);
        } catch (error) {
          console.error('Error updating configuration YAML:', error);
        }
      }

      
      const versionPayload = {
        scoreId: String(score.id),
        configuration: configurationYaml,
        isFeatured: false,
        note: versionNote || 'Updated score configuration',
      };

      const createVersionResponse = await client.graphql({
        query: `
          mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
            createScoreVersion(input: $input) {
              id
              scoreId
              configuration
              isFeatured
              note
              createdAt
              updatedAt
            }
          }
        `,
        variables: {
          input: versionPayload
        }
      }) as GraphQLResult<CreateScoreVersionResponse>;
      
      const newVersion = 'data' in createVersionResponse && createVersionResponse.data?.createScoreVersion;
      
      // Update local state with the new version
      if (newVersion) {
        const placeholderVersion = {
          ...newVersion,
          user: {
            name: "Ryan Porter",
            avatar: "/user-avatar.png",
            initials: "RP"
          }
        };
        setVersions(prev => [placeholderVersion, ...prev]);
        setSelectedVersionId(placeholderVersion.id);
        
        // Only set as champion if there isn't already a champion version
        // AND this is the very first version ever created for this score
        if (!championVersionId && versions.length === 0) {
          setChampionVersionId(placeholderVersion.id);
          
          // Update the Score record to set this as the champion version
          try {
            await client.graphql({
              query: `
                mutation UpdateScoreChampion($input: UpdateScoreInput!) {
                  updateScore(input: $input) {
                    id
                    championVersionId
                  }
                }
              `,
              variables: {
                input: {
                  id: String(score.id),
                  championVersionId: String(placeholderVersion.id),
                }
              }
            });
            
            toast.success('New version created and set as champion (first version ever)');
          } catch (error) {
            console.error('Error updating champion version:', error);
            toast.error('Created version but failed to set as champion');
          }
        } else {
          toast.success('New version created successfully');
        }
      }
      
      setHasChanges(false);
      setVersionNote('');
      setForceExpandHistory(true); // Auto-expand version history after save
    } catch (error) {
      console.error('Error saving score:', error);
      toast.error(error instanceof Error ? error.message : 'Error updating score');
    }
  };

  const handlePromoteToChampion = async (versionId: string) => {
    try {
      const version = versions.find(v => v.id === versionId);
      if (!version) return;

      // Update the Score record to set this as the champion version
      await client.graphql({
        query: `
          mutation UpdateScoreChampion($input: UpdateScoreInput!) {
            updateScore(input: $input) {
              id
              championVersionId
            }
          }
        `,
        variables: {
          input: {
            id: String(score.id),
            championVersionId: String(versionId),
          }
        }
      });

      // Update local state
      setChampionVersionId(versionId);
      
      // If this version is not already selected, select it
      if (selectedVersionId !== versionId) {
        handleVersionSelect(version);
      }

      toast.success('Version promoted to champion');
    } catch (error) {
      console.error('Error promoting version to champion:', error);
      toast.error('Failed to promote version to champion');
    }
  };

  return (
    <div
      className={cn(
        "w-full rounded-lg text-card-foreground hover:bg-accent/50 transition-colors",
        variant === 'grid' ? (
          isSelected ? "bg-card-selected" : "bg-card"
        ) : "bg-card-selected",
        variant === 'detail' && "h-full flex flex-col overflow-hidden",
        className
      )}
      {...props}
    >
      <div className={cn(
        "p-4 w-full",
        variant === 'detail' && "flex-1 flex flex-col min-h-0 overflow-hidden"
      )}>
        <div 
          className={cn(
            "w-full",
            variant === 'grid' && "cursor-pointer",
            variant === 'detail' && "h-full flex flex-col min-h-0"
          )}
          onClick={() => variant === 'grid' && onClick?.()}
          role={variant === 'grid' ? "button" : undefined}
          tabIndex={variant === 'grid' ? 0 : undefined}
          onKeyDown={variant === 'grid' ? (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              onClick?.()
            }
          } : undefined}
        >
          {variant === 'grid' ? (
            <GridContent score={editedScore} isSelected={isSelected} />
          ) : (
            <DetailContent 
              score={editedScore}
              isFullWidth={isFullWidth}
              onToggleFullWidth={onToggleFullWidth}
              onClose={onClose}
              onEditChange={handleEditChange}
              onSave={onSave || handleSave}
              onCancel={handleCancel}
              hasChanges={hasChanges}
              versions={versions}
              championVersionId={championVersionId}
              selectedVersionId={selectedVersionId}
              onVersionSelect={handleVersionSelect}
              onToggleFeature={handleToggleFeature}
              onPromoteToChampion={handlePromoteToChampion}
              versionNote={versionNote}
              onNoteChange={handleNoteChange}
              resetEditingCounter={resetEditingCounter}
              forceExpandHistory={forceExpandHistory}
              exampleItems={exampleItems}
            />
          )}
        </div>
      </div>
    </div>
  )
} 