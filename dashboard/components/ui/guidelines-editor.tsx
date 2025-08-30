import * as React from 'react'
import { Button } from '@/components/ui/button'
import { CardButton } from '@/components/CardButton'
import { Edit, Expand, X, FileText, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import Editor from "@monaco-editor/react"
import { defineCustomMonacoThemes, applyMonacoTheme, setupMonacoThemeWatcher, getCommonMonacoOptions } from '@/lib/monaco-theme'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

interface GuidelinesEditorProps {
  guidelines?: string
  isEditing?: boolean
  isExpanded?: boolean
  onToggleExpanded?: () => void
  onStartInlineEdit?: () => void
  onOpenFullscreenEditor?: () => void
  onGuidelinesChange?: (value: string) => void
  onSaveGuidelines?: () => void
  onCancelEdit?: () => void
  hasChanges?: boolean
  isSaving?: boolean
  className?: string
  title?: string
}

interface FullscreenGuidelinesEditorProps {
  isOpen: boolean
  title: string
  value: string
  onChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
  hasChanges: boolean
  isSaving: boolean
}

export const GuidelinesEditor = React.memo(({
  guidelines,
  isEditing = false,
  isExpanded = false,
  onToggleExpanded,
  onStartInlineEdit,
  onOpenFullscreenEditor,
  onGuidelinesChange,
  onSaveGuidelines,
  onCancelEdit,
  hasChanges = false,
  isSaving = false,
  className,
  title = "Guidelines"
}: GuidelinesEditorProps) => {
  return (
    <div className={cn("mb-6", className)}>
      {/* Header with action buttons - always visible */}
      <div className="flex justify-between items-center mb-3">
        <h3 className="text-sm font-medium">{title}</h3>
        <div className="flex gap-1">
          {!isEditing && onStartInlineEdit && (
            <CardButton
              icon={Edit}
              onClick={onStartInlineEdit}
              aria-label="Edit guidelines inline"
            />
          )}
          {onOpenFullscreenEditor && (
            <CardButton
              icon={Expand}
              onClick={onOpenFullscreenEditor}
              aria-label="Open guidelines editor"
            />
          )}
        </div>
      </div>
      
      {/* Guidelines content */}
      {isEditing ? (
        // Inline editing mode - show ~12 lines
        <div className="space-y-3">
          <div className="rounded-lg bg-background overflow-hidden border-0 ring-2 ring-transparent focus-within:ring-ring">
            <Editor
              height="300px"
              defaultLanguage="markdown"
              value={guidelines || ''}
              onChange={(value) => onGuidelinesChange?.(value || '')}
              onMount={(editor, monaco) => {
                // Configure Monaco editor
                defineCustomMonacoThemes(monaco)
                applyMonacoTheme(monaco)
                setupMonacoThemeWatcher(monaco)
              }}
              options={{
                ...getCommonMonacoOptions(),
                wordWrap: 'on',
                lineNumbers: 'off',
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                fontSize: 14,
                tabSize: 2,
                insertSpaces: true,
                automaticLayout: true,
              }}
            />
          </div>
        </div>
      ) : guidelines && guidelines.trim() !== '' ? (
        // Display mode with markdown rendering and expand/collapse
        <div 
          className="rounded-lg bg-background p-4 cursor-pointer transition-all duration-200 hover:bg-accent/10"
          onClick={() => onToggleExpanded?.()}
        >
          <div 
            className={cn(
              "prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-muted-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground transition-all duration-200",
              !isExpanded && "overflow-hidden"
            )}
            style={!isExpanded ? { 
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              maxHeight: '5.25rem'
            } : {}}
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              components={{
                p: ({ children }) => <p className="mb-3 last:mb-0 text-muted-foreground leading-relaxed">{children}</p>,
                ul: ({ children }) => <ul className="list-disc pl-6 mb-3 space-y-1">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-6 mb-3 space-y-1">{children}</ol>,
                li: ({ children }) => <li className="text-muted-foreground">{children}</li>,
                strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                code: ({ children }) => <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono text-foreground">{children}</code>,
                pre: ({ children }) => <pre className="bg-muted p-3 rounded overflow-x-auto mb-3">{children}</pre>,
                blockquote: ({ children }) => <blockquote className="border-l-4 border-muted pl-4 italic text-muted-foreground mb-3">{children}</blockquote>,
                h1: ({ children }) => <h1 className="text-base font-semibold mb-2 text-foreground">{children}</h1>,
                h2: ({ children }) => <h2 className="text-sm font-semibold mb-2 text-foreground">{children}</h2>,
                h3: ({ children }) => <h3 className="text-sm font-medium mb-1 text-foreground">{children}</h3>,
              }}
            >
              {guidelines}
            </ReactMarkdown>
          </div>
          {/* Expand/Collapse indicator */}
          <div className="mt-3 flex flex-col items-center">
            <div className="w-full h-px bg-muted"></div>
            <div className="mt-1">
              {!isExpanded ? (
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              ) : (
                <ChevronUp className="h-3 w-3 text-muted-foreground" />
              )}
            </div>
          </div>
        </div>
      ) : (
        // No guidelines placeholder
        <div className="rounded-lg bg-background p-4 text-center py-8 text-muted-foreground text-sm">
          No guidelines.
        </div>
      )}
    </div>
  )
})

GuidelinesEditor.displayName = 'GuidelinesEditor'

export const FullscreenGuidelinesEditor = React.memo(({
  isOpen,
  title,
  value,
  onChange,
  onSave,
  onCancel,
  hasChanges,
  isSaving
}: FullscreenGuidelinesEditorProps) => {
  const previewRef = React.useRef<HTMLDivElement>(null)
  const editorRef = React.useRef<any>(null)

  // Synchronized scrolling handler
  const handleEditorScroll = React.useCallback(() => {
    if (!editorRef.current || !previewRef.current) return
    
    const editor = editorRef.current
    const preview = previewRef.current
    
    // Get scroll position as percentage of total scrollable height
    const scrollTop = editor.getScrollTop()
    const scrollHeight = editor.getScrollHeight()
    const clientHeight = editor.getLayoutInfo().height
    const maxScroll = scrollHeight - clientHeight
    
    if (maxScroll <= 0) return
    
    const scrollPercentage = scrollTop / maxScroll
    
    // Apply the same scroll percentage to preview
    const previewMaxScroll = preview.scrollHeight - preview.clientHeight
    if (previewMaxScroll > 0) {
      preview.scrollTop = scrollPercentage * previewMaxScroll
    }
  }, [])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 bg-card">
      <div className="flex flex-col h-full p-4">
        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold">{title}</h2>
          </div>
          <CardButton
            icon={X}
            onClick={hasChanges ? onCancel : onCancel}
            aria-label="Close"
          />
        </div>

        {/* Split Editor and Preview - Two rounded rectangles */}
        <div className="flex-1 flex gap-4 overflow-hidden">
          {/* Editor Card */}
          <div className="flex-1 flex flex-col bg-background rounded-lg overflow-hidden">
            <div className="px-4 py-2 bg-card-selected text-sm font-medium text-muted-foreground">
              Markdown Editor
            </div>
            <div className="flex-1 overflow-hidden">
              <Editor
                height="100%"
                defaultLanguage="markdown"
                value={value}
                onChange={(value) => onChange(value || '')}
                onMount={(editor, monaco) => {
                  // Store editor reference for scroll synchronization
                  editorRef.current = editor
                  
                  // Configure Monaco editor
                  defineCustomMonacoThemes(monaco)
                  applyMonacoTheme(monaco)
                  setupMonacoThemeWatcher(monaco)
                  
                  // Set up scroll synchronization
                  editor.onDidScrollChange(handleEditorScroll)
                }}
                options={{
                  ...getCommonMonacoOptions(),
                  wordWrap: 'on',
                  lineNumbers: 'off',
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  fontSize: 14,
                  tabSize: 2,
                  insertSpaces: true,
                  automaticLayout: true,
                }}
              />
            </div>
          </div>

          {/* Preview Card */}
          <div className="flex-1 flex flex-col bg-background rounded-lg overflow-hidden">
            <div className="px-4 py-2 bg-card-selected text-sm font-medium text-muted-foreground">
              Preview
            </div>
            <div ref={previewRef} className="flex-1 overflow-y-auto p-4">
              {value ? (
                <div className="prose prose-sm max-w-none prose-headings:text-foreground prose-p:text-muted-foreground prose-strong:text-foreground prose-code:text-foreground prose-pre:bg-muted prose-pre:text-foreground">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    components={{
                      // Customize components for better styling
                      p: ({ children }) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                      ul: ({ children }) => <ul className="mb-2 ml-4 list-disc">{children}</ul>,
                      ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal">{children}</ol>,
                      li: ({ children }) => <li className="mb-1">{children}</li>,
                      strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
                      em: ({ children }) => <em className="italic">{children}</em>,
                      code: ({ children }) => <code className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                      pre: ({ children }) => <pre className="bg-muted p-2 rounded overflow-x-auto text-xs">{children}</pre>,
                      h1: ({ children }) => <h1 className="text-base font-semibold mb-2 text-foreground">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-sm font-semibold mb-2 text-foreground">{children}</h2>,
                      h3: ({ children }) => <h3 className="text-sm font-medium mb-1 text-foreground">{children}</h3>,
                    }}
                  >
                    {value}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                  Start typing to see preview...
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer with save/cancel buttons if changes exist */}
        {hasChanges && (
          <div className="flex justify-end items-center gap-2 pt-4">
            <Button
              variant="outline"
              onClick={onCancel}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button
              onClick={onSave}
              disabled={isSaving}
            >
              {isSaving ? (
                <>
                  <div className="animate-spin h-4 w-4 border-2 border-background border-t-transparent rounded-full mr-2" />
                  Saving Guidelines...
                </>
              ) : (
                'Save Guidelines'
              )}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
})

FullscreenGuidelinesEditor.displayName = 'FullscreenGuidelinesEditor'
