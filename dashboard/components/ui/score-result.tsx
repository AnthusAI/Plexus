import React, { useState } from 'react'
import { X, Microscope, Scale, MessageSquareMore, UnfoldVertical, Text, View, ChevronDown, ChevronUp, Ellipsis } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { CardButton } from '@/components/CardButton'
import { LabelBadgeComparison } from '@/components/LabelBadgeComparison'
import { Button } from '@/components/ui/button'
import { ScoreResultTrace } from './score-result-trace'

export interface ScoreResultData {
  id: string
  value: string
  confidence: number | null
  explanation: string | null
  metadata: {
    human_label: string | null
    correct: boolean
    human_explanation?: string | null
    text?: string | null
  }
  trace?: any | null
  itemId: string | null
}

export interface ScoreResultComponentProps {
  result: ScoreResultData
  variant?: 'list' | 'detail'
  isFocused?: boolean
  onSelect?: () => void
  onClose?: () => void
  navigationControls?: React.ReactNode
}



export function ScoreResultComponent({ 
  result,
  variant = 'list',
  isFocused = false,
  onSelect,
  onClose,
  navigationControls
}: ScoreResultComponentProps) {
  const [isTextExpanded, setIsTextExpanded] = useState(false);
  


  // Get the first part of text for collapsed view
  const getCollapsedText = (text: string) => {
    if (!text) return '';
    
    // First check for line breaks
    const lines = text.split('\n');
    if (lines.length > 5) {
      return lines.slice(0, 5).join('\n');
    }
    
    // If not enough line breaks, check character length
    const MAX_CHARS = 350; // Roughly 5 lines of 70 chars each
    if (text.length > MAX_CHARS) {
      return text.substring(0, MAX_CHARS) + '...';
    }
    
    return text;
  };

  // Check if text should have a "Show more" button
  const shouldShowMoreButton = (text: string | null | undefined) => {
    if (!text) return false;
    
    // Either enough lines OR enough characters
    return text.split('\n').length > 5 || text.length > 350;
  };

  // List variant (compact view)
  if (variant === 'list') {
    return (
      <Card 
        className={`px-0 pb-0 rounded-lg border-0 shadow-none transition-colors
          hover:bg-background cursor-pointer
          ${isFocused ? 'bg-background' : 'bg-card-light'}`}
        onClick={onSelect}
      >
        <CardContent className="flex flex-col p-2">
          <div className="flex items-start justify-between">
            <div>
              <div className="font-medium">
                <LabelBadgeComparison
                  predictedLabel={result.value}
                  actualLabel={result.metadata.human_label ?? ''}
                  isCorrect={result.metadata.correct}
                  showStatus={false}
                  isFocused={isFocused}
                />
                {result.explanation && (
                  <div className="text-sm text-muted-foreground mt-1 line-clamp-2">
                    {result.explanation}
                  </div>
                )}
              </div>
            </div>
            {result.confidence && (
              <Badge className="bg-card self-start shadow-none">
                {Math.round(result.confidence * 100)}%
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>
    )
  }



  // Detail variant (full view)
  return (
    <div className="relative h-full flex flex-col">
      <div className="flex justify-between items-center mb-2 flex-shrink-0">
        <div className="flex items-center">
          <Microscope className="w-4 h-4 mr-1 text-foreground shrink-0" />
          <span className="text-sm text-foreground">Score result</span>
        </div>
        <div className="flex items-center gap-2">
          {navigationControls}
          {onClose && <CardButton icon={X} onClick={onClose} />}
        </div>
      </div>
      <div className="flex-1 min-h-0 overflow-hidden">
        <div className="bg-card-light rounded-lg h-full overflow-y-auto">
          <div className="space-y-4">
            <div>
              <div className="flex justify-between items-center mb-1">
                <div className="flex items-center">
                  <Scale className="w-4 h-4 mr-1 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Value</p>
                </div>
                <span className="text-sm text-muted-foreground">
                  ID: {result.itemId}
                </span>
              </div>
              <LabelBadgeComparison
                predictedLabel={result.value}
                actualLabel={result.metadata.human_label ?? ''}
                isCorrect={result.metadata.correct}
                isDetail={true}
              />
            </div>

            {result.explanation && (
              <div>
                <div className="flex items-center mb-1">
                  <MessageSquareMore className="w-4 h-4 mr-1 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Explanation</p>
                </div>
                <div className="bg-background rounded-md p-3">
                  <p className="text-sm whitespace-pre-wrap">
                    {result.explanation}
                  </p>
                </div>
              </div>
            )}

            {!result.metadata.correct && result.metadata.human_explanation && (
              <div>
                <div className="flex items-center mb-1">
                  <MessageSquareMore className="w-4 h-4 mr-1 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Label comment</p>
                </div>
                <p className="text-sm whitespace-pre-wrap">
                  {result.metadata.human_explanation}
                </p>
              </div>
            )}

            {result.confidence && (
              <div>
                <div className="flex items-center mb-1">
                  <UnfoldVertical className="w-4 h-4 mr-1 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Confidence</p>
                </div>
                <p className="text-lg font-semibold">
                  {Math.round(result.confidence * 100)}%
                </p>
              </div>
            )}

            {result.metadata.text && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center">
                    <Text className="w-4 h-4 mr-1 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">Text</p>
                  </div>
                  {shouldShowMoreButton(result.metadata.text) && (
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-6 px-2"
                      onClick={(e) => {
                        e.stopPropagation();
                        setIsTextExpanded(!isTextExpanded);
                      }}
                    >
                      {isTextExpanded ? (
                        <><ChevronUp className="h-4 w-4 mr-1" /> Collapse</>
                      ) : (
                        <><ChevronDown className="h-4 w-4 mr-1" /> Expand</>
                      )}
                    </Button>
                  )}
                </div>
                <div className="bg-background rounded-md p-3">
                  {/* Text content */}
                  <div className={isTextExpanded ? "" : "max-h-[150px] overflow-hidden relative"}>
                    <p className="text-sm whitespace-pre-wrap font-mono">
                      {isTextExpanded ? result.metadata.text : getCollapsedText(result.metadata.text || '')}
                    </p>
                    
                    {/* Gradient overlay and ellipsis - shown when collapsed and text is long */}
                    {!isTextExpanded && shouldShowMoreButton(result.metadata.text) && (
                      <>
                        <div 
                          className="absolute bottom-0 left-0 right-0 h-16 pointer-events-none"
                          style={{ 
                            background: 'linear-gradient(to top, var(--background) 0%, var(--background) 25%, rgba(255, 255, 255, 0) 100%)'
                          }}
                        />
                        <div className="absolute bottom-0 left-0 right-0 flex justify-center">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="bg-background/90 hover:bg-background mt-1"
                            onClick={(e) => {
                              e.stopPropagation();
                              setIsTextExpanded(true);
                            }}
                          >
                            <Ellipsis className="h-4 w-4 text-foreground" />
                          </Button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Trace section */}
            {result.trace && (
              <div>
                <div className="flex items-center mb-1">
                  <View className="w-4 h-4 mr-1 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Trace</p>
                </div>
                <ScoreResultTrace trace={result.trace} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
} 