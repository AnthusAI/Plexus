# BERTopic Implementation Plan

## Overview
Implement topic modeling on call transcripts using BERTopic, focusing on customer speaking turns. The implementation will process Parquet files containing call transcripts into manageable chunks for analysis.

## Command Examples
### Basic Usage
```bash
# Run topic analysis on a transcript file
plexus analyze topics --input-file ~/projects/Call-Criteria-Python/.plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet

# Inspect data before processing
plexus analyze topics --input-file ~/projects/Call-Criteria-Python/.plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --inspect

# Specify custom content column
plexus analyze topics --input-file <path> --content-column text

# Specify output directory
plexus analyze topics --input-file <path> --output-dir ./output
```

### File Inspection
```bash
# View transformed Parquet file
python -c "import pandas as pd; df = pd.read_parquet('1039_no_score_id_Start-Date_csv-bertopic.parquet'); print(df.head())"

# View BERTopic text file
head -n 5 1039_no_score_id_Start-Date_csv-bertopic-text.txt
```

### Test Data Location
```bash
# Small test dataset
~/projects/Call-Criteria-Python/.plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet

# Large test dataset
~/projects/Call-Criteria-Python/.plexus_training_data_cache/dataframes/custom_555_60000_9627029a.parquet
```

### Current Command
```bash
# Run topic analysis with refined parameters
plexus analyze topics \
  --input-file ~/projects/Call-Criteria-Python/.plexus_training_data_cache/dataframes/custom_555_60000_9627029a.parquet \
  --output-dir ./output \
  --num-topics 40 \
  --min-ngram 1 \
  --max-ngram 2 \
  --min-topic-size 15 \
  --top-n-words 8
```

### LLM Integration Test
```bash
# Test Ollama LLM integration with default model and prompt
plexus analyze test-ollama

# Test with a specific model
plexus analyze test-ollama --model llama3:8b

# Test with a custom prompt
plexus analyze test-ollama --prompt "Explain the concept of topic modeling in simple terms"

# Test with both custom model and prompt
plexus analyze test-ollama --model codellama:7b --prompt "Write a Python function to calculate Fibonacci numbers"
```

## Progress
### Completed
1. Basic Infrastructure
   - ✅ Created directory structure (`plexus/cli/bertopic/`)
   - ✅ Set up test environment and dependencies

2. Data Transformation
   - ✅ Implemented `transformer.py` with:
     - ✅ `extract_speaking_turns()` function
     - ✅ `transform_transcripts()` function
     - ✅ `inspect_data()` utility
   - ✅ Successfully extracts customer speaking turns
   - ✅ Preserves metadata in Parquet file
   - ✅ Creates clean text file for BERTopic input

3. CLI Implementation
   - ✅ Added `topics` command to `AnalyzeCommands.py`
   - ✅ Configured input/output handling
   - ✅ Added data inspection option
   - ✅ Implemented content column configuration
   - ✅ Added `test-ollama` command for LLM integration testing

4. Verification
   - ✅ Inspected transformed Parquet file
   - ✅ Checked text file format
   - ✅ Validated customer turn extraction

### In Progress
1. LLM Integration
   - ✅ Added Ollama test command
   - [ ] Set up environment for LLM usage
   - [ ] Test various Ollama models

2. BERTopic Integration
   - [ ] Configure BERTopic with default settings
   - [ ] Generate topic visualizations
   - [ ] Add analysis to CLI command

3. Enhancements
   - [ ] Add progress tracking
   - [ ] Improve error handling
   - [ ] Add more CLI options (e.g., BERTopic parameters)
   - [ ] Integrate LLM for topic labeling

## File Structure
```
plexus/
├── cli/
│   ├── AnalyzeCommands.py
│   └── bertopic/
│       ├── __init__.py
│       ├── transformer.py
│       ├── analyzer.py
│       ├── ollama_test.py
│       └── test_inspect.py
```

## Technical Details
### Data Transformation
- Input: Parquet files with transcript data
- Output:
  - Cached Parquet file (same directory as input)
  - Text file for BERTopic input (one turn per line)
- Customer turn extraction:
  - Splits on "Agent:" and "Customer:" markers
  - Filters out very short turns (< 2 words)
  - Preserves all metadata in Parquet file

### BERTopic Configuration
- Use default settings for proof-of-concept
- Focus on customer speaking turns only
- Generate basic visualizations

## Testing Plan
1. [x] Test data transformation
   - [x] Verify customer turn extraction
   - [x] Check metadata preservation
   - [x] Validate text file format
2. [ ] Test BERTopic analysis
   - [ ] Verify topic generation
   - [ ] Check visualization output
3. [ ] Integration testing with CLI

## Future Enhancements
1. Customizable BERTopic parameters
2. Advanced visualization options
3. Topic labeling and interpretation
4. Integration with dashboard

## Dependencies
- pandas
- BERTopic
- sentence-transformers
- hdbscan
- plotly