import type { Monaco } from '@monaco-editor/react'
import type { editor, CancellationToken } from 'monaco-editor'

/**
 * Helper function to get CSS variable value and convert it to hex format for Monaco
 */
const getCssVar = (name: string): string => {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  
  // If the value is an HSL color, convert it to hex
  if (value.startsWith('hsl(')) {
    // Create a temporary element to use the browser's color conversion
    const tempEl = document.createElement('div')
    tempEl.style.color = value
    document.body.appendChild(tempEl)
    const computedColor = getComputedStyle(tempEl).color
    document.body.removeChild(tempEl)
    
    // Convert rgb() format to hex
    if (computedColor.startsWith('rgb')) {
      const rgbValues = computedColor.match(/\d+/g)
      if (rgbValues && rgbValues.length >= 3) {
        const hex = rgbValues.slice(0, 3).map(x => {
          const hex = parseInt(x).toString(16)
          return hex.length === 1 ? '0' + hex : hex
        }).join('')
        return hex // Return without # prefix as Monaco requires
      }
    }
  }
  
  // If it's already a hex color, remove the # prefix
  if (value.startsWith('#')) {
    return value.substring(1)
  }
  
  return value
}

/**
 * Helper function to get CSS variable hex value for Monaco editor colors
 */
const getEditorColor = (cssVar: string): string => {
  return getCssVar(cssVar)
}

/**
 * Configure YAML language support with enhanced syntax highlighting and validation
 */
export const configureYamlLanguage = (monaco: Monaco): void => {
  // First, register YAML as a language if not already registered
  const registeredLanguages = monaco.languages.getLanguages();
  const yamlLanguageExists = registeredLanguages.some((lang: any) => lang.id === 'yaml');
  
  if (!yamlLanguageExists) {
    monaco.languages.register({ 
      id: 'yaml',
      extensions: ['.yaml', '.yml'],
      aliases: ['YAML', 'yaml', 'YML', 'yml'],
      mimetypes: ['application/x-yaml', 'text/x-yaml', 'text/yaml']
    });
    console.log('YAML language registered successfully');
  }

  // Register YAML language configuration
  monaco.languages.setLanguageConfiguration('yaml', {
    comments: {
      lineComment: '#',
    },
    brackets: [
      ['{', '}'],
      ['[', ']'],
      ['(', ')'],
    ],
    autoClosingPairs: [
      { open: '{', close: '}' },
      { open: '[', close: ']' },
      { open: '(', close: ')' },
      { open: '"', close: '"' },
      { open: "'", close: "'" },
    ],
    surroundingPairs: [
      { open: '{', close: '}' },
      { open: '[', close: ']' },
      { open: '(', close: ')' },
      { open: '"', close: '"' },
      { open: "'", close: "'" },
    ],
    indentationRules: {
      increaseIndentPattern: /^(\s*)(.*:(\s*$|\s+.*))/,
      decreaseIndentPattern: /^\s*[\}\]\)].*$/,
    },
  })
  console.log('YAML language configuration set');

  // Enhanced YAML tokenization rules for better syntax highlighting
  monaco.languages.setMonarchTokensProvider('yaml', {
    defaultToken: 'invalid',
    tokenPostfix: '.yaml',
    
    keywords: [
      'true', 'True', 'TRUE',
      'false', 'False', 'FALSE',
      'null', 'Null', 'NULL',
      'yes', 'Yes', 'YES',
      'no', 'No', 'NO',
      'on', 'On', 'ON',
      'off', 'Off', 'OFF'
    ],
    
    tokenizer: {
      root: [
        // Comments
        [/#.*$/, 'comment'],
        
        // Document separators
        [/^---\s*$/, 'tag'],
        [/^\.\.\.\s*$/, 'tag'],
        
        
        // Keys (including quoted keys) - more comprehensive pattern
        [/^\s*([a-zA-Z_][\w\-]*)\s*(?=:)/, 'key'],
        [/^\s*(['"])((?:[^'"]|\\.)*)(\1)\s*(?=:)/, ['delimiter', 'key', 'delimiter']],
        
        // Keys after array dashes (on same line as -)
        [/([a-zA-Z_][\w\-]*)\s*(?=:)/, 'key'],
        
        // Values after colons
        [/:\s*/, 'delimiter', '@value'],
        
        // Arrays - stay in root state to process keys properly
        [/^\s*-\s*/, 'delimiter.array'],
        
        // Everything else
        [/./, 'identifier'],
      ],
      
      value: [
        // Array items - pop back to root and process as array
        [/^\s*-\s*/, 'delimiter.array', '@pop'],
        
        // Keys in value context (for nested structures)
        [/^\s*([a-zA-Z_][\w\-]*)\s*(?=:)/, 'key', '@pop'],
        [/^\s*(['"])((?:[^'"]|\\.)*)(\1)\s*(?=:)/, ['delimiter', 'key', 'delimiter'], '@pop'],
        
        // Strings (single quoted)
        [/'([^'\\]|\\.)*'/, 'string', '@pop'],
        
        // Strings (double quoted)
        [/"([^"\\]|\\.)*"/, 'string', '@pop'],
        
        // Multiline strings (literal and folded)
        [/[\|>][-+]?\d*\s*$/, 'string.yaml', '@multiline'],
        
        // Numbers
        [/-?\d+\.?\d*([eE][-+]?\d+)?/, 'number', '@pop'],
        
        // Booleans and keywords
        [/\b(?:true|false|null|True|False|Null|TRUE|FALSE|NULL|yes|no|Yes|No|YES|NO|on|off|On|Off|ON|OFF|~)\b/, 'keyword', '@pop'],
        
        // Arrays and objects
        [/[\[\]{}]/, 'delimiter.bracket'],
        [/,/, 'delimiter.comma'],
        
        // Anchors and aliases
        [/&[a-zA-Z_][\w]*/, 'type', '@pop'],
        [/\*[a-zA-Z_][\w]*/, 'type', '@pop'],
        
        // Tags
        [/![a-zA-Z_][\w]*/, 'tag', '@pop'],
        
        // Newline ends value
        [/\n/, '', '@pop'],
        
        // Unquoted strings
        [/[^\n\r]+/, 'string', '@pop'],
      ],
      
      multiline: [
        // Exit multiline string when we encounter a YAML key (with colon) at base indentation or less
        // Specific pattern for user_message with multiline indicators
        [/^(\s*)(user_message)(\s*)(:)(\s*)([\|\>][-+]?\d*\s*)$/, ['', 'key', '', 'delimiter', '', 'string.yaml'], '@multiline'],
        [/^(\s*)([a-zA-Z_][\w\-]*)\s*:\s*([\|\>][-+]?\d*\s*)$/, ['', 'key', 'delimiter', 'string.yaml'], '@multiline'],
        [/^([a-zA-Z_][\w\-]*)\s*:/, 'key', '@pop'],
        [/^(\s*)([a-zA-Z_][\w\-]*)\s*:/, ['', 'key'], '@pop'],
        [/^(\s*)(['"])(.*?)\2\s*:/, ['', 'delimiter', 'key', 'delimiter'], '@pop'],
        // Exit multiline string for document separators
        [/^(---|\.\.\.)/, 'tag', '@pop'],
        // Exit multiline string for list items at base level only (not indented lists within the string)
        [/^-\s/, 'delimiter.array', '@pop'],
        // Exit multiline string for comments that start at beginning of line
        [/^\s*#.*$/, 'comment'],
        // Everything else in a multiline string is treated as string content (including quotes)
        [/^.*$/, 'string'],
      ],
    },
  })
  console.log('YAML tokenizer provider registered');

  // Set up YAML validation for indentation errors
  monaco.languages.registerDocumentFormattingEditProvider('yaml', {
    provideDocumentFormattingEdits: (model: editor.ITextModel) => {
      // Basic YAML formatting - mainly for indentation consistency
      const text = model.getValue()
      const lines = text.split('\n')
      const formattedLines: string[] = []
      
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        // Keep original line for now - could add more sophisticated formatting
        formattedLines.push(line)
      }
      
      return [{
        range: model.getFullModelRange(),
        text: formattedLines.join('\n')
      }]
    }
  })

  // Enhanced YAML diagnostics for indentation and syntax errors
  monaco.languages.registerDocumentSemanticTokensProvider('yaml', {
    getLegend: () => ({
      tokenTypes: ['comment', 'string', 'keyword', 'number', 'type', 'class', 'function'],
      tokenModifiers: ['declaration', 'documentation']
    }),
    provideDocumentSemanticTokens: (model: editor.ITextModel, lastResultId: string | null, token: CancellationToken) => {
      // This helps with better syntax highlighting
      const data: number[] = []
      return {
        data: new Uint32Array(data),
        resultId: undefined
      }
    },
    releaseDocumentSemanticTokens: (resultId: string) => {
      // Optional cleanup method - no action needed for our simple implementation
    }
  })

  // Register YAML validation - we'll call this from the editor onChange
  monaco.languages.onLanguage('yaml', () => {
    // This ensures the language is properly registered
    console.log('YAML language registered successfully')
  })
}

/**
 * Helper function to detect if a line contains a YAML key (not just any colon)
 */
const isYamlKeyLine = (line: string): boolean => {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('#')) return false
  
  // Skip document separators and list items
  if (trimmed.startsWith('---') || trimmed.startsWith('...') || trimmed.startsWith('- ')) return false
  
  // Look for key pattern: non-quoted key followed by colon and whitespace/end of line
  const keyPattern = /^(\s*)([^'"\s][^:]*?):\s*($|[^:])/
  const quotedKeyPattern = /^(\s*)(['"])(.*?)\2:\s*($|.)/
  
  return keyPattern.test(line) || quotedKeyPattern.test(line)
}

/**
 * Helper function to detect the predominant indentation pattern in a YAML document
 */
const detectIndentationPattern = (lines: string[]): number => {
  const indentSteps: number[] = []
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (!isYamlKeyLine(line)) continue
    
    const indentMatch = line.match(/^(\s*)/)
    const currentIndent = indentMatch ? indentMatch[1].length : 0
    
    // Look for the next key line at a deeper level
    for (let j = i + 1; j < lines.length; j++) {
      const nextLine = lines[j]
      if (!isYamlKeyLine(nextLine)) continue
      
      const nextIndentMatch = nextLine.match(/^(\s*)/)
      const nextIndent = nextIndentMatch ? nextIndentMatch[1].length : 0
      
      if (nextIndent > currentIndent) {
        indentSteps.push(nextIndent - currentIndent)
        break
      } else if (nextIndent <= currentIndent) {
        break
      }
    }
  }
  
  if (indentSteps.length === 0) return 2 // Default to 2 spaces if no pattern detected
  
  // Find the most common indentation step
  const stepCounts = indentSteps.reduce((acc, step) => {
    acc[step] = (acc[step] || 0) + 1
    return acc
  }, {} as Record<number, number>)
  
  return parseInt(Object.keys(stepCounts).reduce((a, b) => 
    stepCounts[parseInt(a)] > stepCounts[parseInt(b)] ? a : b
  ))
}

/**
 * YAML validation function for indentation errors - Fixed version for multiline strings
 */
export const validateYamlIndentation = (monaco: Monaco, model: editor.ITextModel) => {
  const markers: editor.IMarkerData[] = []
  const lines = model.getValue().split('\n')
  
  // Detect the document's indentation pattern
  const expectedIndentStep = detectIndentationPattern(lines)
  const indentationStack: number[] = []
  let inMultilineString = false
  let multilineStringIndent = 0
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const lineNumber = i + 1
    
    // Skip empty lines and comments
    if (line.trim() === '' || line.trim().startsWith('#')) {
      continue
    }
    
    // Calculate indentation level
    const indentMatch = line.match(/^(\s*)/)
    const indentLevel = indentMatch ? indentMatch[1].length : 0
    
    // Check for tabs (not allowed in YAML)
    if (line.includes('\t')) {
      markers.push({
        severity: monaco.MarkerSeverity.Error,
        message: 'Tabs are not allowed in YAML. Use spaces for indentation.',
        startLineNumber: lineNumber,
        startColumn: line.indexOf('\t') + 1,
        endLineNumber: lineNumber,
        endColumn: line.indexOf('\t') + 2
      })
    }
    
    // Check if we're entering a multiline string (literal | or folded >)
    const multilineStringMatch = line.match(/:\s*[\|>][-+]?\d*\s*$/)
    if (multilineStringMatch && isYamlKeyLine(line)) {
      inMultilineString = true
      // Set expected multiline string indentation to be greater than the key's indentation
      multilineStringIndent = indentLevel + expectedIndentStep
      continue
    }
    
    // If we're in a multiline string, validate differently
    if (inMultilineString) {
      // Check if we've exited the multiline string (line with same or less indentation than the key, and is a key line)
      if (indentLevel <= multilineStringIndent - expectedIndentStep && isYamlKeyLine(line)) {
        inMultilineString = false
        multilineStringIndent = 0
        // Continue with normal validation for this key line
      } else {
        // We're still in the multiline string - skip indentation validation
        // Only check that content has proper indentation (should be at least at multilineStringIndent level)
        if (line.trim() !== '' && indentLevel < multilineStringIndent && !line.trim().startsWith('#')) {
          // Allow for the first content line to establish the base indentation
          if (i > 0) {
            const prevContentLines = lines.slice(0, i).reverse()
            let hasContentLine = false
            for (const prevLine of prevContentLines) {
              if (prevLine.trim() !== '' && !prevLine.trim().startsWith('#') && !prevLine.match(/:\s*[\|>]/)) {
                hasContentLine = true
                break
              }
            }
            
            // Only show warning if there are already content lines in this multiline string
            if (hasContentLine) {
              markers.push({
                severity: monaco.MarkerSeverity.Warning,
                message: `Multiline string content should be indented at least ${multilineStringIndent} spaces.`,
                startLineNumber: lineNumber,
                startColumn: 1,
                endLineNumber: lineNumber,
                endColumn: indentLevel + 1
              })
            }
          }
        }
        continue
      }
    }
    
    // Only validate indentation for actual YAML key lines
    if (isYamlKeyLine(line)) {
      // Check for inconsistent indentation based on detected pattern
      if (indentationStack.length > 0) {
        const lastIndent = indentationStack[indentationStack.length - 1]
        
        if (indentLevel > lastIndent) {
          // This should be a child element - check if indentation follows the pattern
          const indentDifference = indentLevel - lastIndent
          if (indentDifference % expectedIndentStep !== 0) {
            markers.push({
              severity: monaco.MarkerSeverity.Warning,
              message: `Inconsistent indentation. This document uses ${expectedIndentStep}-space indentation. Expected ${lastIndent + expectedIndentStep} spaces, got ${indentLevel}.`,
              startLineNumber: lineNumber,
              startColumn: 1,
              endLineNumber: lineNumber,
              endColumn: indentLevel + 1
            })
          }
        } else if (indentLevel < lastIndent) {
          // Moving back to a parent level - check if it aligns with a previous level
          const validIndentLevels = [0, ...indentationStack.filter(level => level < indentLevel)]
          if (validIndentLevels.length > 0 && !validIndentLevels.includes(indentLevel)) {
            const nearestValidLevel = validIndentLevels.reduce((prev, curr) => 
              Math.abs(curr - indentLevel) < Math.abs(prev - indentLevel) ? curr : prev
            )
            markers.push({
              severity: monaco.MarkerSeverity.Warning,
              message: `Invalid indentation level. Expected ${nearestValidLevel} spaces to match parent level.`,
              startLineNumber: lineNumber,
              startColumn: 1,
              endLineNumber: lineNumber,
              endColumn: indentLevel + 1
            })
          }
        }
      }
      
      // Update indentation stack
      while (indentationStack.length > 0 && indentationStack[indentationStack.length - 1] >= indentLevel) {
        indentationStack.pop()
      }
      indentationStack.push(indentLevel)
    }
  }
  
  return markers
}

/**
 * Define custom Monaco Editor themes that match our Tailwind theme using standardized CSS variables
 */
export const defineCustomMonacoThemes = (monaco: Monaco): void => {
  // Enhanced token rules for YAML syntax highlighting using standardized editor colors
  const commonRules = [
    // Comments - using editor-comment color
    { token: 'comment', foreground: getEditorColor('--editor-comment'), fontStyle: 'italic' },
    
    // YAML Keys - using editor-key color with bold styling
    { token: 'key', foreground: getEditorColor('--editor-key'), fontStyle: 'bold' },
    { token: 'type', foreground: getEditorColor('--editor-key'), fontStyle: 'bold' },
    
    // Strings - using editor-string color (violet)
    { token: 'string', foreground: getEditorColor('--editor-string') },
    { token: 'string.yaml', foreground: getEditorColor('--editor-string') },
    
    // Numbers - using editor-number color (pink)
    { token: 'number', foreground: getEditorColor('--editor-number') },
    { token: 'number.yaml', foreground: getEditorColor('--editor-number') },
    
    // Keywords/Booleans - using editor-keyword color
    { token: 'keyword', foreground: getEditorColor('--editor-keyword'), fontStyle: 'bold' },
    { token: 'keyword.yaml', foreground: getEditorColor('--editor-keyword'), fontStyle: 'bold' },
    { token: 'boolean', foreground: getEditorColor('--editor-keyword') },
    
    // YAML Tags and document separators - using accent color
    { token: 'tag', foreground: getCssVar('--accent-foreground'), fontStyle: 'bold' },
    
    // Structural elements - using muted foreground
    { token: 'delimiter', foreground: getCssVar('--muted-foreground') },
    { token: 'delimiter.bracket', foreground: getCssVar('--muted-foreground') },
    { token: 'delimiter.comma', foreground: getCssVar('--muted-foreground') },
    { token: 'bracket', foreground: getCssVar('--muted-foreground') },
    
    // Identifiers - using string color (most YAML identifiers are string-like)
    { token: 'identifier', foreground: getEditorColor('--editor-string') },
    
    // Whitespace - minimal visibility for indentation guides
    { token: 'whitespace', foreground: getCssVar('--border') },
  ]

  // Create a light theme using CSS variables
  monaco.editor.defineTheme('plexusLightTheme', {
    base: 'vs',
    inherit: true,
    rules: commonRules,
    colors: {
      'editor.background': '#' + getCssVar('--background'),
      'editor.foreground': '#' + getCssVar('--foreground'),
      'editor.lineHighlightBackground': '#' + getCssVar('--muted') + '50',
      'editorLineNumber.foreground': '#' + getCssVar('--muted-foreground'),
      'editorLineNumber.activeForeground': '#' + getCssVar('--foreground'),
      'editor.selectionBackground': '#' + getCssVar('--primary') + '30', // primary with transparency
      'editor.selectionHighlightBackground': '#' + getCssVar('--muted'),
      'editorIndentGuide.background': '#' + getCssVar('--border'),
      'editorCursor.foreground': '#' + getCssVar('--foreground'),
      'editorWhitespace.foreground': '#' + getCssVar('--border'),
      'editor.findMatchBackground': '#' + getCssVar('--accent') + '40',
      'editor.findMatchHighlightBackground': '#' + getCssVar('--accent') + '20',
      'editorBracketMatch.background': '#' + getCssVar('--muted'),
      'editorBracketMatch.border': '#' + getCssVar('--border'),
    }
  } as editor.IStandaloneThemeData)

  // Create a dark theme using the same CSS variables (they adapt automatically)
  monaco.editor.defineTheme('plexusDarkTheme', {
    base: 'vs-dark',
    inherit: true,
    rules: commonRules, // Use the same rules - CSS variables will provide appropriate colors
    colors: {
      'editor.background': '#' + getCssVar('--background'),
      'editor.foreground': '#' + getCssVar('--foreground'),
      'editor.lineHighlightBackground': '#' + getCssVar('--muted') + '50',
      'editorLineNumber.foreground': '#' + getCssVar('--muted-foreground'),
      'editorLineNumber.activeForeground': '#' + getCssVar('--foreground'),
      'editor.selectionBackground': '#' + getCssVar('--primary') + '30', // primary with transparency
      'editor.selectionHighlightBackground': '#' + getCssVar('--muted'),
      'editorIndentGuide.background': '#' + getCssVar('--border'),
      'editorCursor.foreground': '#' + getCssVar('--foreground'),
      'editorWhitespace.foreground': '#' + getCssVar('--border'),
      'editor.findMatchBackground': '#' + getCssVar('--accent') + '40',
      'editor.findMatchHighlightBackground': '#' + getCssVar('--accent') + '20',
      'editorBracketMatch.background': '#' + getCssVar('--muted'),
      'editorBracketMatch.border': '#' + getCssVar('--border'),
    }
  } as editor.IStandaloneThemeData)
}

/**
 * Apply the appropriate Monaco theme based on the current dark/light mode
 */
export const applyMonacoTheme = (monaco: Monaco): void => {
  // Check if we're in dark mode
  const isDarkMode = document.documentElement.classList.contains('dark')
  
  // Force a refresh of CSS variables before applying theme
  const background = getComputedStyle(document.documentElement).getPropertyValue('--background').trim()
  const foreground = getComputedStyle(document.documentElement).getPropertyValue('--foreground').trim()
  
  // Redefine themes to ensure they have the latest CSS variables
  defineCustomMonacoThemes(monaco)
  
  // Apply the appropriate theme
  monaco.editor.setTheme(isDarkMode ? 'plexusDarkTheme' : 'plexusLightTheme')
}

/**
 * Set up theme change detection for Monaco editor
 */
export const setupMonacoThemeWatcher = (monaco: Monaco): (() => void) => {
  // Function to apply the appropriate theme
  const applyTheme = () => {
    if (!monaco) return
    applyMonacoTheme(monaco)
  }
  
  // Apply theme immediately
  applyTheme()
  
  // Set up a mutation observer to detect theme changes
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.attributeName === 'class') {
        applyTheme()
      }
    })
  })
  
  // Start observing the document element for class changes
  observer.observe(document.documentElement, { attributes: true })
  
  // Return cleanup function
  return () => {
    observer.disconnect()
  }
}

/**
 * Common Monaco editor options that work well with our theme
 */
export const getCommonMonacoOptions = (isMobileDevice = false): editor.IStandaloneEditorConstructionOptions => ({
  minimap: { enabled: false },
  fontSize: 15, // Increased from 14 for better readability
  lineHeight: 22, // Better line spacing
  lineNumbers: 'off', // Disabled line numbers
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  wrappingIndent: 'indent',
  automaticLayout: true,
  fontFamily: '"SF Mono", "Monaco", "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace',
  fontWeight: '500', // Slightly bolder for better visibility
  fontLigatures: true,
  contextmenu: true,
  cursorBlinking: 'smooth',
  cursorSmoothCaretAnimation: 'on',
  smoothScrolling: true,
  renderLineHighlight: 'all',
  colorDecorators: true,
  bracketPairColorization: { enabled: true }, // Better bracket matching
  guides: {
    bracketPairs: true,
    indentation: true,
  },
  // Remove editor borders/outlines
  overviewRulerBorder: false,
  hideCursorInOverviewRuler: true,
  // iPad/mobile specific options
  ...(isMobileDevice ? {
    // Reduce features that might cause issues on mobile
    quickSuggestions: false,
    parameterHints: { enabled: false },
    folding: false,
    dragAndDrop: false,
    links: false,
    // Optimize touch handling
    mouseWheelZoom: false,
    scrollbar: {
      useShadows: false,
      verticalHasArrows: true,
      horizontalHasArrows: true,
      vertical: 'visible',
      horizontal: 'visible',
      verticalScrollbarSize: 20,
      horizontalScrollbarSize: 20,
    },
    // Improve performance
    renderWhitespace: 'none',
    renderControlCharacters: false,
    renderIndentGuides: false,
  } : {})
}) 