import React, { useState, useRef } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Info, ChevronUp, ChevronDown, MessageCircleMore, ThumbsUp, ThumbsDown } from 'lucide-react'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'

interface Score {
  name: string
  value: string
  explanation: string
  isAnnotated?: boolean
  annotations?: any[]
  allowFeedback?: boolean
}

interface ItemDetailScoreResultProps {
  score: Score
}

const ItemDetailScoreResult: React.FC<ItemDetailScoreResultProps> = ({ score }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isAnnotationsExpanded, setIsAnnotationsExpanded] = useState(false)
  const textRef = useRef<HTMLDivElement>(null)
  const [showExpandButton, setShowExpandButton] = useState(false)

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
          p: ({node, ...props}) => <p className="mb-2" {...props} />,
          strong: ({node, ...props}) => <strong className="font-semibold" {...props} />,
          ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-2" {...props} />,
          li: ({node, ...props}) => <li className="mb-1" {...props} />,
        }}
      >
        {text}
      </ReactMarkdown>
    )
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
          {score.allowFeedback && (
            <>
              {score.isAnnotated && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsAnnotationsExpanded(!isAnnotationsExpanded)}
                  className="text-xs bg-secondary text-secondary-foreground hover:bg-secondary hover:text-secondary-foreground"
                >
                  <MessageCircleMore className="h-4 w-4" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="text-xs hover:bg-muted hover:text-muted-foreground"
              >
                <ThumbsUp className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-xs hover:bg-muted hover:text-muted-foreground"
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
      {score.isAnnotated && isAnnotationsExpanded && (
        <div className="mt-2 space-y-2">
          <div className="flex justify-between items-center mb-2">
            <h6 className="text-sm font-medium">Feedback</h6>
            <Button
              variant="outline"
              size="sm"
              className="text-xs"
            >
              Create
            </Button>
          </div>
          {score.annotations && score.annotations.map((annotation, index) => (
            <div key={index} className="pl-4 border-l-2 border-primary">
              {/* Render annotation content here */}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ItemDetailScoreResult
