import React, { useState, useRef } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ThumbsUp, ThumbsDown, MessageCircleMore, Info, ChevronUp, ChevronDown } from "lucide-react"
import Link from 'next/link'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import ReactMarkdown from 'react-markdown'

// Add type for node prop
interface MarkdownComponentProps {
  node?: any;
  children?: React.ReactNode;
  [key: string]: any;
}

interface ItemDetailScoreResultProps {
  score: any;
  isAnnotation: boolean;
  handleThumbsUp?: (scoreName: string) => void;
  handleThumbsDown?: (scoreName: string) => void;
  handleNewAnnotationSubmit?: (scoreName: string) => void;
  toggleAnnotations?: (scoreName: string) => void;
  showNewAnnotationForm?: { scoreName: string | null; isThumbsUp: boolean };
  newAnnotation?: { value: string; explanation: string; annotation: string };
  setNewAnnotation?: (annotation: { value: string; explanation: string; annotation: string }) => void;
  expandedAnnotations?: string[];
  thumbedUpScores?: Set<string>;
  setShowNewAnnotationForm?: (form: { scoreName: string | null; isThumbsUp: boolean }) => void;
  setThumbedUpScores?: (scores: Set<string>) => void;
  isFeedbackMode?: boolean;
}

export default function ItemDetailScoreResult({
  score,
  isAnnotation,
  handleThumbsUp,
  handleThumbsDown,
  handleNewAnnotationSubmit,
  toggleAnnotations,
  showNewAnnotationForm,
  newAnnotation,
  setNewAnnotation,
  expandedAnnotations,
  thumbedUpScores,
  setShowNewAnnotationForm,
  setThumbedUpScores,
  isFeedbackMode = false
}: ItemDetailScoreResultProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const textRef = useRef<HTMLDivElement>(null)
  const [showExpandButton, setShowExpandButton] = useState(false)

  const hasAnnotations = score.annotations && score.annotations.length > 0
  const hasFeedback = score.isAnnotated || hasAnnotations
  const hasThumbsDownFeedback = (score.annotations || [])
    .some((annotation: any) => !annotation.isThumbsUp)
  const feedbackIconColor = hasFeedback
    ? hasThumbsDownFeedback
      ? 'bg-false text-primary-foreground hover:bg-false hover:text-primary-foreground'
      : 'bg-true text-primary-foreground hover:bg-true hover:text-primary-foreground'
    : ''

  React.useEffect(() => {
    if (textRef.current) {
      const lineHeight = parseInt(window.getComputedStyle(textRef.current).lineHeight)
      setShowExpandButton(textRef.current.scrollHeight > lineHeight * 2)
    }
  }, [score.explanation])

  const getValueBadgeClass = (value: string) => {
    return value.toLowerCase() === 'yes' 
      ? 'bg-true text-primary-foreground w-16 justify-center' 
      : 'bg-false text-primary-foreground w-16 justify-center'
  }

  const renderRichText = (text: string) => {
    return (
      <ReactMarkdown
        components={{
          p: ({node, ...props}: MarkdownComponentProps) => <p className="mb-2" {...props} />,
          strong: ({node, ...props}: MarkdownComponentProps) => <strong className="font-semibold" {...props} />,
          ul: ({node, ...props}: MarkdownComponentProps) => <ul className="list-disc pl-5 mb-2" {...props} />,
          li: ({node, ...props}: MarkdownComponentProps) => <li className="mb-1" {...props} />,
        }}
      >
        {text}
      </ReactMarkdown>
    )
  }

  const getBorderColor = () => {
    if (score.isSystem) return 'var(--secondary)'
    if (score.isThumbsUp) return 'var(--true)'
    return 'var(--false)'
  }

  return (
    <div className="py-2 border-b last:border-b-0">
      <div className="flex justify-between items-center mb-1">
        <div className="flex items-center">
          <h5 className="text-sm font-medium">{score.name}</h5>
          <div className="inline-flex items-center ml-1">
            <Link href={`/scorecards?score=${encodeURIComponent(score.name)}`} passHref>
              <Button variant="ghost" size="sm" className="p-0 h-auto translate-y-[2px]" title={`More info about ${score.name}`}>
                <Info className="h-4 w-4 text-muted-foreground" />
              </Button>
            </Link>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {hasFeedback && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => toggleAnnotations?.(score.name)}
              className={`text-xs ${feedbackIconColor}`}
            >
              <MessageCircleMore className="h-4 w-4" />
            </Button>
          )}
          {score.allowFeedback && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleThumbsUp?.(score.name)}
                className={`text-xs hover:bg-true hover:text-primary-foreground ${
                  thumbedUpScores?.has(score.name) ? 'bg-true text-primary-foreground' : ''
                }`}
              >
                <ThumbsUp className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleThumbsDown?.(score.name)}
                className="text-xs hover:bg-false hover:text-primary-foreground"
              >
                <ThumbsDown className="h-4 w-4" />
              </Button>
            </>
          )}
          <Badge className={score.value.includes('%') ? 'bg-primary text-primary-foreground w-16 justify-center' : getValueBadgeClass(score.value)}>
            {score.value}
          </Badge>
        </div>
      </div>
      <div className="relative">
        <div 
          ref={textRef}
          className="text-sm text-muted-foreground overflow-hidden cursor-pointer"
          style={{ 
            display: '-webkit-box',
            WebkitLineClamp: '2',
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            ...(isExpanded ? { WebkitLineClamp: 'unset', display: 'block' } : {})
          }}
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {renderRichText(score.explanation)}
        </div>
        {showExpandButton && (
          <Button 
            variant="link" 
            size="sm" 
            onClick={() => setIsExpanded(!isExpanded)}
            className="absolute bottom-0 right-0 px-0 py-1 h-auto bg-white dark:bg-gray-800"
          >
            {isExpanded 
              ? <ChevronUp className="h-3 w-3 inline ml-1" />
              : <ChevronDown className="h-3 w-3 inline ml-1" />
            }
          </Button>
        )}
      </div>
      {!isAnnotation && (
        <>
          {showNewAnnotationForm?.scoreName === score.name && (
            <div 
              className="mb-2 space-y-2 border-l-4 pl-4"
              style={{ 
                borderColor: (showNewAnnotationForm?.isThumbsUp ? 'var(--true)' : 'var(--false)') + ' !important' 
              }}
            >
              <div className="mb-4">
                <h6 className="text-sm font-medium mb-2">Feedback</h6>
                <div className="space-y-2">
                  {showNewAnnotationForm?.isThumbsUp ? (
                    <>
                      <div className="text-sm font-medium">Value: {newAnnotation?.value}</div>
                      <div className="text-sm">Explanation: {newAnnotation?.explanation}</div>
                    </>
                  ) : (
                    <>
                      <Select 
                        onValueChange={(value) => setNewAnnotation?.({ 
                          ...newAnnotation!, 
                          value 
                        })}
                        value={newAnnotation?.value}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select value" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Yes">Yes</SelectItem>
                          <SelectItem value="No">No</SelectItem>
                        </SelectContent>
                      </Select>
                      <Textarea 
                        placeholder="Explanation" 
                        value={newAnnotation?.explanation}
                        onChange={(e) => setNewAnnotation?.({
                          ...newAnnotation!,
                          explanation: e.target.value
                        })}
                      />
                    </>
                  )}
                  <Input 
                    placeholder="Feedback" 
                    value={newAnnotation?.annotation}
                    onChange={(e) => setNewAnnotation?.({
                      ...newAnnotation!,
                      annotation: e.target.value
                    })}
                  />
                  <div className="flex justify-end space-x-2">
                    <Button 
                      variant="outline" 
                      onClick={() => setShowNewAnnotationForm?.({ scoreName: null, isThumbsUp: false })}
                    >
                      Cancel
                    </Button>
                    <Button onClick={() => handleNewAnnotationSubmit?.(score.name)}>
                      Submit Feedback
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {hasFeedback && expandedAnnotations?.includes(score.name) && (
            <div className="mt-2 space-y-2">
              <div className="flex justify-between items-center mb-2">
                <h6 className="text-sm font-medium">Feedback History</h6>
              </div>
              {(score.annotations || [])
                .sort((a: any, b: any) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
                .map((annotation: any, annotationIndex: number) => (
                  <div key={annotationIndex} className="relative">
                    <div 
                      className="pl-4 border-l-4"
                      style={{ borderColor: annotation.isThumbsUp ? 'var(--true)' : 'var(--false)' }}
                    >
                      <div className="absolute top-2 left-4 rounded-full p-1" 
                           style={{ backgroundColor: annotation.isThumbsUp ? 'var(--true)' : 'var(--false)' }}>
                        {annotation.isThumbsUp ? (
                          <ThumbsUp className="h-3 w-3 text-primary-foreground" />
                        ) : (
                          <ThumbsDown className="h-3 w-3 text-primary-foreground" />
                        )}
                      </div>
                      <div className="flex justify-end mb-2">
                        <Badge className={getValueBadgeClass(annotation.value)}>{annotation.value}</Badge>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {renderRichText(annotation.explanation)}
                      </div>
                      {annotation.annotation && (
                        <div className="mt-2 text-sm italic">
                          "{annotation.annotation}"
                        </div>
                      )}
                      <div className="flex justify-between items-center mt-2 text-xs text-muted-foreground">
                        <span>{new Date(annotation.timestamp).toLocaleString()}</span>
                        {annotation.user && (
                          <div className="flex items-center space-x-2">
                            <span>{annotation.user.name}</span>
                            <Avatar className="h-6 w-6 bg-muted">
                              <AvatarFallback className="bg-muted">{annotation.user.initials}</AvatarFallback>
                            </Avatar>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </>
      )}

      {/* Add timestamp and user info for annotations */}
      {isAnnotation && (
        <div className="flex justify-between items-center mt-2 text-xs text-muted-foreground">
          <span>{new Date(score.timestamp).toLocaleString()}</span>
          {score.user && (
            <div className="flex items-center space-x-2">
              <span>{score.user.name}</span>
              <Avatar className="h-6 w-6 bg-muted">
                <AvatarFallback className="bg-muted">{score.user.initials}</AvatarFallback>
              </Avatar>
            </div>
          )}
        </div>
      )}
      {score.annotation && (
        <div className="mt-2 text-sm italic">
          "{score.annotation}"
        </div>
      )}
    </div>
  )
}
