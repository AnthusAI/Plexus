"use client"

import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"

interface ArtifactEditorProps {
  artifact: any
  artifactType: string
  onChange: (edited: any) => void
  disabled?: boolean
}

/**
 * Artifact Editor Component
 *
 * Allows inline editing of review artifacts with JSON validation.
 * Currently uses a textarea with JSON formatting - can be upgraded to Monaco editor later.
 */
export function ArtifactEditor({ artifact, artifactType, onChange, disabled = false }: ArtifactEditorProps) {
  const [editedArtifact, setEditedArtifact] = useState(artifact)
  const [isEditing, setIsEditing] = useState(false)
  const [editedJson, setEditedJson] = useState(JSON.stringify(artifact, null, 2))
  const [jsonError, setJsonError] = useState<string | null>(null)

  const handleJsonChange = (value: string) => {
    setEditedJson(value)

    // Try to parse JSON
    try {
      const parsed = JSON.parse(value)
      setJsonError(null)
      setEditedArtifact(parsed)
      onChange(parsed)
    } catch (e) {
      setJsonError(e instanceof Error ? e.message : 'Invalid JSON')
      // Don't update editedArtifact or call onChange if JSON is invalid
    }
  }

  const toggleEditMode = () => {
    if (isEditing) {
      // Switching from edit to view - make sure JSON is valid
      if (jsonError) {
        // Don't allow switching if there's an error
        return
      }
    } else {
      // Switching from view to edit - reset JSON string from current artifact
      setEditedJson(JSON.stringify(editedArtifact, null, 2))
      setJsonError(null)
    }
    setIsEditing(!isEditing)
  }

  return (
    <div className="space-y-2 border rounded-lg p-4 bg-muted/30">
      <div className="flex items-center justify-between">
        <div>
          <Label>Artifact</Label>
          {artifactType && (
            <p className="text-xs text-muted-foreground mt-1">
              Type: {artifactType}
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={toggleEditMode}
          disabled={disabled || (isEditing && jsonError !== null)}
        >
          {isEditing ? 'View Only' : 'Edit'}
        </Button>
      </div>

      {isEditing ? (
        <div className="space-y-2">
          <Textarea
            value={editedJson}
            onChange={(e) => handleJsonChange(e.target.value)}
            disabled={disabled}
            className="font-mono text-sm min-h-[200px]"
            placeholder="Edit JSON artifact..."
          />
          {jsonError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                JSON Error: {jsonError}
              </AlertDescription>
            </Alert>
          )}
          <p className="text-xs text-muted-foreground">
            Edit the JSON above. Changes will be included in your response.
          </p>
        </div>
      ) : (
        <pre className="p-3 bg-background rounded text-sm overflow-auto max-h-[300px]">
          {JSON.stringify(editedArtifact, null, 2)}
        </pre>
      )}
    </div>
  )
}
