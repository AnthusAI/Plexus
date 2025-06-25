import * as React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { MoreHorizontal, X, Square, Columns2, StickyNote, Info, ChevronDown, ChevronUp, Loader2, Box, ListChecks, FileText, Tag } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Badge } from '@/components/ui/badge'
import { Timestamp } from '@/components/ui/timestamp'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import ItemScoreResultCard from './ItemScoreResultCard'
import { IdentifierDisplay } from '@/components/ui/identifier-display'
import NumberFlowWrapper from '@/components/ui/number-flow'
import ItemScoreResults from '../ItemScoreResults'
import { useItemScoreResults } from '@/hooks/useItemScoreResults'
import { useTranslations } from '@/app/contexts/TranslationContext'
import { MetadataEditor } from '@/components/ui/metadata-editor'
import { FileAttachments } from './FileAttachments'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

// Interface for scorecard results
interface ScorecardResult {
  scorecardId: string;
  scorecardName: string;
  resultCount: number;
}

// Interface for the new Identifier model structure
export interface IdentifierItem {
  name: string;
  value: string;
  url?: string;
  position?: number;
}

// Clean interface for ItemCard parameters
export interface ItemData {
  // Core required parameters
  id: number | string
  timestamp: string // ISO string for when the item was created/updated
  duration?: number // Duration in seconds (optional for elapsed time display)
  scorecards: ScorecardResult[] // List of scorecards with result counts
  
  // Optional UI fields
  icon?: React.ReactNode
  externalId?: string
  description?: string
  identifiers?: string | IdentifierItem[] // Support both JSON string (legacy) and new array format
  isNew?: boolean
  isLoadingResults?: boolean
  metadata?: Record<string, string> // Metadata object
  attachedFiles?: string[] // Array of file paths/URLs
  
  // Legacy fields for backwards compatibility (will be phased out)
  date?: string
  status?: string
  results?: number
  inferences?: number
  cost?: string
  accountId?: string
  scorecardId?: string
  scoreId?: string
  evaluationId?: string
  updatedAt?: string
  createdAt?: string
  isEvaluation?: boolean
  groupedScoreResults?: any
  scorecardBreakdown?: Array<{
    scorecardId: string;
    scorecardName: string;
    count: number;
  }>
  text?: string // For detail view text display
}

interface ItemCardProps extends React.HTMLAttributes<HTMLDivElement> {
  item: ItemData
  onEdit?: () => void
  onViewData?: () => void
  isSelected?: boolean
  onClick?: () => void
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  variant?: 'grid' | 'detail'
  getBadgeVariant: (status: string) => string
  skeletonMode?: boolean
  readOnly?: boolean // Add readOnly prop
  onSave?: (item: ItemData) => Promise<void> // Add onSave prop
  onScoreResultsRefetchReady?: (refetchFn: (() => void) | null) => void // Add callback for score results refetch
  naturalHeight?: boolean // Add naturalHeight prop for document flow vs height-filling behavior
  onScoreResultSelect?: (scoreResult: any) => void // Add score result selection callback
  selectedScoreResultId?: string // Add selected score result ID
}

const ItemCard = React.forwardRef<HTMLDivElement, ItemCardProps>(({ 
  item, 
  onEdit, 
  onViewData, 
  variant = 'grid', 
  isSelected,
  onClick,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  getBadgeVariant,
  skeletonMode = false,
  readOnly = false,
  onSave,
  onScoreResultsRefetchReady,
  naturalHeight = false,
  onScoreResultSelect,
  selectedScoreResultId,
  className, 
  ...props 
}, ref) => {
  const t = useTranslations('scorecards')
  const tItems = useTranslations('items')
  const [isNarrowViewport, setIsNarrowViewport] = React.useState(false)
  
  // Use the score results hook for detail view
  const { groupedResults, isLoading, error, refetch, silentRefetch } = useItemScoreResults(
    variant === 'detail' ? String(item.id) : null
  )

  // Extract HTML props that might conflict with motion props
  const { onDrag, ...htmlProps } = props as any;
  
  const totalResults = item.scorecards.reduce((sum, sc) => sum + sc.resultCount, 0);
  const hasMultipleScorecards = item.scorecards.length > 1;

  React.useEffect(() => {
    if (variant === 'detail') {
      const checkViewportWidth = () => {
        setIsNarrowViewport(window.innerWidth < 640)
      }

      checkViewportWidth()
      window.addEventListener('resize', checkViewportWidth)
      return () => window.removeEventListener('resize', checkViewportWidth)
    }
  }, [variant])

  // Pass the silent refetch function to the parent when it's available for detail view
  React.useEffect(() => {
    if (variant === 'detail' && onScoreResultsRefetchReady) {
      onScoreResultsRefetchReady(silentRefetch);
      
      // Clean up by passing null when component unmounts or variant changes
      return () => {
        onScoreResultsRefetchReady(null);
      };
    }
  }, [variant, silentRefetch, onScoreResultsRefetchReady])



  // Grid mode content
  const renderGridContent = () => (
    <div className="space-y-1 @[500px]:min-h-[150px] @[700px]:min-h-[150px] @[900px]:min-h-[150px] @[1100px]:min-h-[120px]">
      <IdentifierDisplay
        externalId={item.externalId}
        identifiers={item.identifiers}
        iconSize="md"
        textSize="xs"
        skeletonMode={skeletonMode}
        displayMode="compact"
      />

      <Timestamp 
        time={item.timestamp} 
        variant="relative" 
        showIcon={true} 
        className="text-xs"
        skeletonMode={skeletonMode}
      />

      {/* Elapsed time display between createdAt and updatedAt */}
      {item.createdAt && item.updatedAt && (
        <Timestamp 
          time={item.createdAt}
          completionTime={item.updatedAt}
          variant="elapsed" 
          showIcon={true}
          className="text-xs"
          skeletonMode={skeletonMode}
        />
      )}

      {/* Scorecard summary - only show if there are actually scorecards */}
      {item.scorecards.length > 0 && (
        <div className="flex items-baseline gap-1 font-semibold text-sm mt-3">
          <ListChecks className="h-4 w-4 flex-shrink-0 text-muted-foreground translate-y-0.5" />
          <span className="text-foreground">
            {hasMultipleScorecards ?
              `${item.scorecards.length} ${t('scorecards')}` :
              item.scorecards[0]?.scorecardName || t('scorecard')
            }
          </span>
        </div>
      )}

      {/* Results count - only show if there are actually scorecards */}
      {item.scorecards.length > 0 && (
        <div className="flex items-baseline gap-1 text-sm text-muted-foreground">
          <Box className="h-4 w-4 flex-shrink-0 translate-y-0.5" />
          <span>
            <span className="text-foreground"><NumberFlowWrapper value={totalResults} skeletonMode={skeletonMode || item.isLoadingResults} /></span> {t(totalResults === 1 ? 'scoreResults' : 'scoreResults')}
          </span>
        </div>
      )}
    </div>
  )

  // Grid mode layout
  if (variant === 'grid') {
    return (
      <motion.div
        ref={ref}
        id={`item-${item.id}`}
        initial={{ opacity: 1 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className={cn(
          "w-full rounded-lg text-card-foreground hover:bg-accent/50 relative cursor-pointer",
          isSelected ? "bg-card-selected" : "bg-card",
          item.isNew && "new-item-shadow",
          isSelected && "selected-border-rounded",
          className
        )}
        onClick={onClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onClick?.()
          }
        }}
        {...htmlProps}
      >
        <div className="p-3 w-full relative z-10">
          <div className="w-full relative">
            {/* Top-right icon */}
            <div className="absolute top-0 right-0 z-10">
              <div className="flex flex-col items-center text-muted-foreground space-y-1">
                {item.icon || <StickyNote className="h-[1.75rem] w-[1.75rem]" strokeWidth={1.25} />}
                <div className="text-xs text-center" title={tItems('item')}>
                  <span className="font-semibold">{tItems('item')}</span>
                </div>
              </div>
            </div>
            
            {/* Float spacer for icon */}
            <div className="float-right w-16 h-12"></div>
            
            {/* Content */}
            {renderGridContent()}
            
            {/* Clear the float */}
            <div className="clear-both"></div>
          </div>
        </div>
      </motion.div>
    )
  }

  // Detail mode layout - simplified to fit within existing container
  return (
    <Card className={`rounded-none sm:rounded-lg ${naturalHeight ? 'min-h-screen' : 'h-full'} flex flex-col bg-card border-none`}>
      <CardHeader className="flex-shrink-0 flex flex-row items-start justify-between py-4 px-4 sm:px-3 space-y-0">
        <div>
          <div className="flex items-center gap-1">
            <StickyNote className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            <h2 className="text-xl text-muted-foreground font-semibold">{tItems('itemDetails')}</h2>
          </div>
          <div className="mt-1 space-y-1">
            <IdentifierDisplay 
              externalId={item.externalId}
              identifiers={item.identifiers}
              iconSize="md"
              textSize="sm"
              skeletonMode={skeletonMode}
              displayMode="full"
            />
            <div className="text-sm text-muted-foreground">
              <Timestamp time={item.timestamp || item.date || ''} variant="relative" className="text-xs" skeletonMode={skeletonMode} />
            </div>
            {item.createdAt && item.updatedAt && (
              <Timestamp time={item.createdAt} completionTime={item.updatedAt} variant="elapsed" className="text-xs" skeletonMode={skeletonMode} />
            )}
            {/* Total results summary */}
            {totalResults > 0 && (
              <div className="text-sm mt-2">
                <span className="text-foreground font-medium"><NumberFlowWrapper value={totalResults} skeletonMode={skeletonMode} /></span> <span className="text-muted-foreground">{t(totalResults === 1 ? 'scoreResultAcross' : 'scoreResultsAcross')}</span> <span className="text-foreground font-medium"><NumberFlowWrapper value={item.scorecards.length} skeletonMode={skeletonMode} /></span> <span className="text-muted-foreground">{t(item.scorecards.length === 1 ? 'scorecard' : 'scorecards')}</span>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <CardButton
                icon={MoreHorizontal}
                onClick={() => {}}
                aria-label="More options"
                skeletonMode={skeletonMode}
              />
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content align="end" className="min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
                {onViewData && (
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={onViewData}
                  >
                    <Info className="mr-2 h-4 w-4" />
                    {tItems('viewDetails')}
                  </DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          {!isNarrowViewport && onToggleFullWidth && (
            <CardButton
              icon={isFullWidth ? Columns2 : Square}
              onClick={onToggleFullWidth}
              aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
              skeletonMode={skeletonMode}
            />
          )}
          {onClose && (
            <CardButton
              icon={X}
              onClick={onClose}
              aria-label="Close"
              skeletonMode={skeletonMode}
            />
          )}
        </div>
      </CardHeader>
      <CardContent className={`flex-grow px-4 sm:px-3 pb-4 ${naturalHeight ? '' : 'overflow-auto'}`}>
        <div className="space-y-4">
          {/* Description field display */}
          {item.description && 
           item.description.trim() && 
           !item.description.match(/^API Call - Report \d+$/) && 
           !item.description.match(/^(Call|Report|Session|Item) - .+$/) && (
            <div>
              <h3 className="text-sm font-medium text-foreground mb-2">{tItems('description')}</h3>
              <div className="p-3">
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            </div>
          )}
          
          {/* Collapsible sections for text, metadata, and file attachments */}
          <Accordion type="multiple" className="w-full space-y-4">
            {/* Text field display */}
            {item.text && (
              <AccordionItem value="text" className="border-b-0">
                <AccordionTrigger className="hover:no-underline py-2 px-0">
                  <div className="flex items-center gap-2">
                    <FileText className="h-3 w-3 text-muted-foreground" />
                    <span className="text-sm font-medium leading-none text-muted-foreground">{tItems('text')}</span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pt-0 pb-4">
                  <div className="p-3 bg-background rounded">
                    <div className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkBreaks]}
                        components={{
                          // Customize components for better styling
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
                        {item.text}
                      </ReactMarkdown>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            )}
            
            {/* Metadata section */}
            {(item.metadata && Object.keys(item.metadata).length > 0) && (
              <AccordionItem value="metadata" className="border-b-0">
                <AccordionTrigger className="hover:no-underline py-2 px-0">
                  <div className="flex items-center gap-2">
                    <Tag className="h-3 w-3 text-muted-foreground" />
                    <span className="text-sm font-medium leading-none text-muted-foreground">{tItems('metadata')}</span>
                    {!readOnly && <span className="text-[10px] text-muted-foreground">{tItems('optional')}</span>}
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pt-0 pb-4">
                  <MetadataEditor
                    value={item.metadata || {}}
                    onChange={(newMetadata) => {
                      // Update metadata in parent component if onChange is provided
                      if (onSave) {
                        onSave({ ...item, metadata: newMetadata });
                      }
                    }}
                    disabled={readOnly}
                    suppressHeader={true}
                  />
                </AccordionContent>
              </AccordionItem>
            )}
            
            {/* File attachments section */}
            {(item.attachedFiles && item.attachedFiles.length > 0) && (
              <AccordionItem value="attachments" className="border-b-0">
                <AccordionTrigger className="hover:no-underline py-2 px-0">
                  <div className="flex items-center gap-2">
                    <FileText className="h-3 w-3 text-muted-foreground" />
                    <span className="text-sm font-medium leading-none text-muted-foreground">{tItems('attachedFiles')}</span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="pt-0 pb-4">
                  <FileAttachments
                    attachedFiles={item.attachedFiles || []}
                    readOnly={readOnly}
                    onChange={(newFiles) => {
                      // Update attached files in parent component if onChange is provided
                      if (onSave) {
                        onSave({ ...item, attachedFiles: newFiles });
                      }
                    }}
                    onUpload={async (file) => {
                      // Mock upload implementation - return a path
                      return Promise.resolve(`/uploads/${file.name}`);
                    }}
                  />
                </AccordionContent>
              </AccordionItem>
            )}
          </Accordion>
          
          <ItemScoreResults
            groupedResults={groupedResults}
            isLoading={isLoading}
            error={error}
            itemId={String(item.id)}
            onScoreResultSelect={onScoreResultSelect}
            selectedScoreResultId={selectedScoreResultId}
          />
        </div>
      </CardContent>
    </Card>
  )
});

ItemCard.displayName = 'ItemCard';

export default ItemCard; 