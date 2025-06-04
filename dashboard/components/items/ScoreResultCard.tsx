import * as React from 'react'
import Link from 'next/link';
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { MoreHorizontal, X, Square, Columns2, Box, ListChecks, ListCheck, FileText } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { cn } from '@/lib/utils'
import { CardButton } from '@/components/CardButton'
import { Badge } from '@/components/ui/badge'
import { Timestamp } from '@/components/ui/timestamp'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { IdentifierDisplay } from '@/components/ui/identifier-display'
import { ScoreResultTrace } from '@/components/ui/score-result-trace'
import FileContentViewer from '@/components/ui/FileContentViewer'
import { getDashboardUrl } from '@/utils/plexus-links';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

// Interface for score result data
export interface ScoreResultData {
  id: string
  value: string
  explanation?: string
  confidence?: number | null
  itemId: string
  accountId: string
  scorecardId: string
  scoreId: string
  trace?: any | null
  attachments?: string[] | null
  scorecard?: {
    id: string
    name: string
    externalId?: string
  }
  score?: {
    id: string
    name: string
    externalId?: string
  }
  updatedAt?: string
  createdAt?: string
}

interface ScoreResultCardProps extends React.HTMLAttributes<HTMLDivElement> {
  scoreResult: ScoreResultData
  isFullWidth?: boolean
  onToggleFullWidth?: () => void
  onClose?: () => void
  skeletonMode?: boolean
  naturalHeight?: boolean
}

const ScoreResultCard = React.forwardRef<HTMLDivElement, ScoreResultCardProps>(({ 
  scoreResult,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  skeletonMode = false,
  naturalHeight = false,
  className, 
  ...props 
}, ref) => {
  React.useEffect(() => {
    console.log('[ScoreResultCard] Received scoreResult:', scoreResult);
    if (scoreResult) {
      console.log('[ScoreResultCard] scoreResult.attachments:', scoreResult.attachments);
    }
  }, [scoreResult]);

  const [isNarrowViewport, setIsNarrowViewport] = React.useState(false)

  React.useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)
    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  const getFileName = (filePath: string) => {
    return filePath.split('/').pop() || filePath;
  }

  return (
    <Card className={`rounded-none sm:rounded-lg ${naturalHeight ? 'min-h-screen' : 'h-full'} flex flex-col bg-card border-none`} ref={ref} {...props}>
      <CardHeader className="flex-shrink-0 flex flex-row items-start justify-between py-4 px-4 sm:px-3 space-y-0">
        <div>
          <div className="flex items-center gap-1">
            <Box className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
            <h2 className="text-xl text-muted-foreground font-semibold">Score Result Details</h2>
          </div>
          <div className="mt-1 space-y-1">
            <IdentifierDisplay 
              externalId={scoreResult.id}
              iconSize="md"
              textSize="sm"
              skeletonMode={skeletonMode}
              displayMode="full"
            />
            <div className="text-sm text-muted-foreground">
              <Timestamp 
                time={scoreResult.updatedAt || scoreResult.createdAt || new Date().toISOString()} 
                variant="relative" 
                className="text-xs" 
                skeletonMode={skeletonMode} 
              />
            </div>
            {scoreResult.createdAt && scoreResult.updatedAt && (
              <Timestamp 
                time={scoreResult.createdAt} 
                completionTime={scoreResult.updatedAt} 
                variant="elapsed" 
                className="text-xs" 
                skeletonMode={skeletonMode} 
              />
            )}
            
            {/* Scorecard summary */}
            {scoreResult.scorecard && (
              <div className="mt-3">
                <div className="flex items-baseline gap-1 font-semibold text-sm">
                  <ListChecks className="h-4 w-4 flex-shrink-0 text-muted-foreground translate-y-0.5" />
                  <Link href={getDashboardUrl({ recordType: 'scorecard', id: scoreResult.scorecard.id })} passHref legacyBehavior>
                    <a className="text-foreground hover:underline">{scoreResult.scorecard.name}</a>
                  </Link>
                </div>
              </div>
            )}
            
            {/* Score summary */}
            {scoreResult.score && scoreResult.scorecard && (
              <div className="mt-2">
                <div className="flex items-baseline gap-1 text-sm text-muted-foreground">
                  <ListCheck className="h-4 w-4 flex-shrink-0 translate-y-0.5" />
                  <Link href={getDashboardUrl({ recordType: 'score', id: scoreResult.score.id, parentId: scoreResult.scorecard.id })} passHref legacyBehavior>
                     <a className="text-foreground hover:underline">{scoreResult.score.name}</a>
                  </Link>
                </div>
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
                <DropdownMenu.Item 
                  className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                  onSelect={() => {}}
                >
                  View Raw Data
                </DropdownMenu.Item>
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

          {/* Value */}
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Value</h3>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{scoreResult.value}</Badge>
              {scoreResult.confidence !== null && scoreResult.confidence !== undefined && (
                <span className="text-xs text-muted-foreground">
                  {Math.round((scoreResult.confidence || 0) * 100)}% confidence
                </span>
              )}
            </div>
          </div>
          
          {/* Explanation */}
          {scoreResult.explanation && (
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-2">Explanation</h3>
              <div className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
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
                  {scoreResult.explanation}
                </ReactMarkdown>
              </div>
            </div>
          )}
          
          {/* Trace */}
          <ScoreResultTrace trace={scoreResult.trace} />

          {/* Attachments */}
          {scoreResult.attachments && scoreResult.attachments.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-2 mt-4">Attachments</h3>
              <Accordion type="multiple" className="w-full">
                {scoreResult.attachments.map((attachmentPath, index) => (
                  <AccordionItem 
                    value={`attachment-${index}`} 
                    key={attachmentPath + index}
                    className="border-b-0 mb-2"
                  >
                    <AccordionTrigger>
                        <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4" />
                            {getFileName(attachmentPath)}
                        </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <FileContentViewer filePath={attachmentPath} />
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
});

ScoreResultCard.displayName = 'ScoreResultCard';

export default ScoreResultCard; 