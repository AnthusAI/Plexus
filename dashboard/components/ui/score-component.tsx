import * as React from 'react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { MoreHorizontal, X, Square, Columns2, FileStack, ChevronDown, ChevronUp, ChevronRight, Award, FileCode, Minimize, Maximize, ArrowDownWideNarrow, Expand, Shrink, TestTube, FlaskConical, FlaskRound, TestTubes, ListCheck, MessageCircleMore, IdCard, Coins, Trash2, Crown, Clock, PanelLeftOpen, PanelLeftClose, Edit } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { CardButton } from '@/components/CardButton'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import * as Popover from '@radix-ui/react-popover'
import {
  DropdownMenu as ShadcnDropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { ScoreSidebarVersionHistory } from '@/components/ui/score-sidebar-version-history'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { generateClient } from 'aws-amplify/api'
import { toast } from 'sonner'

import type { GraphQLResult } from '@aws-amplify/api'
import Editor, { Monaco } from '@monaco-editor/react'
import * as monaco from 'monaco-editor'
import { parse as parseYaml, stringify as stringifyYaml } from 'yaml'
import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import type { editor } from 'monaco-editor'
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions, configureYamlLanguage, validateYamlIndentation } from '@/lib/monaco-theme'
import { useYamlLinter, useLintMessageHandler } from '@/hooks/use-yaml-linter'
import YamlLinterPanel from '@/components/ui/yaml-linter-panel'
import { TestScoreDialog } from '@/components/scorecards/test-score-dialog'
import { createTask } from '@/utils/data-operations'
import { useAccount } from '@/app/contexts/AccountContext'
import { GuidelinesEditor, FullscreenGuidelinesEditor } from '@/components/ui/guidelines-editor'
import { Timestamp } from "@/components/ui/timestamp"
import { ScoreHeaderInfo, type ScoreHeaderData } from '@/components/ui/score-header-info'

const client = generateClient();

export interface ScoreData {
  id: string
  name: string
  description: string
  guidelines?: string
  type: string
  order: number
  externalId?: string
  key?: string
  icon?: React.ReactNode
  configuration?: string // YAML configuration string
  championVersionId?: string // ID of the champion version
  isDisabled?: boolean // Whether the score is disabled
}

export interface ScoreVersion {
  id: string
  scoreId: string
  configuration: string // YAML string
  guidelines?: string
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
    description?: string
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
  onFeedbackAnalysis?: () => void
  onCostAnalysis?: () => void
  onDelete?: () => void
  exampleItems?: Array<{
    id: string
    displayValue: string
  }>
  scorecardName?: string
  onTaskCreated?: (task: any) => void
  initialSelectedVersionId?: string | null
  onVersionSelect?: (versionId: string) => void
}

interface DetailContentProps {
  score: ScoreData
  isFullWidth: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  onEditChange?: (changes: Partial<ScoreData>) => void
  onSave?: () => void
  onCancel?: () => void
  onFeedbackAnalysis?: () => void
  onCostAnalysis?: () => void
  onDelete?: () => void
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
  selectedAccount?: { id: string } | null
  scorecardName?: string
  onTaskCreated?: (task: any) => void
  // Guidelines editing props
  isGuidelinesExpanded?: boolean
  onToggleGuidelinesExpanded?: () => void
  isGuidelinesEditing?: boolean
  guidelinesEditValue?: string
  hasGuidelinesChanges?: boolean
  isSavingGuidelines?: boolean
  onStartInlineEdit?: () => void
  onOpenGuidelinesEditor?: () => void
  onGuidelinesChange?: (value: string) => void
  onSaveGuidelines?: () => void
  onCancelGuidelinesEdit?: () => void
}

const GridContent = React.memo(({ 
  score,
  isSelected 
}: { 
  score: ScoreData
  isSelected?: boolean
}) => {
  // Pre-compute all displayed values in a single operation before rendering
  // This ensures React renders them in the same cycle and prevents flickering
  // Use only the Score record data, never fetch additional data for grid view
  const displayData = React.useMemo(() => ({
    name: score.name,
    description: score.description || '',
    externalId: score.externalId || score.id
  }), [score.name, score.description, score.externalId, score.id]);
  
  return (
    <div className="flex justify-between items-start">
      <div className="space-y-1.5">
        <div className="font-medium">{displayData.name}</div>
        <div className="text-sm text-muted-foreground flex items-center gap-1">
          <IdCard className="h-3 w-3" />
          <span>{displayData.externalId}</span>
        </div>
        <div className="text-sm">{displayData.description}</div>
      </div>
      {score.icon && (
        <div className="flex flex-col items-center gap-1">
          <div className="text-muted-foreground">
            {score.icon}
          </div>
          <div className="text-xs text-muted-foreground text-center">Score</div>
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
  onFeedbackAnalysis,
  onCostAnalysis,
  onDelete,
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
  selectedAccount,
  scorecardName,
  onTaskCreated,
  // Guidelines editing props
  isGuidelinesExpanded = false,
  onToggleGuidelinesExpanded,
  isGuidelinesEditing = false,
  guidelinesEditValue = '',
  hasGuidelinesChanges = false,
  isSavingGuidelines = false,
  onStartInlineEdit,
  onOpenGuidelinesEditor,
  onGuidelinesChange,
  onSaveGuidelines,
  onCancelGuidelinesEdit,
}: DetailContentProps) => {
  // Get the current version's configuration
  const currentVersion = versions?.find(v => 
    v.id === (selectedVersionId || championVersionId)
  )
  
  // Parse YAML configuration if available, otherwise create default YAML
  const defaultYamlObj: Record<string, any> = {
    name: score.name
  };
  
  // Only add fields that have values to avoid "key: null" in YAML
  if (score.externalId && score.externalId !== '') {
    defaultYamlObj.externalId = score.externalId;
  }
  if (score.key && score.key !== '') {
    defaultYamlObj.key = score.key;
  }
  if (score.description && score.description !== '') {
    defaultYamlObj.description = score.description;
  }
  
  const defaultYaml = stringifyYaml(defaultYamlObj)
  
  // Track the current configuration in local state
  const [currentConfig, setCurrentConfig] = React.useState(currentVersion?.configuration || defaultYaml)
  
  // Track if we're currently editing to prevent useEffect from overriding changes
  const [isEditing, setIsEditing] = React.useState(false)
  
  // YAML Linting integration
  const { lintResult, setupMonacoIntegration, jumpToLine } = useYamlLinter({
    context: 'score',
    debounceMs: 500,
    showMonacoMarkers: true
  })
  const handleLintMessageClick = useLintMessageHandler(jumpToLine)
  

  
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
        externalId: externalIdValue,
        // Fall back to score's description if not present in version configuration
        description: parsed.description !== undefined ? parsed.description : score.description
      };
    } catch (error) {
      console.error('Error parsing YAML:', error)
      return { 
        name: score.name, 
        externalId: score.externalId,
        key: score.key,
        description: score.description
      }
    }
  }, [currentConfig, score])

  // Handle form field changes
  const handleFormChange = (field: string, value: string | boolean) => {
    
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
        // Only set the field if the value is not empty/null to avoid "key: null" in YAML
        if (value !== null && value !== undefined && value !== '') {
          parsed[field] = value;
        } else {
          // Remove the field entirely if it's empty/null
          delete parsed[field];
        }
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

  const handleTestScoreWithItem = async (itemId: string) => {
    console.log('Testing score with item:', { scoreId: score.id, scoreName: score.name, itemId });
    console.log('Account context:', { selectedAccount });
    
    try {
      const command = `predict --scorecard "${scorecardName || 'Unknown'}" --score "${score.name}" --item ${itemId}`;
      const taskInput = {
        type: 'Score Test',
        target: 'prediction',
        command: command,
        accountId: selectedAccount?.id || 'call-criteria',
        dispatchStatus: 'PENDING',
        status: 'PENDING'
      };
      
      console.log('Creating task with input:', taskInput);
      
      const task = await createTask(taskInput);
      
      console.log('Task creation result:', task);
      
      if (task) {
        toast.success("Score test dispatched", {
          description: <span className="font-mono text-sm truncate block">{command}</span>
        });
        
        // Notify parent component about task creation
        onTaskCreated?.(task);
      } else {
        console.error("createTask returned null or undefined");
        toast.error("Failed to dispatch score test - no task returned");
      }
    } catch (error) {
      console.error("Error dispatching score test:", error);
      toast.error(`Error dispatching score test: ${error}`);
    }
  };

  const closeTestScoreDialog = () => {
    setIsTestDialogOpen(false);
  };

  const handleEvaluateAccuracy = async () => {
    try {
      const command = `evaluate accuracy --score-id ${score.id}`;
      const task = await createTask({
        type: 'Accuracy Evaluation',
        target: 'evaluation',
        command: command,
        accountId: selectedAccount?.id || 'call-criteria',
        dispatchStatus: 'PENDING',
        status: 'PENDING'
      });
      
      if (task) {
        toast.success("Accuracy evaluation dispatched", {
          description: <span className="font-mono text-sm truncate block">{command}</span>
        });
      } else {
        toast.error("Failed to dispatch accuracy evaluation");
      }
    } catch (error) {
      console.error("Error dispatching accuracy evaluation:", error);
      toast.error("Error dispatching accuracy evaluation");
    }
  };

  const handleEvaluateConsistency = async () => {
    try {
      const command = `evaluate consistency --score-id ${score.id}`;
      const task = await createTask({
        type: 'Consistency Evaluation',
        target: 'evaluation',
        command: command,
        accountId: selectedAccount?.id || 'call-criteria',
        dispatchStatus: 'PENDING',
        status: 'PENDING'
      });
      
      if (task) {
        toast.success("Consistency evaluation dispatched", {
          description: <span className="font-mono text-sm truncate block">{command}</span>
        });
      } else {
        toast.error("Failed to dispatch consistency evaluation");
      }
    } catch (error) {
      console.error("Error dispatching consistency evaluation:", error);
      toast.error("Error dispatching consistency evaluation");
    }
  };

  const handleEvaluateAlignment = async () => {
    try {
      const command = `evaluate alignment --score-id ${score.id}`;
      const task = await createTask({
        type: 'Alignment Evaluation',
        target: 'evaluation',
        command: command,
        accountId: selectedAccount?.id || 'call-criteria',
        dispatchStatus: 'PENDING',
        status: 'PENDING'
      });
      
      if (task) {
        toast.success("Alignment evaluation dispatched", {
          description: <span className="font-mono text-sm truncate block">{command}</span>
        });
      } else {
        toast.error("Failed to dispatch alignment evaluation");
      }
    } catch (error) {
      console.error("Error dispatching alignment evaluation:", error);
      toast.error("Error dispatching alignment evaluation");
    }
  };



  // Add sidebar state
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState<'guidelines' | 'code'>('guidelines')
  const [isGuidelinesInlineEdit, setIsGuidelinesInlineEdit] = React.useState(false)
  const [fullscreenActiveTab, setFullscreenActiveTab] = React.useState<'guidelines' | 'code'>('guidelines')
  const [newVersionNote, setNewVersionNote] = React.useState('')

  // Sort versions by creation date (newest first)
  const sortedVersions = React.useMemo(() => {
    if (!versions) return []
    return [...versions].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  }, [versions])

  // Find champion version
  const championVersion = React.useMemo(() => {
    if (!versions) return undefined
    return versions.find(v => v.id === championVersionId)
  }, [versions, championVersionId])

  // Get currently selected version or champion
  const selectedVersion = React.useMemo(() => {
    if (!versions) return undefined
    if (selectedVersionId) {
      return versions.find(v => v.id === selectedVersionId)
    }
    return championVersion
  }, [selectedVersionId, championVersion, versions])



  // Guidelines handlers (moved up for sidebar use)
  const handleStartInlineEdit = () => {
    onStartInlineEdit?.()
  }

  const handleOpenGuidelinesEditor = () => {
    onOpenGuidelinesEditor?.()
  }

  return (
    <div className={cn(
      "w-full h-full flex flex-col",
      isEditorFullscreen && "absolute inset-0 z-10 bg-background p-4 rounded-lg"
    )}>
      {/* Description Section - Above sidebar, not versioned */}
      {!isEditorFullscreen && (
        <div className="border-border">
          <div className="space-y-3 mb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ListCheck className="h-5 w-5 text-foreground" />
                <span className="text-lg font-semibold">Score</span>
              </div>
              <div className="flex gap-2">
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
                    <DropdownMenuItem onClick={handleEvaluateAccuracy}>
                      <FlaskConical className="mr-2 h-4 w-4" />
                      Evaluate Accuracy
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={handleEvaluateConsistency}>
                      <FlaskRound className="mr-2 h-4 w-4" />
                      Evaluate Consistency
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={handleEvaluateAlignment}>
                      <TestTubes className="mr-2 h-4 w-4" />
                      Evaluate Alignment
                    </DropdownMenuItem>
                    {onFeedbackAnalysis && (
                      <DropdownMenuItem onClick={onFeedbackAnalysis}>
                        <MessageCircleMore className="mr-2 h-4 w-4" />
                        Analyze Feedback
                      </DropdownMenuItem>
                    )}
                    {onCostAnalysis && (
                      <DropdownMenuItem onClick={onCostAnalysis}>
                        <Coins className="mr-2 h-4 w-4" />
                        Analyze Cost
                      </DropdownMenuItem>
                    )}
                    {onDelete && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem 
                          onClick={onDelete}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete Score
                        </DropdownMenuItem>
                      </>
                    )}
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
            <ScoreHeaderInfo
              data={{
                name: parsedConfig.name || '',
                description: parsedConfig.description || '',
                key: parsedConfig.key || '',
                externalId: parsedConfig.externalId || ''
              }}
              onChange={(changes: Partial<ScoreHeaderData>) => {
                setIsEditing(true);
                Object.entries(changes).forEach(([field, value]) => {
                  handleFormChange(field, value);
                });
              }}
              namePlaceholder="Score name"
              descriptionPlaceholder="No description"
              keyPlaceholder="score-key"
              externalIdPlaceholder="External ID"
            />
          </div>
        </div>
      )}

      {/* Main Layout - Sidebar + Content */}
      {!isEditorFullscreen && (
        <div className="flex flex-1 min-h-0 bg-background rounded-lg overflow-hidden">
          {/* Left Sidebar - Version History */}
          <ScoreSidebarVersionHistory
            versions={versions}
            championVersionId={championVersionId}
            selectedVersionId={selectedVersionId}
            onVersionSelect={onVersionSelect}
            isSidebarCollapsed={isSidebarCollapsed}
            onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          />

          {/* Main Content - Versioned Content */}
          <div className="flex-1 flex flex-col">
            {/* Version Header */}
            {selectedVersion && (
              <div className="p-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-medium text-sm">
                        {selectedVersion.id === championVersionId ? 'Champion Version' : 'Version'}
                      </h3>
                      {selectedVersion.id === championVersionId && (
                        <Crown className="h-4 w-4 text-muted-foreground" />
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground mb-2">
                      <Timestamp time={selectedVersion.createdAt} variant="relative" className="text-xs" />
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {selectedVersion.note || 'No note'}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-3">
                    {selectedVersion.id !== championVersionId && onPromoteToChampion && (
                      <ShadcnDropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                            aria-label="Version actions"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => onPromoteToChampion(selectedVersion.id)}>
                            <Crown className="mr-2 h-4 w-4" />
                            Promote
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </ShadcnDropdownMenu>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Tabbed Content */}
            <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
              <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'guidelines' | 'code')} className="flex-1 flex flex-col min-h-0">
                <div className="flex items-center justify-between border-b border-border">
                  <TabsList className="h-auto p-0 bg-transparent justify-start">
                    <TabsTrigger value="guidelines" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-4 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Guidelines</TabsTrigger>
                    <TabsTrigger value="code" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-4 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Code</TabsTrigger>
                  </TabsList>
                  <div className="flex gap-1 pr-3">
                    <CardButton
                      icon={Expand}
                      onClick={() => {
                        setFullscreenActiveTab(activeTab)
                        setIsEditorFullscreen(true)
                      }}
                      aria-label="Open fullscreen editor"
                    />
                  </div>
                </div>
                
                <TabsContent value="guidelines" className="flex-1 bg-background mt-0 data-[state=inactive]:hidden min-h-0 flex flex-col">
                  {isGuidelinesInlineEdit ? (
                    <Editor
                      height="100%"
                      defaultLanguage="markdown"
                      value={guidelinesEditValue || selectedVersion?.guidelines || score.guidelines || ''}
                      onChange={(value) => {
                        onGuidelinesChange?.(value || '')
                      }}
                      onMount={(editor, monaco) => {
                        defineCustomMonacoThemes(monaco)
                        applyMonacoTheme(monaco)
                        setupMonacoThemeWatcher(monaco)
                        
                        // Add click outside handler
                        const handleClickOutside = (e: MouseEvent) => {
                          const editorElement = editor.getDomNode()
                          if (editorElement && !editorElement.contains(e.target as Node)) {
                            setIsGuidelinesInlineEdit(false)
                            // Only exit edit mode, don't save a new version
                            // The changes are already stored in guidelinesEditValue via onGuidelinesChange
                          }
                        }
                        
                        // Add the event listener after a short delay to avoid immediate triggering
                        setTimeout(() => {
                          document.addEventListener('mousedown', handleClickOutside)
                        }, 100)
                        
                        // Cleanup function
                        return () => {
                          document.removeEventListener('mousedown', handleClickOutside)
                        }
                      }}
                      options={{
                        ...getCommonMonacoOptions(),
                        wordWrap: 'on',
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 14,
                        tabSize: 2,
                        insertSpaces: true,
                        automaticLayout: true,
                      }}
                    />
                  ) : (
                    <div 
                      className="flex-1 p-4 overflow-y-auto cursor-text hover:bg-muted/30 transition-colors"
                      onClick={() => {
                        setIsGuidelinesInlineEdit(true)
                        handleStartInlineEdit?.()
                      }}
                    >
                      <div className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
                        {(() => {
                          // Show edited content if there are unsaved changes, otherwise show original content
                          const contentToShow = hasGuidelinesChanges 
                            ? guidelinesEditValue 
                            : (selectedVersion?.guidelines || score.guidelines || '');
                          
                          return contentToShow ? (
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm, remarkBreaks]}
                              components={{
                                p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
                                ul: ({ children }) => <ul className="mb-3 ml-4 list-disc">{children}</ul>,
                                ol: ({ children }) => <ol className="mb-3 ml-4 list-decimal">{children}</ol>,
                                li: ({ children }) => <li className="mb-1">{children}</li>,
                                strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                                em: ({ children }) => <em className="italic">{children}</em>,
                                code: ({ children }) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                                pre: ({ children }) => <pre className="bg-muted p-3 rounded overflow-x-auto text-sm">{children}</pre>,
                                h1: ({ children }) => <h1 className="text-lg font-semibold mb-3 text-foreground">{children}</h1>,
                                h2: ({ children }) => <h2 className="text-base font-semibold mb-2 text-foreground">{children}</h2>,
                                h3: ({ children }) => <h3 className="text-sm font-medium mb-2 text-foreground">{children}</h3>,
                                blockquote: ({ children }) => <blockquote className="border-l-4 border-muted-foreground/20 pl-4 italic text-muted-foreground">{children}</blockquote>,
                              }}
                            >
                              {contentToShow}
                            </ReactMarkdown>
                          ) : (
                            <div className="text-muted-foreground italic">
                              Click to add guidelines...
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                  )}
                </TabsContent>
                
                <TabsContent value="code" className="flex-1 bg-background mt-0 data-[state=inactive]:hidden">
                  <div className="flex flex-col h-full">
                    {/* Code Editor */}
                    <div className="flex-1 min-h-0">
                      <Editor
                        height="100%"
                        defaultLanguage="yaml"
                        value={score.configuration || ''}
                        onChange={(value) => {
                          // For direct YAML editing, bypass the complex form field logic
                          // and just update the configuration directly
                          setIsEditing(true);
                          onEditChange?.({ configuration: value || '' });
                        }}
                        onMount={(editor, monaco) => {
                          defineCustomMonacoThemes(monaco)
                          applyMonacoTheme(monaco)
                          setupMonacoThemeWatcher(monaco)
                          configureYamlLanguage(monaco)
                          setupMonacoIntegration(editor, monaco)
                        }}
                        options={{
                          ...getCommonMonacoOptions(),
                          wordWrap: 'on',
                          minimap: { enabled: false },
                          scrollBeyondLastLine: false,
                          fontSize: 14,
                          tabSize: 2,
                          insertSpaces: true,
                          automaticLayout: true,
                        }}
                      />
                    </div>
                    {/* Validation Panel underneath */}
                    <div className="border-t border-border bg-background p-3 min-h-[200px]">
                      <YamlLinterPanel 
                        result={lintResult || undefined}
                        onMessageClick={handleLintMessageClick}
                      />
                    </div>
                  </div>
                </TabsContent>
              </Tabs>
            </div>
          </div>
        </div>
      )}

      {/* Fullscreen Editor Mode */}
      {isEditorFullscreen && (
        <div className="flex flex-col h-full w-full">
          {/* Fullscreen Tabs */}
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <Tabs value={fullscreenActiveTab} onValueChange={(value) => setFullscreenActiveTab(value as 'guidelines' | 'code')} className="flex-1 flex flex-col min-h-0">
              <div className="flex items-center justify-between border-b border-border">
                <TabsList className="h-auto p-0 bg-transparent justify-start">
                  <TabsTrigger value="guidelines" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Guidelines</TabsTrigger>
                  <TabsTrigger value="code" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Code</TabsTrigger>
                </TabsList>
                <div className="flex gap-2">
                  <CardButton
                    icon={X}
                    onClick={() => setIsEditorFullscreen(false)}
                    aria-label="Close fullscreen"
                  />
                </div>
              </div>
              
              {/* Guidelines Tab - 50/50 split */}
              <TabsContent value="guidelines" className="flex-1 mt-0 data-[state=inactive]:hidden min-h-0">
                <div className="flex h-full">
                  {/* Left: Markdown Editor */}
                  <div className="w-1/2 border-r border-border">
                    <Editor
                      height="100%"
                      defaultLanguage="markdown"
                      value={guidelinesEditValue || selectedVersion?.guidelines || score.guidelines || ''}
                      onChange={(value) => {
                        onGuidelinesChange?.(value || '')
                      }}
                      onMount={(editor, monaco) => {
                        defineCustomMonacoThemes(monaco)
                        applyMonacoTheme(monaco)
                        setupMonacoThemeWatcher(monaco)
                      }}
                      options={{
                        ...getCommonMonacoOptions(),
                        wordWrap: 'on',
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 14,
                        tabSize: 2,
                        insertSpaces: true,
                        automaticLayout: true,
                      }}
                    />
                  </div>
                  {/* Right: Preview */}
                  <div className="w-1/2 p-4 overflow-y-auto bg-background">
                    <div className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
                      {(guidelinesEditValue || selectedVersion?.guidelines || score.guidelines) ? (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkBreaks]}
                          components={{
                            p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
                            ul: ({ children }) => <ul className="mb-3 ml-4 list-disc">{children}</ul>,
                            ol: ({ children }) => <ol className="mb-3 ml-4 list-decimal">{children}</ol>,
                            li: ({ children }) => <li className="mb-1">{children}</li>,
                            strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                            em: ({ children }) => <em className="italic">{children}</em>,
                            code: ({ children }) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                            pre: ({ children }) => <pre className="bg-muted p-3 rounded overflow-x-auto text-sm">{children}</pre>,
                            h1: ({ children }) => <h1 className="text-lg font-semibold mb-3 text-foreground">{children}</h1>,
                            h2: ({ children }) => <h2 className="text-base font-semibold mb-2 text-foreground">{children}</h2>,
                            h3: ({ children }) => <h3 className="text-sm font-medium mb-2 text-foreground">{children}</h3>,
                            blockquote: ({ children }) => <blockquote className="border-l-4 border-muted-foreground/20 pl-4 italic text-muted-foreground">{children}</blockquote>,
                          }}
                        >
                          {guidelinesEditValue || selectedVersion?.guidelines || score.guidelines || ''}
                        </ReactMarkdown>
                      ) : (
                        <div className="text-muted-foreground italic">
                          No guidelines yet. Start typing in the editor to add guidelines.
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </TabsContent>
              
              {/* Code Tab - 2/3 + 1/3 split */}
              <TabsContent value="code" className="flex-1 mt-0 data-[state=inactive]:hidden min-h-0">
                <div className="flex h-full">
                  {/* Left: YAML Editor (2/3) */}
                  <div className="w-2/3 border-r border-border">
                    <Editor
                      height="100%"
                      defaultLanguage="yaml"
                      value={score.configuration || ''}
                      onChange={(value) => {
                        // For direct YAML editing, bypass the complex form field logic
                        // and just update the configuration directly
                        setIsEditing(true);
                        onEditChange?.({ configuration: value || '' });
                      }}
                      onMount={(editor, monaco) => {
                        defineCustomMonacoThemes(monaco)
                        applyMonacoTheme(monaco)
                        setupMonacoThemeWatcher(monaco)
                        configureYamlLanguage(monaco)
                        setupMonacoIntegration(editor, monaco)
                      }}
                      options={{
                        ...getCommonMonacoOptions(),
                        wordWrap: 'on',
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 14,
                        tabSize: 2,
                        insertSpaces: true,
                        automaticLayout: true,
                      }}
                    />
                  </div>
                  {/* Right: Validation Panel (1/3) */}
                  <div className="w-1/3 bg-background p-3 overflow-y-auto">
                    <YamlLinterPanel 
                      result={lintResult || undefined}
                      onMessageClick={handleLintMessageClick}
                    />
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </div>
          
          {/* Save/Cancel buttons - only show when there are changes */}
          {(hasChanges || hasGuidelinesChanges) && (
            <div className="flex items-center gap-3 p-4 bg-background">
              <Button
                variant="secondary"
                onClick={() => {
                  setNewVersionNote('')
                  setIsEditorFullscreen(false)
                }}
                disabled={isSavingGuidelines}
                className="h-10"
              >
                Cancel
              </Button>
              <textarea
                value={newVersionNote}
                onChange={(e) => {
                  setNewVersionNote(e.target.value)
                  onNoteChange?.(e.target.value)
                }}
                placeholder="Please say what you changed and why..."
                className="flex-1 px-3 py-2 rounded-md bg-background text-sm resize-none h-10 border border-muted
                         placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                rows={1}
              />
              <Button
                variant="default"
                onClick={() => hasGuidelinesChanges ? onSaveGuidelines?.() : onSave?.()}
                disabled={isSavingGuidelines}
                className="h-10"
              >
                {isSavingGuidelines ? 'Saving...' : 'Save'}
              </Button>
            </div>
          )}
        </div>
      )}



      {/* Unified Save/Cancel Bar - appears when there are changes */}
      {(hasChanges || hasGuidelinesChanges) && !isEditorFullscreen && (
        <div className="mt-3">
          <div className="flex items-center gap-3 bg-muted/50 rounded-lg p-3">
            <Button
              variant="secondary"
              onClick={() => {
                setNewVersionNote('')
                onCancel?.()
              }}
              className="shrink-0 h-10"
            >
              Cancel
            </Button>
            <input
              type="text"
              value={newVersionNote}
              onChange={(e) => {
                setNewVersionNote(e.target.value)
                onNoteChange(e.target.value)
              }}
              placeholder="Please say what you changed and why..."
              className="flex-1 px-3 py-2 rounded-md bg-background text-sm h-10
                       placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button
              variant="default"
              onClick={() => hasGuidelinesChanges ? onSaveGuidelines?.() : onSave?.()}
              className="shrink-0 h-10"
            >
              Save Changes
            </Button>
          </div>
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
  onFeedbackAnalysis,
  onCostAnalysis,
  onDelete,
  exampleItems = [],
  scorecardName,
  onTaskCreated,
  initialSelectedVersionId,
  onVersionSelect,
  className,
  ...props
}: ScoreComponentProps) {
  const { selectedAccount } = useAccount();
  const [editedScore, setEditedScore] = React.useState<ScoreData>(score)
  const [hasChanges, setHasChanges] = React.useState(false)
  const [versions, setVersions] = React.useState<ScoreVersion[]>([])
  const [championVersionId, setChampionVersionId] = React.useState<string>()
  const [selectedVersionId, setSelectedVersionId] = React.useState<string | undefined>(initialSelectedVersionId || undefined)
  const [versionNote, setVersionNote] = React.useState('')
  const [resetEditingCounter, setResetEditingCounter] = React.useState(0)
  const [forceExpandHistory, setForceExpandHistory] = React.useState(false)
  const [isGuidelinesExpanded, setIsGuidelinesExpanded] = React.useState(false)
  const [isGuidelinesEditing, setIsGuidelinesEditing] = React.useState(false)
  const [isGuidelinesFullscreen, setIsGuidelinesFullscreen] = React.useState(false)
  const [guidelinesEditValue, setGuidelinesEditValue] = React.useState('')
  const [hasGuidelinesChanges, setHasGuidelinesChanges] = React.useState(false)
  const [isSavingGuidelines, setIsSavingGuidelines] = React.useState(false)

  // Version selection handler
  const handleVersionSelect = (version: ScoreVersion) => {
    console.log('🔍 Loading version:', version.id, 'Guidelines:', version.guidelines)
    setSelectedVersionId(version.id)
    setVersionNote(version.note || '')
    
    // Call parent's version select handler to update URL
    onVersionSelect?.(version.id)
    
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

      
      // Update the editedScore with values from the YAML configuration and version record
      // YAML is source of truth for most fields, but guidelines come from ScoreVersion.guidelines
      setEditedScore(prev => {
        const updated = {
          ...prev,
          // Use values from YAML, falling back to previous values if not present
          name: config.name !== undefined ? config.name : prev.name,
          // Support all three formats for external ID
          externalId: externalIdValue !== undefined ? String(externalIdValue) : prev.externalId,
          key: config.key !== undefined ? config.key : prev.key,
          description: config.description !== undefined ? config.description : prev.description,
          // Guidelines come from ScoreVersion.guidelines, not from YAML
          guidelines: version.guidelines !== undefined ? version.guidelines : prev.guidelines,
          // Store the complete configuration for the editor
          configuration: version.configuration
        };
        console.log('🔧 Setting editedScore guidelines to:', updated.guidelines)
        return updated;
      })
      
      // Reset hasChanges since we just loaded a version
      setHasChanges(false);
      
      // Reset guidelines editing state when switching versions
      setHasGuidelinesChanges(false);
      setIsGuidelinesEditing(false);
      setGuidelinesEditValue(version.guidelines || '');
      
      // Remove toast notification for simply viewing a version
      // We only want notifications for actions that change state
    } catch (error) {
      console.error('Error parsing version YAML:', error)
      toast.error('Error loading version configuration')
    }
  }
  
  // Ensure editedScore is updated when score prop changes
  React.useEffect(() => {
    setEditedScore(score)
    setVersionNote('') // Reset note when score changes
    setHasChanges(false) // Reset changes flag when score changes
    setResetEditingCounter(prev => prev + 1) // Signal to DetailContent to reset editing state
    setForceExpandHistory(false) // Reset expansion when score changes
  }, [score])
  
  // Fetch versions when score changes - ONLY for detail view
  React.useEffect(() => {
    // Skip version fetching for grid view to prevent flickering
    if (variant === 'grid') {
      return;
    }
    
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
                description
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
          
          // Update the editedScore with the fetched description
          setEditedScore(prev => ({
            ...prev,
            description: scoreData.description || prev.description
          }));
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
                  guidelines
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
        
        if ('errors' in response && response.errors) {
          console.error('🚨 GraphQL errors loading versions:', response.errors);
        }
        
        if ('data' in response && response.data?.listScoreVersionByScoreIdAndCreatedAt?.items) {
          const versionItems = response.data.listScoreVersionByScoreIdAndCreatedAt.items;
          console.log('🔍 Loaded versions:', versionItems.map(v => ({ id: v.id, guidelines: v.guidelines })));
          setVersions(versionItems);
          
          // Sort versions by createdAt in descending order
          const sortedVersions = [...versionItems].sort(
            (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          );
          
          // Find champion version or use the most recent one if no champion exists
          const champion = championId 
            ? versionItems.find(v => v.id === championId) 
            : null;
            
          // Priority order for version selection:
          // 1. initialSelectedVersionId (from deep link)
          // 2. champion version
          // 3. most recent version
          
          if (initialSelectedVersionId) {
            // Try to select the version specified in the URL
            const initialVersion = versionItems.find(v => v.id === initialSelectedVersionId);
            if (initialVersion) {
              console.log('🔗 Deep link: Selecting initial version:', initialVersion.id);
              handleVersionSelect(initialVersion);
            } else {
              console.warn('⚠️ Deep link: Initial version not found, falling back to champion');
              // Fallback to champion if initial version not found
              if (champion) {
                handleVersionSelect(champion);
              } else if (sortedVersions.length > 0) {
                handleVersionSelect(sortedVersions[0]);
              }
            }
          } else if (champion) {
            // No deep link, select champion version
            console.log('👑 Selecting champion version:', champion.id);
            handleVersionSelect(champion);
          } else if (sortedVersions.length > 0) {
            // No champion, select most recent version
            console.log('📅 Selecting most recent version:', sortedVersions[0].id);
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
  }, [score, variant, initialSelectedVersionId])





  const handleSaveGuidelines = async () => {
    if (isSavingGuidelines) return
    
    try {
      setIsSavingGuidelines(true)
      
      // Debug: Check what we actually have
      console.log('🔍 handleSaveGuidelines - guidelinesEditValue type:', typeof guidelinesEditValue)
      console.log('🔍 handleSaveGuidelines - guidelinesEditValue value:', guidelinesEditValue)
      
      // This should always be a string - if it's not, we have a bug to fix
      if (typeof guidelinesEditValue !== 'string') {
        console.error('❌ BUG: guidelinesEditValue is not a string!', guidelinesEditValue)
        throw new Error(`guidelinesEditValue should be a string, got ${typeof guidelinesEditValue}`)
      }
      
      // Update the score guidelines
      handleEditChange({ guidelines: guidelinesEditValue })
      setIsGuidelinesEditing(false)
      setIsGuidelinesFullscreen(false)
      setHasGuidelinesChanges(false)
      
      // Call the internal handleSave with the current guidelines value
      await handleSave(guidelinesEditValue)
      toast.success('Guidelines saved successfully')
    } catch (error) {
      console.error('Error saving guidelines:', error)
      toast.error('Failed to save guidelines')
    } finally {
      setIsSavingGuidelines(false)
    }
  }

  const handleCancelGuidelinesEdit = () => {
    // Reset to the original content for the selected version
    const currentVersion = selectedVersionId ? versions.find(v => v.id === selectedVersionId) : undefined;
    const originalContent = currentVersion?.guidelines || editedScore.guidelines || '';
    setGuidelinesEditValue(originalContent)
    setHasGuidelinesChanges(false)
    setIsGuidelinesEditing(false)
    setIsGuidelinesFullscreen(false)
  }

  const handleGuidelinesChange = (value: string) => {
    console.log('🔍 handleGuidelinesChange called with type:', typeof value)
    console.log('🔍 handleGuidelinesChange called with value:', value)
    
    if (typeof value !== 'string') {
      console.error('❌ BUG: handleGuidelinesChange received non-string!', value)
      console.trace('Stack trace for non-string value')
      return // Don't set invalid value
    }
    
    setGuidelinesEditValue(value)
    setHasGuidelinesChanges(value !== (editedScore.guidelines || ''))
  }

  const handleEditChange = (changes: Partial<ScoreData>) => {
    
    // Always update the editedScore state with the changes
    setEditedScore(prev => {
      // Create updated state with the changes
      const updated = { ...prev, ...changes };
      
      // Mark that we have unsaved changes
      setHasChanges(true);
      
      // If we're changing fields other than the note, reset onlyNoteChanged flag
      if ('name' in changes || 'key' in changes || 'externalId' in changes || 
          'description' in changes || 'configuration' in changes || 'guidelines' in changes) {
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
          if (changes.name && changes.name !== '') {
            updatedConfig.name = changes.name;
          } else {
            delete updatedConfig.name;
          }
        }
        
        // Update key if changed
        if (changes.key !== undefined) {
          if (changes.key && changes.key !== '') {
            updatedConfig.key = changes.key;
          } else {
            delete updatedConfig.key;
          }
        }
        
        // Update description if changed
        if (changes.description !== undefined) {
          if (changes.description && changes.description !== '') {
            updatedConfig.description = changes.description;
          } else {
            delete updatedConfig.description;
          }
        }
        
        // Update external ID with the appropriate format
        if (changes.externalId !== undefined) {
          if (changes.externalId && changes.externalId !== '') {
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
          } else {
            // Remove all external ID fields if empty
            delete updatedConfig.externalId;
            delete updatedConfig.external_id;
            delete updatedConfig.id;
          }
        }
        
        // Update isDisabled if changed
        if (changes.isDisabled !== undefined) {
          if (changes.isDisabled) {
            updatedConfig.isDisabled = changes.isDisabled;
          } else {
            delete updatedConfig.isDisabled;
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
    setHasGuidelinesChanges(false) // Also reset guidelines changes
    setGuidelinesEditValue(editedScore.guidelines || '') // Reset guidelines to original value
    setIsGuidelinesEditing(false) // Exit guidelines editing mode
    setSelectedVersionId(undefined) // Reset selection to champion
    setResetEditingCounter(prev => prev + 1) // Signal to DetailContent to reset editing state
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

  const handleSave = async (overrideGuidelines?: string) => {
    try {
      console.log('ScoreComponent handleSave called for score:', score);
      console.log('editedScore data:', editedScore);
      console.log('versions array:', versions);
      console.log('championVersionId:', championVersionId);
      
      // Signal to DetailContent to reset editing state
      setResetEditingCounter(prev => prev + 1)
      
      // Update the Score record with the new values
      console.log('Updating Score record...');
      const updateResult = await client.graphql({
        query: `
          mutation UpdateScore($input: UpdateScoreInput!) {
            updateScore(input: $input) {
              id
              name
              externalId
              key
              description
            }
          }
        `,
        variables: {
          input: {
            id: String(score.id),
            name: editedScore.name,
            ...(editedScore.externalId && editedScore.externalId !== '' && { externalId: editedScore.externalId }),
            ...(editedScore.key && editedScore.key !== '' && { key: editedScore.key }),
            ...(editedScore.description && editedScore.description !== '' && { description: editedScore.description }),
          }
        }
      });
      
      console.log('Score record update result:', updateResult);

      // Check if we're editing an existing version or creating a new one
      const isEditingExistingVersion = selectedVersionId && versions.some(v => v.id === selectedVersionId);
      
      // Create a new version with the current configuration
      let configurationYaml = editedScore.configuration;
      
      // If no configuration exists, create one based on current values
      if (!configurationYaml) {
        // Check if we should use external_id or externalId format
        // Default to external_id for new configurations as it's more standard
        const newConfigObj: Record<string, any> = {
          name: editedScore.name
        };
        
        // Only add fields that have values to avoid "key: null" in YAML
        if (editedScore.externalId && editedScore.externalId !== '') {
          newConfigObj.external_id = editedScore.externalId;
        }
        if (editedScore.key && editedScore.key !== '') {
          newConfigObj.key = editedScore.key;
        }
        if (editedScore.description && editedScore.description !== '') {
          newConfigObj.description = editedScore.description;
        }
        if (editedScore.isDisabled) {
          newConfigObj.isDisabled = editedScore.isDisabled;
        }
        
        configurationYaml = stringifyYaml(newConfigObj);
      } else {
        // Ensure the configuration has the latest values
        try {
          const parsed = parseYaml(configurationYaml);
          
          // Determine which format to use for external ID by examining the parsed object
          const hasExternalId = 'externalId' in parsed;
          const hasExternalUnderscoreId = 'external_id' in parsed;
          const hasSimpleId = 'id' in parsed && !hasExternalId && !hasExternalUnderscoreId;

          
          // Update the external ID field using the same format that was in the original YAML
          if (editedScore.externalId && editedScore.externalId !== '') {
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
          } else {
            // Remove all external ID fields if empty
            delete parsed.id;
            delete parsed.external_id;
            delete parsed.externalId;
          }
          
          // Update other fields
          parsed.name = editedScore.name;
          
          // Only set key if it has a value
          if (editedScore.key && editedScore.key !== '') {
            parsed.key = editedScore.key;
          } else {
            delete parsed.key;
          }
          
          // Only set description if it has a value
          if (editedScore.description && editedScore.description !== '') {
            parsed.description = editedScore.description;
          } else {
            delete parsed.description;
          }
          
          // Handle isDisabled field
          if (editedScore.isDisabled) {
            parsed.isDisabled = editedScore.isDisabled;
          } else {
            delete parsed.isDisabled;
          }
          
          // Update the configuration
          configurationYaml = stringifyYaml(parsed);
        } catch (error) {
          console.error('Error updating configuration YAML:', error);
        }
      }

      
      const now = new Date().toISOString();
      const versionPayload = {
        scoreId: String(score.id),
        configuration: configurationYaml,
        guidelines: overrideGuidelines !== undefined ? overrideGuidelines : (editedScore.guidelines || ''),
        isFeatured: false,
        note: versionNote || 'Updated score configuration',
        createdAt: now,
        updatedAt: now
      };

      console.log('Creating ScoreVersion with payload:', versionPayload);
      console.log('🔍 Guidelines being saved:', overrideGuidelines !== undefined ? overrideGuidelines : (editedScore.guidelines || ''));
      const createVersionResponse = await client.graphql({
        query: `
          mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
            createScoreVersion(input: $input) {
              id
              scoreId
              configuration
              guidelines
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
      
      console.log('CreateScoreVersion response:', createVersionResponse);
      
      const newVersion = 'data' in createVersionResponse && createVersionResponse.data?.createScoreVersion;
      
      // Update local state with the new version
      console.log('🔍 Created newVersion with guidelines:', newVersion && 'guidelines' in newVersion ? newVersion.guidelines : 'N/A');
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
      
      // Call the parent's onSave callback if provided
      onSave?.();
    } catch (error) {
      console.error('Error saving score:', error);
      console.error('Full error details:', {
        message: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : 'No stack trace',
        fullError: error
      });
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
        "w-full rounded-lg text-card-foreground transition-colors",
        variant === 'grid' ? (
          isSelected ? "bg-card-selected" : "bg-card hover:bg-accent"
        ) : "bg-card-selected",
        variant === 'detail' && "h-full flex flex-col overflow-hidden",
        className
      )}
      style={{
        ...(isSelected && variant === 'grid' && {
          boxShadow: 'inset 0 0 0 0.5rem var(--secondary)'
        })
      }}
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
              onSave={handleSave}
              onCancel={handleCancel}
              onFeedbackAnalysis={onFeedbackAnalysis}
              onCostAnalysis={onCostAnalysis}
              onDelete={onDelete}
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
              selectedAccount={selectedAccount}
              scorecardName={scorecardName}
              onTaskCreated={onTaskCreated}
              // Guidelines editing props
              isGuidelinesExpanded={isGuidelinesExpanded}
              onToggleGuidelinesExpanded={() => setIsGuidelinesExpanded(!isGuidelinesExpanded)}
              isGuidelinesEditing={isGuidelinesEditing}
              guidelinesEditValue={guidelinesEditValue}
              hasGuidelinesChanges={hasGuidelinesChanges}
              isSavingGuidelines={isSavingGuidelines}
              onStartInlineEdit={() => {
                setIsGuidelinesEditing(true)
                // Use the current displayed content (either edited or original)
                const currentVersion = selectedVersionId ? versions.find(v => v.id === selectedVersionId) : undefined;
                const currentContent = hasGuidelinesChanges 
                  ? guidelinesEditValue 
                  : (currentVersion?.guidelines || editedScore.guidelines || '');
                setGuidelinesEditValue(currentContent)
              }}
              onOpenGuidelinesEditor={() => {
                setIsGuidelinesFullscreen(true)
                // Use the current displayed content (either edited or original)
                const currentVersion = selectedVersionId ? versions.find(v => v.id === selectedVersionId) : undefined;
                const currentContent = hasGuidelinesChanges 
                  ? guidelinesEditValue 
                  : (currentVersion?.guidelines || editedScore.guidelines || '');
                setGuidelinesEditValue(currentContent)
              }}
              onGuidelinesChange={handleGuidelinesChange}
              onSaveGuidelines={handleSaveGuidelines}
              onCancelGuidelinesEdit={handleCancelGuidelinesEdit}
            />
          )}
        </div>
      </div>

      {/* Fullscreen Guidelines Editor */}
      <FullscreenGuidelinesEditor
        isOpen={isGuidelinesFullscreen}
        title={`Guidelines - ${score.name}`}
        value={guidelinesEditValue}
        onChange={handleGuidelinesChange}
        onSave={handleSaveGuidelines}
        onCancel={handleCancelGuidelinesEdit}
        hasChanges={hasGuidelinesChanges}
        isSaving={isSavingGuidelines}
      />
    </div>
  )
} 