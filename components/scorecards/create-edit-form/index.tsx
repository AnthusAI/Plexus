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
  scorecard?: Schema['Scorecard']['type']
  accountId: string
  onSave: () => void
  onCancel: () => void
  isFullWidth?: boolean
  onToggleWidth?: () => void
  isNarrowViewport?: boolean
}

interface ScoreSection {
  name: string;
  scores: Array<{
    id: string;
    name: string;
    type: string;
    accuracy: number;
    version: string;
    timestamp: Date;
    distribution: Array<{ category: string; value: number }>;
    versionHistory: Array<any>; // We can make this more specific if needed
  }>;
}

interface FormData {
  name: string;
  key: string;
  description: string;
  accountId: string;
  externalId: string;
  scoreDetails: ScoreSection[];
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
  const [formData, setFormData] = useState<FormData>(() => initializeFormData(scorecard, accountId));

  useEffect(() => {
    console.log('Scorecard prop:', scorecard);
    console.log('Form data:', formData);
  }, [scorecard, formData]);

  useEffect(() => {
    if (scorecard) {
      setFormData(initializeFormData(scorecard, accountId));
    }
  }, [scorecard, accountId]);

  function initializeFormData(scorecard: Schema['Scorecard']['type'] | undefined, accountId: string): FormData {
    const defaultData: FormData = {
      name: "",
      key: "",
      description: "",
      accountId,
      externalId: "",
      scoreDetails: []
    };

    if (scorecard) {
      console.log('Initializing form with scorecard:', {
        raw: scorecard,
        externalId: scorecard.externalId,
        keys: Object.keys(scorecard)
      });

      const parsedDetails = scorecard.scoreDetails ? 
        (typeof scorecard.scoreDetails === 'string' ? 
          JSON.parse(scorecard.scoreDetails) : 
          scorecard.scoreDetails) : 
        [];

      const formData = {
        name: scorecard.name ?? defaultData.name,
        key: scorecard.key ?? defaultData.key,
        description: scorecard.description ?? defaultData.description,
        externalId: scorecard.externalId ?? defaultData.externalId,
        accountId,
        scoreDetails: parsedDetails
      };

      console.log('Initialized form data:', formData);
      return formData;
    }

    return defaultData;
  }

  async function handleSave() {
    try {
      if (scorecard?.id) {
        try {
          const { name, key, accountId, scoreDetails } = formData
          
          const updateInput = {
            id: scorecard.id,
            name,
            key,
            accountId,
            scoreDetails: JSON.stringify(scoreDetails)
          } as const
          
          console.log('Sending update:', updateInput)
          
          const result = await client.models.Scorecard.update(updateInput)
          
          console.log('Update result:', result)
          
          if (result.errors) {
            throw new Error(result.errors.map(e => e.message).join(', '))
          }
          
          onSave()
        } catch (updateError) {
          console.error('Update failed:', updateError)
          throw updateError
        }
      } else {
        // For create, externalId is required
        if (!formData.externalId?.trim()) {
          throw new Error('External ID is required')
        }

        const createInput = {
          name: formData.name,
          key: formData.key,
          accountId: formData.accountId,
          externalId: formData.externalId.trim(),
          scoreDetails: JSON.stringify(formData.scoreDetails)
        } as const
        
        console.log('Sending create:', createInput)
        
        const result = await client.models.Scorecard.create(createInput)
        console.log('Create result:', result)
        
        if (result.errors) {
          throw new Error('Create failed: ' + 
            result.errors.map(e => e.message).join(', '))
        }
        
        onSave()
      }
    } catch (error) {
      console.error('Operation failed:', error)
      throw error
    }
  }

  const handleAddSection = () => {
    const newSection = {
      name: "New section",
      scores: []
    }
    setFormData({
      ...formData,
      scoreDetails: [...formData.scoreDetails, newSection]
    })
  }

  const handleAddScore = (sectionIndex: number) => {
    const baseAccuracy = Math.floor(Math.random() * 30) + 60
    const newScore = {
      id: Date.now().toString(),
      name: "New Score",
      type: "Boolean",
      accuracy: baseAccuracy,
      version: Date.now().toString(),
      timestamp: new Date(),
      distribution: [
        { category: "Positive", value: baseAccuracy },
        { category: "Negative", value: 100 - baseAccuracy }
      ],
      versionHistory: [{
        version: Date.now().toString(),
        parent: null,
        timestamp: new Date(),
        accuracy: baseAccuracy,
        distribution: [
          { category: "Positive", value: baseAccuracy },
          { category: "Negative", value: 100 - baseAccuracy }
        ]
      }],
      aiProvider: "OpenAI",
      aiModel: "gpt-4-turbo",
      isFineTuned: false
    }
    const updatedScoreDetails = [...formData.scoreDetails]
    updatedScoreDetails[sectionIndex].scores.push(newScore)
    setFormData({
      ...formData,
      scoreDetails: updatedScoreDetails
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
      <div className="flex-shrink-0 border-b">
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
            <div className="-mx-4 sm:-mx-6 mb-4">
              <div className="px-4 sm:px-6 py-2">
                <h4 className="text-md font-semibold">Scores</h4>
              </div>
            </div>
            {formData.scoreDetails.map((section, sectionIndex) => (
              <div key={sectionIndex} className="mb-6">
                <div className="-mx-4 sm:-mx-6 mb-4">
                  <div className="bg-card px-4 sm:px-6 py-2">
                    <EditableField
                      value={section.name}
                      onChange={(value) => {
                        const updatedScoreDetails = [...formData.scoreDetails]
                        updatedScoreDetails[sectionIndex] = { ...section, name: value }
                        setFormData({ ...formData, scoreDetails: updatedScoreDetails })
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
                        const updatedScoreDetails = [...formData.scoreDetails]
                        updatedScoreDetails[sectionIndex].scores[scoreIndex] = {
                          ...score,
                          name: score.name
                        }
                        setFormData({ ...formData, scoreDetails: updatedScoreDetails })
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
      <div className="flex-shrink-0 p-6 border-t bg-card rounded-b-lg">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button onClick={handleSave}>Save Scorecard</Button>
        </div>
      </div>
    </div>
  )
}