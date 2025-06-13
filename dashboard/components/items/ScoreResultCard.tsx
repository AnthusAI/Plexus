import * as React from 'react'
import Link from 'next/link';
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { MoreHorizontal, X, Square, Columns2, Box, ListChecks, ListCheck, FileText, Target, MessageSquareMore, View, Files, AlertTriangle } from 'lucide-react'
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
import { downloadData } from 'aws-amplify/storage';
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
  errorCode?: string | null
  errorMessage?: string | null
}

const ScoreResultCard = React.forwardRef<HTMLDivElement, ScoreResultCardProps>(({ 
  scoreResult,
  isFullWidth = false,
  onToggleFullWidth,
  onClose,
  skeletonMode = false,
  naturalHeight = false,
  errorCode = null,
  errorMessage = null,
  className, 
  ...props 
}, ref) => {
  React.useEffect(() => {
    console.log('[ScoreResultCard] Received scoreResult:', scoreResult);
    if (scoreResult) {
      console.log('[ScoreResultCard] scoreResult.attachments:', scoreResult.attachments);
      console.log('[ScoreResultCard] scoreResult.trace:', scoreResult.trace);
    }
  }, [scoreResult]);

  // Extract error information from the score result - same logic as ItemScoreResults
  const errorInfo = React.useMemo(() => {
    const value = scoreResult.value?.toLowerCase() || '';
    const explanation = scoreResult.explanation?.toLowerCase() || '';
    
    const hasError = value.includes('error') || 
           value.includes('fail') || 
           value.includes('exception') || 
           explanation.includes('error') || 
           explanation.includes('fail') || 
           explanation.includes('exception') ||
           explanation.includes('timeout') ||
           explanation.includes('not found') ||
           explanation.includes('invalid');

    if (!hasError) {
      return { hasError: false, errorCode: null, errorMessage: null };
    }

    // Try to extract error code from value or explanation
    let detectedErrorCode = null;
    let detectedErrorMessage = null;

    // Look for HTTP status codes
    const statusCodeMatch = (scoreResult.value + ' ' + (scoreResult.explanation || '')).match(/\b([4-5]\d{2})\b/);
    if (statusCodeMatch) {
      detectedErrorCode = statusCodeMatch[1];
    }

    // Look for common error messages
    const fullText = scoreResult.value + ' ' + (scoreResult.explanation || '');
    if (fullText.toLowerCase().includes('timeout')) {
      detectedErrorMessage = 'Request timeout';
      detectedErrorCode = detectedErrorCode || '408';
    } else if (fullText.toLowerCase().includes('not found')) {
      detectedErrorMessage = 'Resource not found';
      detectedErrorCode = detectedErrorCode || '404';
    } else if (fullText.toLowerCase().includes('invalid')) {
      detectedErrorMessage = 'Invalid request';
      detectedErrorCode = detectedErrorCode || '400';
    } else if (fullText.toLowerCase().includes('exception')) {
      detectedErrorMessage = 'Internal exception';
      detectedErrorCode = detectedErrorCode || '500';
    } else {
      detectedErrorMessage = 'Unknown error';
      detectedErrorCode = detectedErrorCode || '500';
    }

    // Use provided props if available, otherwise use detected values
    return { 
      hasError: true, 
      errorCode: errorCode || detectedErrorCode, 
      errorMessage: errorMessage || detectedErrorMessage 
    };
  }, [scoreResult.value, scoreResult.explanation, errorCode, errorMessage]);

  const [isNarrowViewport, setIsNarrowViewport] = React.useState(false)
  const [traceData, setTraceData] = React.useState<any>(null)

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

  // Check for trace.json file and load its content
  const traceJsonPath = React.useMemo(() => {
    if (!scoreResult.attachments) return null;
    return scoreResult.attachments.find(path => 
      getFileName(path).toLowerCase() === 'trace.json'
    ) || null;
  }, [scoreResult.attachments]);

  // Load trace data from trace.json file
  React.useEffect(() => {
    console.log('[ScoreResultCard] traceJsonPath:', traceJsonPath);
    
    if (traceJsonPath) {
      const fetchTraceData = async () => {
        try {
          console.log('[ScoreResultCard] Fetching trace.json content from:', traceJsonPath);
          
          // Determine which storage bucket to use based on file path
          let storageOptions: { path: string; options?: { bucket?: string } } = { path: traceJsonPath };
          
          if (traceJsonPath.startsWith('scoreresults/')) {
            // Score result files are stored in the scoreResultAttachments bucket
            storageOptions = {
              path: traceJsonPath,
              options: { bucket: 'scoreResultAttachments' }
            };
          } else if (traceJsonPath.startsWith('reportblocks/')) {
            // Report block files are stored in the reportBlockDetails bucket
            storageOptions = {
              path: traceJsonPath,
              options: { bucket: 'reportBlockDetails' }
            };
          } else if (traceJsonPath.startsWith('attachments/')) {
            // These files are in the default attachments bucket
            storageOptions = { path: traceJsonPath };
          }
          
          const downloadResult = await downloadData(storageOptions).result;
          const fileText = await downloadResult.body.text();
          
          console.log('[ScoreResultCard] Raw trace.json content:', fileText);
          
          // Parse the JSON content
          const parsedTraceData = JSON.parse(fileText);
          console.log('[ScoreResultCard] Parsed trace data:', parsedTraceData);
          
          setTraceData(parsedTraceData);
        } catch (error) {
          console.error('[ScoreResultCard] Error fetching trace.json:', error);
          // Fallback to existing trace data if file fetch fails
          console.log('[ScoreResultCard] Falling back to scoreResult.trace:', scoreResult.trace);
          setTraceData(scoreResult.trace || null);
        }
      };
      
      fetchTraceData();
    } else {
      console.log('[ScoreResultCard] No trace.json found, setting traceData to null');
      setTraceData(null);
    }
  }, [traceJsonPath]);

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
            <div className="flex items-center gap-1 mb-2">
              <Target className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-medium text-muted-foreground">Value</h3>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{scoreResult.value}</Badge>
              {scoreResult.confidence !== null && scoreResult.confidence !== undefined && (
                <span className="text-xs text-muted-foreground">
                  {Math.round((scoreResult.confidence || 0) * 100)}% confidence
                </span>
              )}
            </div>
          </div>
          
          {/* Error Indicator */}
          {errorInfo.hasError && (
            <div className="p-4 rounded-md bg-destructive">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4 text-attention" />
                <h3 className="text-sm font-medium text-attention">Error {errorInfo.errorCode}</h3>
              </div>
              {errorInfo.errorMessage && (
                <div className="text-sm text-attention">
                  {errorInfo.errorMessage}
                </div>
              )}
            </div>
          )}
          
          {/* Explanation */}
          {scoreResult.explanation && (
            <div>
              <div className="flex items-center gap-1 mb-2">
                <MessageSquareMore className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-sm font-medium text-muted-foreground">Explanation</h3>
              </div>
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
          {traceJsonPath && (
            <div>
              <div className="flex items-center gap-1 mb-2">
                <View className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-sm font-medium text-muted-foreground">Trace</h3>
              </div>
              <ScoreResultTrace trace={traceData} />
            </div>
          )}

          {/* Attachments */}
          {scoreResult.attachments && scoreResult.attachments.length > 0 && (
            <div>
              <div className="flex items-center gap-1 mb-2">
                <Files className="h-4 w-4 text-muted-foreground" />
                <h3 className="text-sm font-medium text-muted-foreground">Attachments</h3>
              </div>
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