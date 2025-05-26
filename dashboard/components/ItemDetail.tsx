import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { ChevronUp, ChevronDown, Square, Columns2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CardButton } from '@/components/CardButton'
import ItemDetailScoreResult from './ItemDetailScoreResult'
import { Timestamp } from '@/components/ui/timestamp'
import { useItemScoreResults } from '@/hooks/useItemScoreResults'
import ItemScoreResults from './ItemScoreResults'

interface Score {
  name: string
  value: string
  explanation: string
  isAnnotated: boolean
  allowFeedback: boolean
  annotations: Array<{
    value: string
    explanation: string
    annotation?: string
    timestamp: string
    user?: {
      name: string
      initials: string
    }
    isSystem?: boolean
    isThumbsUp?: boolean
  }>
}

interface FeedbackItem {
  id: string
  scorecard: string
  inferences: string
  results: string
  cost: string
  status: string
  date: string
  sampleMetadata: any[]
  sampleTranscript: any[]
  sampleScoreResults: any[]
}

interface ItemDetailProps {
  item: FeedbackItem
  controlButtons?: React.ReactNode
  getBadgeVariant: (status: string) => string
  getRelativeTime: (dateString: string | undefined) => string
  isMetadataExpanded: boolean
  setIsMetadataExpanded: (expanded: boolean) => void
  isDataExpanded: boolean
  setIsDataExpanded: (expanded: boolean) => void
  isErrorExpanded: boolean
  setIsErrorExpanded: (expanded: boolean) => void
  sampleMetadata: any[]
  sampleTranscript: any[]
  sampleScoreResults: any[]
  handleThumbsUp: (scoreName: string) => void
  handleThumbsDown: (scoreName: string) => void
  handleNewAnnotationSubmit: (scoreName: string) => void
  toggleAnnotations: (scoreName: string) => void
  showNewAnnotationForm: { scoreName: string | null; isThumbsUp: boolean }
  setShowNewAnnotationForm: (form: { scoreName: string | null; isThumbsUp: boolean }) => void
  newAnnotation: any
  setNewAnnotation: (annotation: any) => void
  expandedAnnotations: string[]
  thumbedUpScores: Set<string>
  setThumbedUpScores: (scores: Set<string>) => void
  isFullWidth: boolean
  isFeedbackMode: boolean
  onToggleFullWidth: () => void
  onClose: () => void
}

const ItemDetail: React.FC<ItemDetailProps> = ({
  item,
  controlButtons,
  getBadgeVariant,
  getRelativeTime,
  isMetadataExpanded,
  setIsMetadataExpanded,
  isDataExpanded,
  setIsDataExpanded,
  isErrorExpanded,
  setIsErrorExpanded,
  sampleMetadata,
  sampleTranscript,
  sampleScoreResults,
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
  isFullWidth,
  isFeedbackMode,
  onToggleFullWidth,
  onClose,
}) => {
  const [isNarrowViewport, setIsNarrowViewport] = useState(false)
  
  // Use the new hook to fetch score results
  const { groupedResults, isLoading, error } = useItemScoreResults(item.id)
  
  // Debug logging - commented out
  // console.log('ItemDetail - item data:', { id: item.id, item });
  // console.log('ItemDetail - score results:', { groupedResults, isLoading, error });

  useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }

    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)

    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  useEffect(() => {
    setIsDataExpanded(isFullWidth);
  }, [isFullWidth, setIsDataExpanded]);

  return (
    <Card className="rounded-none sm:rounded-lg h-full flex flex-col bg-card border-none">
      <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-4 px-4 sm:px-3 space-y-0">
        <div>
          <h2 className="text-xl font-semibold">Item Details</h2>
          <p className="text-sm text-muted-foreground">
            <Timestamp time={item.date} variant="relative" />
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {!isNarrowViewport && (
            <CardButton
              icon={isFullWidth ? Columns2 : Square}
              onClick={onToggleFullWidth}
            />
          )}
          <CardButton
            icon={X}
            onClick={onClose}
          />
        </div>
      </CardHeader>
      <CardContent className="flex-grow overflow-auto px-4 sm:px-3 pb-4">
        <div className="space-y-4">
          <ItemScoreResults
            groupedResults={groupedResults}
            isLoading={isLoading}
            error={error}
            itemId={item.id}
          />
        </div>
      </CardContent>
    </Card>
  )
}

export default ItemDetail
