# Multi-Modal Input Refactoring - Item.to_score_input()

## Status: ✅ COMPLETE - Ready for Evaluation Testing

This refactoring enables Plexus scores to use different input sources (Deepgram JSON, text files, images, etc.) instead of being limited to `item.text`.

---

## What Was Implemented

### Core Architecture

**New Method**: `Item.to_score_input(item_config) -> ScoreInput`

The Item model now transforms itself into a ScoreInput object, using an optional `item_config` to specify which InputSource to use:

```python
# Default behavior (no config) - uses item.text
score_input = item.to_score_input(item_config=None)

# With DeepgramInputSource
item_config = {
    'class': 'DeepgramInputSource',
    'options': {
        'pattern': '.*deepgram.*\\.json$',
        'format': 'paragraphs',
        'time_range_start': 0,
        'time_range_duration': 60
    }
}
score_input = item.to_score_input(item_config=item_config)
```

**YAML Configuration**:
```yaml
# In score YAML file
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    format: "paragraphs"
    time_range_start: 0
    time_range_duration: 60
```

### Modified Components

1. **plexus/dashboard/api/models/item.py**
   - Added `to_score_input(item_config)` method
   - Handles metadata parsing (JSON string → dict)
   - Graceful fallback to item.text on errors

2. **plexus/input_sources/DeepgramInputSource.py**
   - Returns `ScoreInput` instead of string
   - Fixed S3 bucket routing (auto-detects DataSources vs ScoreResultAttachments)
   - Fixed paragraph parsing (handles production JSON with `sentences` array)
   - Supports time slicing with `time_range_start` and `time_range_duration`

3. **plexus/cli/prediction/predictions.py**
   - Modified `select_sample()` to load score YAML and extract `item:` config
   - Passes item_config to `Item.to_score_input()`
   - Added logging to show exact Score.Input text going to classifier

4. **plexus/scores/LangGraphScore.py**
   - Fixed psycopg import issue (lazy loading with graceful fallback)

---

## Proof of Control - 4 Tests

We proved complete control over the classifier input by running 4 tests with different configurations:

| Test | Configuration | Text Length | % Change | Key Feature |
|------|--------------|-------------|----------|-------------|
| 1 | No item config | 2,758 chars | Baseline | Uses item.text with speaker labels |
| 2 | Paragraphs format | 1,632 chars | -41% | Speaker labels removed, formatted |
| 3 | Words format | 1,550 chars | -44% | Lowercase, no punctuation |
| 4 | Time slice (60s) | 517 chars | **-81%** | **Only first 60 seconds!** |

**Logged Output Examples**:

```
# Test 1: No item config
📝 SCORE.INPUT GOING TO CLASSIFIER:
   - Text length: 2758 characters
   - First 300 chars: Agent: Thank you for calling Renewal by Andersen and Provia...

# Test 4: Time slice (first 60 seconds)
📝 SCORE.INPUT GOING TO CLASSIFIER:
   - Text length: 517 characters
   - First 300 chars: Thank you for calling Renewal by Andersen and Provia...
```

---

## Issues Fixed

### 1. S3 Bucket Auto-Detection
**Problem**: Item attachments are in DataSources bucket, but code was looking in ScoreResultAttachments bucket.

**Solution**: `download_from_s3()` now auto-detects bucket based on path prefix:
- `items/*` or `datasets/*` → DataSources bucket
- `score_results/*` → ScoreResultAttachments bucket

### 2. Deepgram Paragraph Structure
**Problem**: Production JSON has `{"transcript": "...", "sentences": [...]}` but tests assumed `{"paragraphs": {...]}`.

**Solution**: Updated `DeepgramInputSource.extract()` to parse production format correctly.

### 3. psycopg Import Blocking CLI
**Problem**: Unconditional import of PostgreSQL library blocked CLI when not installed.

**Solution**: Made import lazy with graceful fallback to in-memory checkpointer.

### 4. Prediction Results Not Found
**Problem**: Results dict keyed by score UUID, but code searched by score name.

**Solution**: Added fallback to check `parameters.key` and `parameters.name`.

### 5. Item Config Loading
**Problem**: Score YAML `item:` section wasn't being passed to `Item.to_score_input()`.

**Solution**: Modified `select_sample()` to load YAML, extract `item:` config, and pass it through.

---

## Test Results

### Unit Tests ✅
```bash
$ pytest tests/test_input_sources/
```
- ✅ test_text_file_input_source.py (3 tests)
- ✅ test_deepgram_input_source.py (4 tests)
- ✅ test_scorecard_integration.py (1 test)
- ✅ test_input_source_factory.py (4 tests)

### Integration Tests ✅
```bash
$ python3 -m plexus.cli predict --scorecard aw_confirmation --score opening_company_name \
  --item "9c929f25-a91f-4db7-8943-5aa93498b8e9--299298112" --yaml
```

**Results**:
- ✅ Item fetched from API
- ✅ Score YAML loaded with `item:` config
- ✅ DeepgramInputSource extracted text from S3
- ✅ Time slicing reduced text to 517 chars (first 60 seconds)
- ✅ Prediction executed: Value = "Yes"

---

## Next Steps: Evaluation Testing

**Blocking Issue**: Cannot run evaluations from current machine because it's not whitelisted to access the CallCriteriaDBCache database.

**Action Required**:
1. Commit this refactoring to repository
2. Move to whitelisted machine
3. Run evaluations to verify multi-modal input works in evaluation pipeline:
   ```bash
   python3 -m plexus.cli evaluate accuracy \
     --scorecard aw_confirmation \
     --score opening_company_name \
     --number-of-samples 10 \
     --yaml
   ```

**Expected Behavior**:
- Evaluation should load score YAML
- Extract `item:` config for each sample
- Call `Item.to_score_input(item_config)` for each item
- Use DeepgramInputSource to extract first 60 seconds
- Generate predictions and compute accuracy metrics

---

## Technical Details

### Pipeline Flow

```
Item (from API)
  ↓
Item.to_score_input(item_config)
  ↓
[if item_config specified]
  ↓
InputSource.extract(item)
  ↓
Download from S3 (auto-detect bucket)
  ↓
Parse format (Deepgram JSON, text file, etc.)
  ↓
Apply transformations (time slicing, formatting)
  ↓
ScoreInput(text=processed_text, metadata={...})
  ↓
Scorecard.score_entire_text(score_input)
  ↓
Score.predict(score_input)
  ↓
Classifier receives exact text we specified!
```

### Files Modified

**Core Implementation**:
- `plexus/dashboard/api/models/item.py` - Added `to_score_input()` method
- `plexus/input_sources/DeepgramInputSource.py` - Returns ScoreInput, fixed parsing
- `plexus/input_sources/TextFileInputSource.py` - Returns ScoreInput
- `plexus/input_sources/score_input.py` - Lightweight ScoreInput class

**CLI Integration**:
- `plexus/cli/prediction/predictions.py` - Loads item config from YAML, passes to to_score_input()

**Bug Fixes**:
- `plexus/utils/score_result_s3_utils.py` - S3 bucket auto-detection
- `plexus/scores/LangGraphScore.py` - Lazy psycopg import

**Tests**:
- `tests/test_input_sources/test_deepgram_input_source.py` - Added paragraph structure tests
- `tests/test_input_sources/test_text_file_input_source.py` - Rewrote with boto3 mocking
- `tests/test_input_sources/test_scorecard_integration.py` - End-to-end test
- `tests/test_input_sources/test_input_source_factory.py` - Factory pattern tests

### Configuration Example

```yaml
# scorecards/AW - Confirmation/opening_company_name.yaml
name: Opening (Company Name)
key: opening_company_name
class: LangGraphScore
# ... model config ...
item:
  class: DeepgramInputSource
  options:
    pattern: ".*deepgram.*\\.json$"
    format: "paragraphs"           # or "words" for lowercase no-punct
    time_range_start: 0             # Start at beginning
    time_range_duration: 60         # Only first 60 seconds
data:
  class: CallCriteriaDBCache
  # ... data config ...
```

---

## Git Commit Message

```
feat: Add multi-modal input support via Item.to_score_input()

Enable scores to use different input sources (Deepgram JSON, text files, etc.)
instead of being limited to item.text. This allows time-slicing audio transcripts,
extracting from attachments, and using different text formats.

Key changes:
- Added Item.to_score_input(item_config) method
- Modified InputSources to return ScoreInput objects
- CLI loads item: config from score YAML and passes to to_score_input()
- Fixed S3 bucket auto-detection (DataSources vs ScoreResultAttachments)
- Fixed Deepgram JSON parsing for production format
- Added comprehensive logging of Score.Input text before classification

Tested with real production data:
- Default mode: 2,758 chars (item.text)
- With time slicing: 517 chars (81% reduction, first 60 seconds only)
- Predictions execute successfully with controlled input

Ready for evaluation testing on whitelisted machine.
```
