# Input Sources for Plexus Scores

## Overview

Input sources allow scores to extract text from various sources (e.g., file attachments, Deepgram transcripts) instead of using the default `item.text` field.

## YAML Configuration

### New `item` Section

The `item` section specifies per-item processing configuration:

```yaml
item:
  class: DeepgramInputSource    # Optional: Input source class
  options:                       # Optional: Input source options
    pattern: ".*deepgram.*\\.json$"
    format: "paragraphs"
  processors:                    # Optional: Text processors
    - class: FilterCustomerOnlyProcessor
      parameters: {}
```

**Key Points:**
- `class` (optional): Input source class name. If omitted, uses default `item.text`
- `options` (optional): Configuration passed to input source
- `processors` (optional): Applied AFTER input source extraction

## Available Input Sources

### 1. TextFileInputSource

Extracts raw text from file attachments matching a regex pattern.

**Example:**
```yaml
item:
  class: TextFileInputSource
  options:
    pattern: ".*transcript\\.txt$"  # Regex to match filename
```

**Options:**
- `pattern` (required): Regex pattern to match attachment filenames

**Use Cases:**
- Plain text transcripts
- Preprocessed text files
- Any text-based attachments

### 2. DeepgramInputSource

Parses Deepgram JSON transcription files with multiple formatting options.

**Example:**
```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    format: "paragraphs"           # paragraphs, utterances, words, raw
    include_timestamps: false      # Include [X.XXs] markers
    speaker_labels: true           # Include "Speaker N:" prefixes
```

**Options:**
- `pattern` (required): Regex pattern to match Deepgram JSON files
- `format` (optional, default: "paragraphs"): Output format
  - `paragraphs`: Double-spaced paragraphs with speaker diarization
  - `utterances`: Single-spaced utterances (speaker turns)
  - `words`: Space-separated words
  - `raw`: Complete transcript as single string
- `include_timestamps` (optional, default: false): Add timestamp markers
- `speaker_labels` (optional, default: false): Add "Speaker N:" prefixes
- `time_range_start` (optional, default: 0.0): Start time in seconds for filtering
- `time_range_duration` (optional, default: None): Duration in seconds, or None for no end limit

**Format Examples:**

**Paragraphs (default):**
```
Hello, thank you for calling customer support. How can I help you today?

Hi, I'm having trouble with my account login.

I can definitely help you with that.
```

**Utterances:**
```
Hello, thank you for calling customer support. How can I help you today?
Hi, I'm having trouble with my account login.
I can definitely help you with that.
```

**With speaker labels:**
```
Speaker 0: Hello, thank you for calling customer support.
Speaker 1: Hi, I'm having trouble with my account login.
Speaker 0: I can definitely help you with that.
```

**With timestamps:**
```
[0.00s] Hello, thank you for calling customer support.
[5.00s] Hi, I'm having trouble with my account login.
[10.00s] I can definitely help you with that.
```

### Time-Based Slicing

DeepgramInputSource supports extracting specific time ranges from transcripts using the `time_range_start` and `time_range_duration` parameters.

**How It Works:**
- Elements (paragraphs/utterances/words) are included if they **start** within the time range
- Works independently of `include_timestamps` option (you can filter by time without displaying timestamps)
- Works across all format modes: paragraphs, utterances, words, raw

**Example Configurations:**

**Extract first minute:**
```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    format: "paragraphs"
    time_range_start: 0
    time_range_duration: 60
```

**Extract 2 minutes starting at 1:45 (105 seconds):**
```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    format: "utterances"
    time_range_start: 105
    time_range_duration: 120
```

**Extract everything after 5 minutes:**
```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    format: "words"
    time_range_start: 300
    # time_range_duration omitted = no end limit
```

**With floating-point precision:**
```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    time_range_start: 1.5
    time_range_duration: 3.2  # Extract 3.2 seconds starting at 1.5s
```

**Time slicing with timestamp display:**
```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    format: "paragraphs"
    include_timestamps: true     # Show timestamps in output
    time_range_start: 60         # But only for content from 60s onward
    time_range_duration: 30
```

**Parameter Behavior:**
- `time_range_start`: Defaults to 0 (beginning of transcript)
- `time_range_duration`: Defaults to None (no end limit - include everything from start)
- Inclusion rule: `time_range_start <= element.start < (time_range_start + time_range_duration)`
- If `time_range_duration` is None: Include all elements from `time_range_start` onward
- If time range extends beyond transcript: Include all elements that start within range
- If `time_range_start` exceeds transcript length: Return empty string

**Use Cases:**
- Analyze conversation openings (first 30 seconds)
- Focus on specific conversation phases (middle 2 minutes)
- Evaluate call closings (last minute)
- Split long conversations into segments for separate scoring
- Test scores on specific problematic time ranges

## Processing Pipeline

Text flows through this pipeline:

1. **Input Source** (if `item.class` specified)
   - Extracts text from attachment matching pattern
   - If no `item.class`: uses default `item.text`

2. **Processors** (if configured)
   - Priority: `item.processors` > `data.processors`
   - Transforms text (filters, modifications, etc.)

3. **Score Prediction**
   - Receives processed text
   - Runs LLM/classifier

## Migration Guide

### From Legacy Format

**Old (still works):**
```yaml
data:
  processors:
    - class: SomeProcessor
```

**New (recommended):**
```yaml
item:
  processors:
    - class: SomeProcessor
```

### Adding Input Sources

**Step 1: Add input source class**
```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    format: "paragraphs"
```

**Step 2: Move processors (optional)**
```yaml
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
  processors:  # Moved from data.processors
    - class: FilterCustomerOnlyProcessor
```

## Error Handling

Input sources use **strict error handling**:
- Missing attachments → `ValueError` with available files listed
- Invalid patterns → `ValueError` with clear message
- Download failures → Exception propagates
- No silent fallbacks (by design)

**Example error:**
```
ValueError: No Deepgram file matching pattern '.*deepgram.*\.json$' found.
Available attachments: ['s3://bucket/transcript.txt', 's3://bucket/metadata.xml']
```

## Examples

See example YAML files in this directory:
- [`score_with_deepgram_input.yaml`](./score_with_deepgram_input.yaml) - Deepgram transcript input
- [`score_with_text_file_input.yaml`](./score_with_text_file_input.yaml) - Text file input
- [`score_with_processors_only.yaml`](./score_with_processors_only.yaml) - Processors without input source
- [`score_legacy_format.yaml`](./score_legacy_format.yaml) - Legacy format (backwards compatible)

## Testing Input Sources

### 1. Test with Predictions

```bash
# Pull score configuration
plexus score pull --scorecard "My Scorecard" --score "My Score"

# Edit YAML to add input source
# Edit scorecards/MyScorecard/MyScore.yaml

# Push updated configuration
plexus score push --scorecard "My Scorecard" --score "My Score"

# Test prediction on item with attachment
plexus predict \
  --scorecard "My Scorecard" \
  --score "My Score" \
  --item-id "item-with-attachment" \
  --include-trace
```

### 2. Check Logs

Look for these log messages:
```
INFO: Using input source 'DeepgramInputSource' for score 'My Score'
INFO: Input source extracted 1234 characters
INFO: Using item.processors for 'My Score': ['FilterCustomerOnlyProcessor']
```

### 3. Run Evaluations

```bash
plexus evaluation run \
  --scorecard "My Scorecard" \
  --score "My Score" \
  --yaml \
  --n-samples 10
```

## Implementation Details

### Files Created

- `plexus/input_sources/InputSource.py` - Abstract base class
- `plexus/input_sources/TextFileInputSource.py` - Text file implementation
- `plexus/input_sources/DeepgramInputSource.py` - Deepgram implementation
- `plexus/input_sources/InputSourceFactory.py` - Factory pattern
- `plexus/input_sources/__init__.py` - Package exports

### Files Modified

- `plexus/Scorecard.py` - Input source integration and processor priority
- `plexus/Evaluation.py` - Item object fetching for evaluations
- `plexus/data/FeedbackItems.py` - Added `item_id` column to DataFrames

### Test Coverage

74 unit and integration tests covering:
- Input source base class functionality
- TextFileInputSource extraction and error handling
- DeepgramInputSource with all format options
- Factory instantiation and error handling
- Integration with score pipeline
- Backwards compatibility

## Future Enhancements

Potential future input sources:
- **AssemblyAIInputSource** - AssemblyAI transcripts
- **WhisperInputSource** - OpenAI Whisper format
- **PDFTextInputSource** - Extract text from PDFs
- **EmailBodyInputSource** - Extract email body from MIME
- **HTMLInputSource** - Parse and extract HTML content

## Support

For questions or issues, see:
- [Plexus Documentation](https://docs.plexus.ai)
- [GitHub Issues](https://github.com/AnthusAI/Plexus/issues)
