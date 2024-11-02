"use client"
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Plus, X, Square, Columns2 } from "lucide-react"
import { generateClient } from "aws-amplify/data"
import { generateClient as generateGraphQLClient } from '@aws-amplify/api'
import type { Schema } from "@/amplify/data/resource"
import { EditableField } from "@/components/ui/editable-field"
import { ScoreItem } from "../score-item"

const client = generateClient<Schema>()
const graphqlClient = generateGraphQLClient()

interface ScorecardFormProps {
  scorecard: Schema['Scorecard']['type'] | null
  accountId: string
  onSave: () => void
  onCancel: () => void
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
  externalId: string
  sections: Array<{
    id?: string
    name: string
    order: number
    scores: Array<{
      id: string
      name: string
      type: string
      order: number
      accuracy: number
      version: string
      timestamp: Date
      aiProvider?: string
      aiModel?: string
      isFineTuned?: boolean
      configuration?: any
      distribution: Array<{ category: string; value: number }>
      versionHistory: Array<{
        version: string
        parent: string | null
        timestamp: Date
        accuracy: number
        distribution: Array<{ category: string; value: number }>
      }>
    }>
  }>
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

  useEffect(() => {
    if (scorecard) {
      setFormData(initializeFormData(scorecard, accountId))
    }
  }, [scorecard, accountId])

  function initializeFormData(scorecard: Schema['Scorecard']['type'] | null, accountId: string): FormData {
    const defaultData: FormData = {
      name: "",
      key: "",
      description: "",
      accountId,
      externalId: "",
      sections: []
    }

    if (!scorecard) return defaultData

    return {
      id: scorecard.id,
      name: scorecard.name,
      key: scorecard.key,
      description: scorecard.description ?? "",
      externalId: scorecard.externalId,
      accountId,
      sections: [] // Sections will be loaded separately via the relationship
    }
  }

  async function handleSave() {
    try {
      if (formData.id) {
        // Update existing scorecard
        await client.models.Scorecard.update({
          id: formData.id,
          name: formData.name,
          key: formData.key,
          description: formData.description,
          externalId: formData.externalId
        })
        
        // Update sections
        for (const section of formData.sections) {
          if (section.id) {
            await client.models.ScorecardSection.update({
              id: section.id,
              name: section.name,
              order: section.order
            })
          } else {
            await client.models.ScorecardSection.create({
              name: section.name,
              order: section.order,
              scorecardId: formData.id
            })
          }
        }
      } else {
        // Create new scorecard
        if (!formData.externalId?.trim()) {
          throw new Error('External ID is required')
        }

        const scorecardResult = await client.models.Scorecard.create({
          name: formData.name,
          key: formData.key,
          description: formData.description,
          accountId: formData.accountId,
          externalId: formData.externalId.trim()
        })
        
        if (!scorecardResult.data) {
          throw new Error('Failed to create scorecard')
        }

        // Create sections
        for (const section of formData.sections) {
          const sectionResult = await client.models.ScorecardSection.create({
            name: section.name,
            order: section.order,
            scorecardId: scorecardResult.data.id
          })
          
          if (!sectionResult.data) continue

          // Create scores
          for (const score of section.scores) {
            await client.models.Score.create({
              name: score.name,
              type: score.type,
              order: score.order,
              sectionId: sectionResult.data.id,
              accuracy: score.accuracy,
              version: score.version,
              aiProvider: score.aiProvider,
              aiModel: score.aiModel,
              isFineTuned: score.isFineTuned,
              configuration: score.configuration,
              distribution: score.distribution,
              versionHistory: score.versionHistory
            })
          }
        }
      }
      
      onSave()
    } catch (error) {
      console.error('Operation failed:', error)
      throw error
    }
  }

  const handleAddSection = () => {
    const maxOrder = Math.max(0, ...formData.sections.map(s => s.order))
    const newSection = {
      name: "New section",
      order: maxOrder + 1,
      scores: []
    }
    setFormData({
      ...formData,
      sections: [...formData.sections, newSection]
    })
  }

  const handleAddScore = (sectionIndex: number) => {
    const baseAccuracy = Math.floor(Math.random() * 30) + 60
    const section = formData.sections[sectionIndex]
    const maxOrder = Math.max(0, ...section.scores.map(s => s.order))
    const now = new Date()
    
    const newScore = {
      id: `temp_${Date.now()}`,
      name: "New Score",
      type: "Boolean",
      order: maxOrder + 1,
      accuracy: baseAccuracy,
      version: Date.now().toString(),
      timestamp: now,
      aiProvider: "OpenAI",
      aiModel: "gpt-4-turbo",
      isFineTuned: false,
      configuration: {},
      distribution: [
        { category: "Positive", value: baseAccuracy },
        { category: "Negative", value: 100 - baseAccuracy }
      ],
      versionHistory: [{
        version: Date.now().toString(),
        parent: null,
        timestamp: now,
        accuracy: baseAccuracy,
        distribution: [
          { category: "Positive", value: baseAccuracy },
          { category: "Negative", value: 100 - baseAccuracy }
        ]
      }]
    }
    const updatedScoreDetails = [...formData.sections]
    updatedScoreDetails[sectionIndex].scores.push(newScore)
    setFormData({
      ...formData,
      sections: updatedScoreDetails
    })
  }

  // Add this function to test direct GraphQL update
  async function testGraphQLUpdate() {
    if (!scorecard?.id) return;
    
    try {
      const updateMutation = `
        mutation UpdateScorecard($input: UpdateScorecardInput!) {
          updateScorecard(input: $input) {
            id
            foreignId
          }
        }
      `;

      const variables = {
        input: {
          id: scorecard.id,
          foreignId: "test123"
        }
      };

      console.log('Testing GraphQL update:', variables);
      const response = await graphqlClient.graphql({ 
        query: updateMutation,
        variables 
      });
      console.log('GraphQL response:', response);
    } catch (error) {
      console.error('GraphQL update failed:', error);
    }
  }

  return (
    <div className="border text-card-foreground shadow rounded-none 
                    sm:rounded-lg h-full flex flex-col bg-card-light border-none">
      {/* Header */}
      <div className="flex-shrink-0 bg-card">
        <div className="px-6 py-4 flex items-center justify-between">
          <Input
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="text-3xl font-semibold bg-background border-0 px-2 h-auto 
                       focus-visible:ring-0 focus-visible:ring-offset-0 
                       placeholder:text-muted-foreground rounded-md flex-1 mr-4"
            placeholder="Scorecard Name"
          />
          <div className="flex items-center flex-shrink-0">
            {!isNarrowViewport && onToggleWidth && (
              <Button variant="ghost" size="icon" onClick={onToggleWidth}>
                {isFullWidth ? <Columns2 className="h-4 w-4" /> : <Square className="h-4 w-4" />}
              </Button>
            )}
            <Button variant="ghost" size="icon" onClick={onCancel} className="ml-2">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="px-6 pb-6">
          <div className="flex gap-4">
            <Input
              value={formData.externalId ?? ''}
              onChange={(e) => setFormData({ ...formData, externalId: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto 
                         focus-visible:ring-0 focus-visible:ring-offset-0 
                         placeholder:text-muted-foreground rounded-md"
              placeholder="External ID"
            />
            <Input
              value={formData.key}
              onChange={(e) => setFormData({ ...formData, key: e.target.value })}
              className="font-mono bg-background border-0 px-2 h-auto 
                         focus-visible:ring-0 focus-visible:ring-offset-0 
                         placeholder:text-muted-foreground rounded-md"
              placeholder="scorecard-key"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="space-y-4">
          <div className="mt-8">
            {formData.sections.map((section, sectionIndex) => (
              <div key={sectionIndex} className="mb-6">
                <div className="-mx-4 sm:-mx-6 mb-4">
                  <div className="bg-card px-4 sm:px-6 py-2">
                    <EditableField
                      value={section.name}
                      onChange={(value: string) => {
                        const updatedScoreDetails = [...formData.sections]
                        updatedScoreDetails[sectionIndex] = { ...section, name: value }
                        setFormData({ ...formData, sections: updatedScoreDetails })
                      }}
                      className="text-md font-semibold"
                    />
                  </div>
                </div>
                <div>
                  {section.scores.map((score, scoreIndex) => (
                    <ScoreItem
                      key={scoreIndex}
                      score={score}
                      onEdit={() => {
                        const updatedScoreDetails = [...formData.sections]
                        updatedScoreDetails[sectionIndex].scores[scoreIndex] = {
                          ...score,
                          name: score.name
                        }
                        setFormData({ ...formData, sections: updatedScoreDetails })
                      }}
                    />
                  ))}
                </div>
                <div className="mt-4">
                  <Button variant="outline" onClick={() => handleAddScore(sectionIndex)}>
                    <Plus className="mr-2 h-4 w-4" /> Create Score
                  </Button>
                </div>
              </div>
            ))}
            <div className="mt-6">
              <Button variant="outline" onClick={handleAddSection}>
                <Plus className="mr-2 h-4 w-4" /> Create Section
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex-shrink-0 p-6 bg-card rounded-b-lg">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={handleSave}>Save Scorecard</Button>
        </div>
      </div>
    </div>
  )
}