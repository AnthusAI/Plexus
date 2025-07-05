/**
 * React Hook for YAML Linting Integration
 * 
 * Provides debounced YAML linting and Monaco editor integration.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { editor, Monaco } from 'monaco-editor'
import { createLinterForContext } from '@/lib/yaml-linter-schemas'
import type { LintResult, LintMessage } from '@/lib/yaml-linter'

interface UseYamlLinterOptions {
  /** The type of YAML being edited */
  context: 'score' | 'data-source'
  /** Debounce delay in milliseconds */
  debounceMs?: number
  /** Whether to automatically show Monaco markers */
  showMonacoMarkers?: boolean
}

interface UseYamlLinterReturn {
  /** Current linting result */
  lintResult: LintResult | null
  /** Whether linting is in progress */
  isLinting: boolean
  /** Manually trigger linting */
  lint: (yamlContent: string) => void
  /** Set up Monaco editor integration */
  setupMonacoIntegration: (editor: editor.IStandaloneCodeEditor, monaco: Monaco) => void
  /** Jump to a specific line in the Monaco editor */
  jumpToLine: (line: number, column?: number) => void
}

export function useYamlLinter({
  context,
  debounceMs = 500,
  showMonacoMarkers = true
}: UseYamlLinterOptions): UseYamlLinterReturn {
  const [lintResult, setLintResult] = useState<LintResult | null>(null)
  const [isLinting, setIsLinting] = useState(false)
  
  const linterRef = useRef(createLinterForContext(context))
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  const monacoRef = useRef<Monaco | null>(null)
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Update linter when context changes
  useEffect(() => {
    linterRef.current = createLinterForContext(context)
  }, [context])

  // Convert lint messages to Monaco markers
  const convertToMonacoMarkers = useCallback((messages: LintMessage[]): editor.IMarkerData[] => {
    return messages
      .filter(msg => msg.line !== undefined && msg.line !== null)
      .map(msg => ({
        severity: msg.level === 'error' 
          ? 8 // MarkerSeverity.Error
          : msg.level === 'warning' 
          ? 4 // MarkerSeverity.Warning
          : 1, // MarkerSeverity.Hint
        startLineNumber: msg.line!,
        startColumn: msg.column || 1,
        endLineNumber: msg.line!,
        endColumn: msg.column ? msg.column + 10 : 1000, // Highlight the whole line if no column
        message: `${msg.title}: ${msg.message}${msg.suggestion ? `\n💡 ${msg.suggestion}` : ''}`,
        code: msg.code,
        source: 'yaml-linter'
      }))
  }, [])

  // Perform linting
  const performLint = useCallback(async (yamlContent: string) => {
    setIsLinting(true)
    
    try {
      // Run linting in a microtask to avoid blocking the UI
      await new Promise(resolve => setTimeout(resolve, 0))
      
      const result = linterRef.current.lint(yamlContent)
      setLintResult(result)

      // Update Monaco markers if editor is available
      if (showMonacoMarkers && editorRef.current && monacoRef.current) {
        const model = editorRef.current.getModel()
        if (model) {
          const markers = convertToMonacoMarkers(result.messages)
          monacoRef.current.editor.setModelMarkers(model, 'yaml-linter', markers)
        }
      }
    } catch (error) {
      console.error('Error during YAML linting:', error)
      // Create an error result
      const errorResult: LintResult = {
        is_valid: false,
        messages: [{
          level: 'error',
          code: 'LINTER_ERROR',
          title: 'Linting Error',
          message: `An error occurred during linting: ${error instanceof Error ? error.message : String(error)}`,
          suggestion: 'Please check your YAML syntax or report this as a bug.'
        }],
        error_count: 1,
        warning_count: 0,
        info_count: 0
      }
      setLintResult(errorResult)
    } finally {
      setIsLinting(false)
    }
  }, [convertToMonacoMarkers, showMonacoMarkers])

  // Debounced lint function
  const lint = useCallback((yamlContent: string) => {
    // Clear existing timeout
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current)
    }

    // Set new timeout
    debounceTimeoutRef.current = setTimeout(() => {
      performLint(yamlContent)
    }, debounceMs)
  }, [performLint, debounceMs])

  // Set up Monaco editor integration
  const setupMonacoIntegration = useCallback((editor: editor.IStandaloneCodeEditor, monaco: Monaco) => {
    editorRef.current = editor
    monacoRef.current = monaco

    // Set up onChange handler for automatic linting
    const disposable = editor.onDidChangeModelContent(() => {
      const content = editor.getValue()
      if (content.trim()) {
        lint(content)
      } else {
        // Clear results for empty content
        setLintResult(null)
        if (showMonacoMarkers) {
          const model = editor.getModel()
          if (model) {
            monaco.editor.setModelMarkers(model, 'yaml-linter', [])
          }
        }
      }
    })

    // Initial lint if there's content
    const initialContent = editor.getValue()
    if (initialContent.trim()) {
      lint(initialContent)
    }

    // Return cleanup function
    return () => {
      disposable.dispose()
      editorRef.current = null
      monacoRef.current = null
    }
  }, [lint, showMonacoMarkers])

  // Jump to line function
  const jumpToLine = useCallback((line: number, column = 1) => {
    if (editorRef.current) {
      editorRef.current.revealLineInCenter(line)
      editorRef.current.setPosition({ lineNumber: line, column })
      editorRef.current.focus()
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current)
      }
    }
  }, [])

  return {
    lintResult,
    isLinting,
    lint,
    setupMonacoIntegration,
    jumpToLine
  }
}

// Utility hook for handling lint message clicks
export function useLintMessageHandler(jumpToLine: (line: number, column?: number) => void) {
  return useCallback((message: LintMessage) => {
    if (message.line !== undefined && message.line !== null) {
      jumpToLine(message.line, message.column)
    }
  }, [jumpToLine])
}