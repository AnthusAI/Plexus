# Classification with Confidence - Implementation Plan

## Overview

Add confidence scoring to the Classifier node by analyzing log probabilities from the first token of LLM responses. This feature will provide uncalibrated confidence values that can be used for filtering predictions and improving classification reliability.

## Core Requirements

### 1. First Token Strategy
- **Assumption**: The first token always represents the complete classification decision
- **Benefit**: Eliminates parsing complexity around multi-token outputs, punctuation, quotes
- **Enforcement**: Requires `parse_from_start: true` to be enabled
- **Fine-tuning**: Model fine-tuning will ensure first token reliability and meaningful confidence scores

### 2. Logprobs Aggregation
- Extract logprobs for the first token from LangChain/OpenAI response
- Identify all predicted tokens that could represent the same classification value
- Sum probabilities for token variants (e.g., "yes", "Yes", "YES") 
- Return aggregated probability as uncalibrated confidence score

## Implementation Tasks

### Task 1: Extend Classifier Parameters
**File**: `plexus/scores/nodes/Classifier.py`

Add new parameters to `Classifier.Parameters`:
```python
enable_confidence: bool = False
```

### Task 2: Extend GraphState
**File**: `plexus/scores/nodes/Classifier.py`

Add to `Classifier.GraphState`:
```python
confidence: Optional[float] = None
raw_logprobs: Optional[Dict] = None
```

### Task 3: Modify LLM Call for Logprobs
**File**: `plexus/scores/nodes/Classifier.py`

- Detect OpenAI models when `enable_confidence=True`
- Bind `logprobs=True, top_logprobs=10` to model
- Extract logprobs from `response.response_metadata`
- Store in `state.raw_logprobs`

### Task 4: Implement Confidence Calculation
**File**: `plexus/scores/nodes/Classifier.py`

Create new node method `get_confidence_node()`:
- Extract first token logprobs from `state.raw_logprobs`
- Map tokens to valid classifications using existing normalization logic
- Aggregate probabilities for matching classification variants
- Set `state.confidence` with final score

### Task 5: Update Workflow Graph
**File**: `plexus/scores/nodes/Classifier.py`

- Add confidence node to workflow when `enable_confidence=True`
- Insert between parse and retry nodes
- Ensure confidence calculation happens after successful classification

### Task 6: Add YAML Configuration Support
**File**: Score YAML parsing logic

Support new parameter in score configuration:
```yaml
- name: my_classifier
  class: Classifier
  enable_confidence: true  # New parameter
  parse_from_start: true   # Required when confidence enabled
```

### Task 7: Add Grammar Validation Rule
**Files**: YAML linter/grammar checker (TypeScript and Python versions)

Add validation rule:
- If `enable_confidence: true`, then `parse_from_start` must be `true`
- Provide clear error message when validation fails

### Task 8: Update Documentation
**File**: `plexus/docs/score-yaml-format.md`

Add concise section:

```markdown
## Confidence Scoring

Enable confidence calculation based on first token log probabilities:

```yaml
- name: confident_classifier
  class: Classifier
  enable_confidence: true    # Enable confidence scoring
  parse_from_start: true     # Required for confidence mode
  valid_classes: ["Yes", "No"]
```

When enabled:
- Returns `confidence` field with uncalibrated probability (0.0-1.0)
- Requires `parse_from_start: true` 
- Works best with fine-tuned models
- Only supported with OpenAI models
```

## Technical Details

### Token Mapping Logic
Reuse existing `normalize_text()` method from parser:
1. Normalize predicted token (lowercase, strip spaces)
2. Normalize each valid class 
3. Match normalized strings
4. Sum probabilities for all matching tokens

### Model Compatibility
- **Supported**: OpenAI models (ChatOpenAI, AzureChatOpenAI)
- **Unsupported**: Other providers (feature gracefully disabled)
- **Future**: Extend to other providers as logprobs become available

### Error Handling
- Missing logprobs: Set `confidence = None`, log warning
- Invalid tokens: Skip unrecognized tokens in aggregation
- Non-OpenAI models: Disable feature, log info message

## Validation Rules

### Grammar Checker Updates
Add to both TypeScript and Python linters:

```python
def validate_confidence_config(node_config):
    if node_config.get('enable_confidence'):
        if not node_config.get('parse_from_start'):
            raise ValidationError(
                "enable_confidence requires parse_from_start: true"
            )
```

## Testing Strategy

### Unit Tests
- Token mapping with various capitalizations
- Probability aggregation logic
- Error handling for missing logprobs
- Grammar validation rules

### Integration Tests  
- End-to-end confidence calculation
- YAML configuration parsing
- Workflow execution with confidence enabled

### Manual Testing
- Compare confidence scores across different model responses
- Verify first token assumption holds with fine-tuned models
- Test with various classification scenarios

## Future Enhancements

### Calibration Support
- Add optional calibration dataset parameter
- Implement Platt scaling or isotonic regression
- Convert raw probabilities to calibrated confidence scores

### Multi-Provider Support
- Extend to Anthropic, Bedrock when logprobs available
- Abstract logprobs extraction interface

### Advanced Token Handling
- Support for multi-character classifications (A/B/C mapping)
- Custom token mapping configurations

## Success Criteria

1. ✅ Confidence scores correlate with classification accuracy
2. ✅ Feature integrates seamlessly with existing Classifier workflow
3. ✅ Grammar validation prevents invalid configurations
4. ✅ Documentation enables easy adoption
5. ✅ Performance impact is minimal (<10% latency increase)

## Dependencies

- LangChain OpenAI integration with logprobs support
- Existing Classifier normalization logic
- YAML configuration parsing system
- Grammar validation framework

## Estimated Effort

- **Core Implementation**: 2-3 days
- **Testing & Validation**: 1-2 days  
- **Documentation & Integration**: 1 day
- **Total**: 4-6 days

