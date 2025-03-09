import React, { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table'
import { ChevronUp, ChevronDown, Square, Columns2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { CardButton } from '@/components/CardButton'
import ItemDetailScoreResult from './ItemDetailScoreResult'
import { formatTimeAgo } from '@/utils/format-time'

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
      <CardHeader className="flex-shrink-0 flex flex-row items-center justify-between py-4 px-4 sm:px-6 space-y-0">
        <div>
          <h2 className="text-xl font-semibold">{item.scorecard}</h2>
          <p className="text-sm text-muted-foreground">
            {formatTimeAgo(item.date)}
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
      <CardContent className="flex-grow overflow-auto px-4 sm:px-6 pb-4">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p className="text-sm font-medium">Inferences</p>
            <p>{item.inferences}</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium">Status</p>
            <Badge 
              className={`w-24 justify-center ${getBadgeVariant(item.status)}`}
            >
              {item.status}
            </Badge>
          </div>
          <div>
            <p className="text-sm font-medium">Results</p>
            <p>{item.results}</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium">Cost</p>
            <p>{item.cost}</p>
          </div>
        </div>
        
        <div className={`${isFullWidth ? 'flex gap-16' : ''}`}>
          <div className={`${isFullWidth ? 'w-1/2' : ''}`}>
            {item.status === 'Error' && (
              <div className="-mx-4 sm:-mx-6 mb-4">
                <div
                  className="relative group hover:bg-destructive hover:text-primary-foreground cursor-pointer"
                  onClick={() => setIsErrorExpanded(!isErrorExpanded)}
                >
                  <div className="flex justify-between items-center px-4 sm:px-6 py-2 bg-destructive text-primary-foreground">
                    <span className="text-md font-semibold">
                      Error
                    </span>
                    {isErrorExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </div>
                </div>
                {isErrorExpanded && (
                  <div className="mt-2 px-4 sm:px-6">
                    <Table>
                      <TableBody>
                        <TableRow>
                          <TableCell className="pl-0 pr-0">Response from OpenAI: 429 - You exceeded your current quota, please check your plan and billing details</TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            )}
            
            <div className="-mx-4 sm:-mx-6 mb-4">
              <div
                className="relative group bg-card-light hover:bg-accent hover:text-accent-foreground cursor-pointer"
                onClick={() => setIsMetadataExpanded(!isMetadataExpanded)}
              >
                <div className="flex justify-between items-center px-4 sm:px-6 py-2">
                  <span className="text-md font-semibold">
                    Metadata
                  </span>
                  {isMetadataExpanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </div>
              </div>
            </div>
            {isMetadataExpanded && (
              <div className="mt-2">
                <Table>
                  <TableBody>
                    {sampleMetadata.map((meta, index) => (
                      <TableRow key={index}>
                        <TableCell className="font-medium pl-0">{meta.key}</TableCell>
                        <TableCell className="text-right pr-0">{meta.value}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
            
            <div className="-mx-4 sm:-mx-6 mt-4">
              <div
                className="relative group bg-card-light hover:bg-accent hover:text-accent-foreground cursor-pointer"
                onClick={() => setIsDataExpanded(!isDataExpanded)}
              >
                <div className="flex justify-between items-center px-4 sm:px-6 py-2">
                  <span className="text-md font-semibold">
                    Data
                  </span>
                  {isDataExpanded ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </div>
              </div>
            </div>
            {isDataExpanded && (
              <div className="mt-2 px-4 sm:px-6">
                {sampleTranscript.map((line, index) => (
                  <p key={index} className="text-sm">
                    <span className="font-semibold">{line.speaker}: </span>
                    {line.text}
                  </p>
                ))}
              </div>
            )}
          </div>

          <div className={`${isFullWidth ? 'w-1/2' : 'mt-4'}`}>
            <div className="-mx-4 sm:-mx-6 mb-4">
              <div className="px-4 sm:px-6 py-2 bg-card-light">
                <h4 className="text-md font-semibold">Score Results</h4>
              </div>
            </div>
            {sampleScoreResults.map((section, sectionIndex) => (
              <div key={sectionIndex} className="mb-6">
                <div className="-mx-4 sm:-mx-6 mb-4">
                  <div className="px-4 sm:px-6 py-2">
                    <h4 className="text-md font-semibold">{section.section}</h4>
                  </div>
                  <hr className="border-t border-border" />
                </div>
                <div>
                  {section.scores.map((score: Score, scoreIndex: number) => (
                    <ItemDetailScoreResult
                      key={scoreIndex}
                      score={score}
                      isAnnotation={false}
                      handleThumbsUp={handleThumbsUp}
                      handleThumbsDown={handleThumbsDown}
                      handleNewAnnotationSubmit={handleNewAnnotationSubmit}
                      toggleAnnotations={toggleAnnotations}
                      showNewAnnotationForm={showNewAnnotationForm}
                      newAnnotation={newAnnotation}
                      setNewAnnotation={setNewAnnotation}
                      expandedAnnotations={expandedAnnotations}
                      thumbedUpScores={thumbedUpScores}
                      setShowNewAnnotationForm={setShowNewAnnotationForm}
                      setThumbedUpScores={setThumbedUpScores}
                      isFeedbackMode={isFeedbackMode}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default ItemDetail
