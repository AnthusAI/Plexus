import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { CardButton } from '@/components/CardButton'
import { X, Plus, ChevronDown, ChevronRight } from 'lucide-react'
import type { Schema } from '@/amplify/data/resource'

interface SectionFormState {
  id?: string
  name: string
  order: number
  scores: any[]
}

interface ScorecardFormProps {
  scorecard: Schema['Scorecard']['type'] | null
  accountId: string
  onSave?: (formData: FormData) => Promise<void>
  onCancel?: () => void
  isFullWidth?: boolean
  onToggleWidth?: () => void
  isNarrowViewport?: boolean
}

interface FormData {
  id?: string
  name: string
  key: string
  description: string
  accountId: string
  externalId?: string
  sections: SectionFormState[]
  examples: string[] // Array to store example items
}

function initializeFormData(scorecard: Schema['Scorecard']['type'] | null, accountId: string): FormData {
  console.log('Initializing form data with scorecard:', scorecard)
  
  const defaultData: FormData = {
    name: "",
    key: "",
    description: "",
    accountId,
    externalId: "",
    sections: [],
    examples: [] // Initialize empty examples array
  }

  if (!scorecard) return defaultData

  return {
    id: scorecard.id,
    name: scorecard.name,
    key: scorecard.key,
    description: scorecard.description ?? "",
    externalId: scorecard.externalId ?? "",
    accountId,
    sections: [],  // We'll load sections through the useEffect
    examples: [] // Initialize empty examples array
  }
}

export function ScorecardForm({ 
  scorecard, 
  accountId, 
  onSave, 
  onCancel,
  isFullWidth = false,
  onToggleWidth,
  isNarrowViewport = false
}: ScorecardFormProps) {
  const [formData, setFormData] = useState<FormData>(() => initializeFormData(scorecard, accountId))
  const [sectionToDelete, setSectionToDelete] = useState<number | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isExamplesExpanded, setIsExamplesExpanded] = useState(false)

  const handleAddExample = () => {
    setFormData({
      ...formData,
      examples: [...formData.examples, "New example item"]
    })
    setIsExamplesExpanded(true)
  }

  const handleSave = async () => {
    if (!formData || !accountId) {
      console.log('Missing formData or accountId:', { formData, accountId })
      return
    }
    
    try {
      setIsSaving(true)
      console.log('Starting save with formData:', formData)
      
      // Log examples for future implementation
      console.log('Examples to be saved:', formData.examples)
      
      // TODO: Implement actual save logic here
      // For now, just call the onSave callback
      if (onSave) {
        await onSave(formData)
      }
      
    } catch (error) {
      console.error('Error saving scorecard:', error)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="border text-card-foreground shadow rounded-lg h-full flex flex-col bg-card-light border-none">
      {/* Header */}
      <div className="flex-shrink-0 bg-card rounded-t-lg">
        {/* ... existing header code ... */}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="space-y-8">
          {/* Examples Section */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <div className="flex items-center">
                <h2 
                  className="text-2xl font-semibold cursor-pointer flex items-center"
                  onClick={() => setIsExamplesExpanded(!isExamplesExpanded)}
                >
                  Example Items
                  <span className="ml-2 text-muted-foreground text-base font-normal">
                    ({formData.examples.length})
                  </span>
                  {isExamplesExpanded ? (
                    <ChevronDown className="h-4 w-4 ml-2 text-muted-foreground" />
                  ) : (
                    <ChevronRight className="h-4 w-4 ml-2 text-muted-foreground" />
                  )}
                </h2>
              </div>
              <CardButton
                icon={Plus}
                label="Add Example"
                onClick={handleAddExample}
              />
            </div>
            
            {isExamplesExpanded && (
              <div className="mb-2">
                {formData.examples.length === 0 ? (
                  <div className="text-center text-muted-foreground py-4">
                    <p>No example items yet</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {/* Examples list will go here */}
                    {formData.examples.map((example, index) => (
                      <div key={index} className="flex items-center justify-between p-2 bg-background rounded-md">
                        <span>{example}</span>
                        <Button variant="ghost" size="icon" onClick={() => {
                          const updatedExamples = [...formData.examples];
                          updatedExamples.splice(index, 1);
                          setFormData({
                            ...formData,
                            examples: updatedExamples
                          });
                        }}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            <hr className="mb-4" />
          </div>

          {/* Sections list */}
          {/* ... existing sections code ... */}
        </div>
      </div>
    </div>
  )
} 