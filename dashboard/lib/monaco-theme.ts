import type { Monaco } from '@monaco-editor/react'
import type { editor } from 'monaco-editor'

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
 * Define custom Monaco Editor themes that match our Tailwind theme using standardized CSS variables
 */
export const defineCustomMonacoThemes = (monaco: Monaco): void => {
  // Improved token rules using standardized editor colors
  const commonRules = [
    // Comments - using editor-comment color
    { token: 'comment', foreground: getEditorColor('--editor-comment'), fontStyle: 'italic' },
    
    // Keys - using editor-key color  
    { token: 'type', foreground: getEditorColor('--editor-key'), fontStyle: 'bold' },
    { token: 'key', foreground: getEditorColor('--editor-key'), fontStyle: 'bold' },
    
    // Strings - using editor-string color (violet)
    { token: 'string', foreground: getEditorColor('--editor-string') },
    { token: 'string.yaml', foreground: getEditorColor('--editor-string') },
    
    // Numbers - using editor-number color (pink)
    { token: 'number', foreground: getEditorColor('--editor-number') },
    { token: 'number.yaml', foreground: getEditorColor('--editor-number') },
    
    // Booleans - using editor-keyword color
    { token: 'boolean', foreground: getEditorColor('--editor-keyword') },
    
    // Structural elements - using muted foreground
    { token: 'delimiter', foreground: getCssVar('--muted-foreground') },
    { token: 'bracket', foreground: getCssVar('--muted-foreground') },
    
    // Keywords - using editor-keyword color
    { token: 'keyword', foreground: getEditorColor('--editor-keyword'), fontStyle: 'bold' },
    { token: 'keyword.yaml', foreground: getEditorColor('--editor-keyword'), fontStyle: 'bold' },
    
    // Identifiers - using foreground color
    { token: 'identifier', foreground: getCssVar('--foreground') },
    
    // YAML specific tags - using editor-key color
    { token: 'tag', foreground: getEditorColor('--editor-key'), fontStyle: 'bold' },
  ]

  // Create a light theme using CSS variables
  monaco.editor.defineTheme('plexusLightTheme', {
    base: 'vs',
    inherit: true,
    rules: commonRules,
    colors: {
      'editor.background': '#' + getCssVar('--background'),
      'editor.foreground': '#' + getCssVar('--foreground'),
      'editor.lineHighlightBackground': '#' + getCssVar('--muted'),
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
      'editor.lineHighlightBackground': '#' + getCssVar('--muted'),
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
  lineNumbers: 'on',
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