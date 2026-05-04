# Configurable Parameters System

## Overview

The Configurable Parameters System provides a reusable dialog component that allows users to input parameters based on YAML configuration. It supports various parameter types including text, numbers, booleans, selects, and specialized Plexus entity selectors (scorecards, scores, score versions).

## Components

### Core Components

1. **ConfigurableParametersDialog** (`dashboard/components/ui/ConfigurableParametersDialog.tsx`)
   - Main dialog component that renders parameters and handles validation
   - Props:
     - `open`: boolean
     - `onOpenChange`: (open: boolean) => void
     - `title`: string
     - `description?`: string
     - `parameters`: ParameterDefinition[]
     - `onSubmit`: (values: ParameterValue) => void | Promise<void>
     - `submitLabel?`: string
     - `cancelLabel?`: string

2. **Parameter Type Components** (`dashboard/components/ui/parameter-types/`)
   - TextParameter
   - NumberParameter
   - BooleanParameter
   - SelectParameter
   - ScorecardSelectParameter
   - ScoreSelectParameter
   - ScoreVersionSelectParameter

### Utilities

1. **parameter-parser.ts** (`dashboard/lib/parameter-parser.ts`)
   - `parseParametersFromYaml(yamlContent: string)`: Extract parameters from YAML
   - `hasParameters(yamlContent: string)`: Check if YAML contains parameters
   - `validateParameters(values, definitions)`: Validate parameter values
   - `getDefaultValues(definitions)`: Get default values for parameters

2. **Type Definitions** (`dashboard/types/parameters.ts`)
   - `ParameterType`: Union type of all supported parameter types
   - `ParameterDefinition`: Interface for parameter configuration
   - `ParameterValue`: Type for parameter values

## YAML Parameter Format

### Basic Structure

```yaml
parameters:
  - name: parameter_name
    label: Display Label
    type: text|number|boolean|select|scorecard_select|score_select|score_version_select
    required: true|false
    default: default_value
    description: Help text for the parameter
    placeholder: Placeholder text
```

### Parameter Types

#### Text
```yaml
- name: description
  label: Description
  type: text
  required: false
  placeholder: Enter description
  description: Optional description for the procedure
```

#### Number
```yaml
- name: max_iterations
  label: Max Iterations
  type: number
  required: true
  default: 10
  min: 1
  max: 100
  description: Maximum number of iterations
```

#### Boolean
```yaml
- name: auto_start
  label: Auto Start
  type: boolean
  default: false
  description: Automatically start the procedure
```

#### Select
```yaml
- name: environment
  label: Environment
  type: select
  required: true
  options:
    - value: dev
      label: Development
    - value: prod
      label: Production
  default: dev
```

#### Scorecard Select
```yaml
- name: scorecard_id
  label: Scorecard
  type: scorecard_select
  required: true
  description: Select the scorecard for this procedure
```

#### Score Select (with dependency)
```yaml
- name: score_id
  label: Score
  type: score_select
  required: true
  depends_on: scorecard_id
  description: Select the score to use
```

#### Score Version Select (with dependency)
```yaml
- name: score_version_id
  label: Score Version
  type: score_version_select
  required: false
  depends_on: score_id
  description: Optionally select a specific version
```

### Automatic Name Variable Injection

**For Report Configurations Only**: When using `scorecard_select` or `score_select` parameter types in report configurations, the system automatically resolves the identifier to the actual object and injects a corresponding `{parameter_name}_name` variable into the template context.

This allows templates to reference both the identifier (which could be an ID, key, external ID, or name) and the resolved human-readable name.

#### How It Works

1. **Parameter Definition**: Define a parameter with type `scorecard_select` or `score_select`
2. **User Input**: User provides an identifier (ID, key, external ID, or name)
3. **Automatic Resolution**: System looks up the object in the database
4. **Name Injection**: Adds `{parameter_name}_name` variable with the resolved name
5. **Template Rendering**: Both variables are available in Jinja2 templates

#### Example

```yaml
parameters:
  - name: scorecard
    label: Scorecard
    type: scorecard_select
    required: true
  - name: days
    label: Days
    type: number
    default: 30

---

# Feedback Analysis Report

## Scorecard: {{ scorecard_name }}
## Last {{ days }} days

This report analyzes scorecard {{ scorecard }} ({{ scorecard_name }}) 
over the last {{ days }} days.
```

**User provides**: `scorecard=2bcaf6b9-c937-4ac5-9d89-8f3862518692`

**System injects**: `scorecard_name="Call Criteria"`

**Rendered output**:
```markdown
# Feedback Analysis Report

## Scorecard: Call Criteria
## Last 30 days

This report analyzes scorecard 2bcaf6b9-c937-4ac5-9d89-8f3862518692 (Call Criteria)
over the last 30 days.
```

#### Supported Parameter Types

- **`scorecard_select`**: Automatically adds `{parameter_name}_name` with the scorecard's name
- **`score_select`**: Automatically adds `{parameter_name}_name` with the score's name

#### Fallback Behavior

If the system cannot resolve the identifier (e.g., invalid ID, network error), it falls back to using the identifier itself as the name. This ensures reports always render successfully, even if resolution fails.

#### Notes

- This feature is **only available in report configurations** (not procedures or other parameter uses)
- The original parameter value is preserved - only an additional `_name` variable is added
- Name resolution happens after parameter validation and before Jinja2 template rendering
- For `score_select` parameters, the system uses the `depends_on` field to find the scorecard context

## Usage Examples

### Procedure Template with Parameters

```yaml
# Example procedure template YAML
name: Hypothesis Generation
description: Generate and test hypotheses

parameters:
  - name: scorecard_id
    label: Scorecard
    type: scorecard_select
    required: true
    description: Select the scorecard for this procedure
    
  - name: score_id
    label: Score
    type: score_select
    required: true
    depends_on: scorecard_id
    description: Select the score to evaluate
    
  - name: score_version_id
    label: Score Version
    type: score_version_select
    required: false
    depends_on: score_id
    description: Optionally select a specific version (defaults to champion)
    
  - name: max_iterations
    label: Max Iterations
    type: number
    required: true
    default: 10
    min: 1
    max: 100
    description: Maximum number of iterations to run
    
  - name: beam_width
    label: Beam Width
    type: number
    required: true
    default: 3
    min: 1
    max: 10
    description: Number of parallel hypotheses to maintain

# ... rest of template configuration
```

### Integrating with Your Component

```typescript
import { ConfigurableParametersDialog } from '@/components/ui/ConfigurableParametersDialog'
import { parseParametersFromYaml, hasParameters } from '@/lib/parameter-parser'

// Check if template has parameters
if (hasParameters(template.yaml)) {
  const parameters = parseParametersFromYaml(template.yaml)
  
  // Show dialog
  <ConfigurableParametersDialog
    open={showDialog}
    onOpenChange={setShowDialog}
    title="Configure Procedure"
    description="Set up your procedure parameters"
    parameters={parameters}
    onSubmit={(values) => {
      console.log('User submitted:', values)
      // Use values to create your resource
    }}
    submitLabel="Create"
  />
}
```

## Validation

The system automatically validates:
- Required fields
- Number min/max constraints
- Type correctness (number vs text, etc.)
- Dependencies (dependent fields require parent field to be set)

Validation errors are displayed inline next to each field.

## Dependency Handling

Parameters can depend on other parameters using `depends_on`:

```yaml
- name: parent_field
  label: Parent
  type: select
  
- name: child_field
  label: Child
  type: select
  depends_on: parent_field  # This field is disabled until parent_field has a value
```

When a parent field changes, all dependent fields are automatically cleared.

## Testing

### Unit Tests
- `dashboard/lib/__tests__/parameter-parser.test.ts` - Parser and validation tests
- `dashboard/components/ui/__tests__/ConfigurableParametersDialog.test.tsx` - Component tests

### Storybook Stories
- `dashboard/stories/ConfigurableParametersDialog.stories.tsx` - Interactive examples

Run tests:
```bash
cd dashboard
npm test -- --testPathPattern="parameter"
```

View in Storybook:
```bash
npm run storybook
```

## Current Integrations

1. **Procedures Dashboard**
   - Template selection checks for parameters
   - Shows parameter dialog before creating procedure
   - Parameters passed to procedure creation

## Future Integrations

1. **Report Configurations**
   - Add parameters to report YAML
   - Show dialog before running report
   - Pass parameters to report generation

2. **Other Use Cases**
   - Task dispatch with custom parameters
   - Evaluation configuration
   - Any feature requiring user input based on YAML config



