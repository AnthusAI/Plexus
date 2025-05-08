# BERTopic Implementation Plan

## Overview
Implement topic modeling on call transcripts using BERTopic, focusing on customer speaking turns. The implementation will process Parquet files containing call transcripts into manageable chunks for analysis, with options for LLM-based transformation including direct question extraction.

## Command Examples
### Basic Usage
```bash
# Run topic analysis on a transcript file
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet

# Inspect data before processing
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --inspect

# Specify custom content column
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file <path> --content-column text

# Extract and analyze only customer utterances
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --customer-only

# Specify output directory
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file <path> --output-dir ./output
```

### LLM Transformation (New)
```bash
# Use LLM to transform transcripts with Ollama (default provider)
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform llm

# Use custom prompt template with Ollama
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform llm --prompt-template plexus/cli/bertopic/prompts/summary.json --llm-model gemma3:27b

# Use OpenAI for transformation with custom model
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform llm --provider openai --llm-model gpt-4o-mini

# Use OpenAI to analyze customer-only utterances
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform llm --provider openai --llm-model gpt-4o-mini --customer-only

# Force regeneration of cached files
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform llm --fresh
```

### Topic Representation with OpenAI (New)
```bash
# Use OpenAI to generate better topic labels and representations
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --use-representation-model

# Combine with other parameters
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --use-representation-model --num-topics 20 --min-topic-size 15

# Use with transformed transcripts
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform llm --provider openai --use-representation-model
```

### Customer Question Extraction (New)
```bash
# Extract direct customer questions using Ollama
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform itemize

# Extract questions using OpenAI with custom prompt template (actual command in use)
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform itemize --prompt-template plexus/cli/bertopic/prompts/itemize.json --fresh --provider openai --llm-model gpt-4o-mini

# Extract customer questions using OpenAI (only on customer utterances)
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform itemize --prompt-template plexus/cli/bertopic/prompts/itemize.json --provider openai --llm-model gpt-4o-mini --customer-only

# Customize retry behavior for parsing failures
python3 -m plexus.cli.CommandLineInterface analyze topics --input-file .plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet --transform itemize --max-retries 3
```

### File Inspection
```bash
# View transformed Parquet file
python -c "import pandas as pd; df = pd.read_parquet('1039_no_score_id_Start-Date_csv-bertopic-itemize-openai.parquet'); print(df.head())"

# View BERTopic text file
head -n 5 1039_no_score_id_Start-Date_csv-bertopic-itemize-openai-text.txt
```

### Test Data Location
```bash
# Small test dataset
.plexus_training_data_cache/dataframes/1039_no_score_id_Start-Date_csv.parquet

# Large test dataset
.plexus_training_data_cache/dataframes/custom_555_60000_9627029a.parquet
```

### Current Command
```bash
# Run topic analysis with refined parameters
python3 -m plexus.cli.CommandLineInterface analyze topics \
  --input-file .plexus_training_data_cache/dataframes/custom_555_60000_9627029a.parquet \
  --output-dir ./output \
  --num-topics 40 \
  --min-ngram 1 \
  --max-ngram 2 \
  --min-topic-size 15 \
  --top-n-words 8 \
  --use-representation-model
```

### LLM Integration Test
```bash
# Test Ollama LLM integration with default model and prompt
python3 -m plexus.cli.CommandLineInterface analyze test-ollama

# Test with a specific Ollama model
python3 -m plexus.cli.CommandLineInterface analyze test-ollama --model gemma3:27b

# Test OpenAI integration
python3 -m plexus.cli.CommandLineInterface analyze test-ollama --provider openai --model gpt-4o-mini

# Test with a custom prompt
python3 -m plexus.cli.CommandLineInterface analyze test-ollama --prompt "Explain the concept of topic modeling in simple terms"
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
     - ✅ `transform_transcripts_llm()` function
     - ✅ `transform_transcripts_itemize()` function
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
   - ✅ Added LLM-based transformation option
   - ✅ Added customer question extraction option
   - ✅ Added support for multiple LLM providers (Ollama, OpenAI)

4. Verification
   - ✅ Inspected transformed Parquet file
   - ✅ Checked text file format
   - ✅ Validated customer turn extraction

5. LLM Integration
   - ✅ Added Ollama test command
   - ✅ Integrated LLM-based transformation with Ollama and LangChain
   - ✅ Added OpenAI integration via LangChain
   - ✅ Added prompt template support
   - ✅ Added robust JSON parsing for LLM outputs
   - ✅ Implemented customer question extraction with structured output
   - ✅ Integrated OpenAI for topic representation and labeling

### In Progress
1. BERTopic Integration
   - [ ] Configure BERTopic with default settings
   - [ ] Generate topic visualizations
   - [ ] Add analysis to CLI command

2. Enhancements
   - [ ] Add progress tracking
   - [ ] Add more CLI options (e.g., BERTopic parameters)
   - [x] Integrate LLM for topic labeling

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
│       ├── prompts/
│       │   ├── itemize.json
│       │   └── summary.json
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
- Customer-only filtering:
  - Optional preprocessing step that extracts only customer utterances
  - Removes all "Agent:" portions of the transcript
  - Preserves only "Customer:" portions concatenated together
  - Useful for focusing analysis specifically on customer language
- LLM-based transformation:
  - Processes entire transcripts through LLM (Ollama or OpenAI)
  - Uses configurable prompt templates via JSON files
  - Creates more concise, focused text for topic analysis
  - Preserves metadata in Parquet file
  - Supports multiple LLM providers with appropriate model selection
- Customer question extraction:
  - Uses structured output parsing with Pydantic models
  - Extracts direct questions asked by customers from transcripts
  - Creates a separate row for each extracted question
  - Includes retry logic for parsing failures
  - Handles JSON parsing with robust error handling
  - Preserves all metadata from original rows
  - Compatible with both Ollama and OpenAI providers

### OpenAI Topic Representation
- How it works:
  - After BERTopic generates topics and their keyword representations
  - For each topic, the most representative documents and keywords are selected
  - These are sent to OpenAI's gpt-4o-mini with a specialized prompt
  - The LLM generates a human-readable label/description for each topic
  - These labels replace the default keyword representations in visualizations and topic info
- Technical implementation:
  - Uses BERTopic's built-in representation_model feature
  - Integrates with OpenAI API through the official client
  - Custom prompt focuses specifically on call center contexts
  - Uses the format "topic: <label>" for parsing the response
  - Includes fallback mechanisms if the OpenAI API fails
- Benefits over default keyword representation:
  - More intuitive, human-readable topic labels
  - Context-aware interpretation (understands call center terminology)
  - Reduces need for manual review of topic keywords
  - Makes visualizations more immediately interpretable
  - Example transformations:
    - "refund_payment_order" → "Customer Refund Processing Issues"
    - "product_not_working_help" → "Technical Support for Product Malfunctions"
    - "delivery_shipping_time" → "Shipping and Delivery Timeline Inquiries"
- Implementation difference from transcript transformation:
  - Transcript transformation occurs before topic modeling (preprocessing)
  - Topic representation occurs after topic modeling (postprocessing)
  - Both can use OpenAI but serve different purposes in the pipeline
  - Can be used together to get maximum benefit from LLMs

### BERTopic Configuration
- Use default settings for proof-of-concept
- Focus on customer speaking turns only
- Generate basic visualizations
- OpenAI representation model integration:
  - Uses gpt-4o-mini to generate human-readable topic labels
  - Customized prompt focused on call center/customer service context
  - Transforms keyword-based topics into meaningful descriptions
  - Example: "refund_shipping_order" → "Customer Refund and Shipping Issues"
  - Integration via the `--use-representation-model` flag with required API key

## Prompt Template Format
LLM transformation uses JSON files for prompt templates:

```json
{
  "template": "Extract the main topics from this call transcript. For each topic, provide 1-2 concise sentences in bullet point format. Focus on customer issues, product mentions, and key discussion points only.\n\n{text}\n\nTopics:"
}
```

The template must include a `{text}` placeholder where the transcript will be inserted.

### Question Extraction Template Format
Question extraction templates also use JSON files with escaped curly braces for JSON structure:

```json
{
  "template": "You are a helpful assistant that extracts customer questions from call transcripts. Your task is to identify the direct questions that customers asked during the call.\n\nAnalyze this call transcript and identify 1-10 direct questions asked by the customer. Extract each question as a direct quote exactly as the customer phrased it.\n\nYou MUST return ONLY a valid JSON object without any explanation text or markdown formatting.\n\nThe JSON object MUST follow this EXACT structure:\n{{\n  \"items\": [\n    {{\n      \"quote\": \"How much was I charged for my recent purchase?\"\n    }},\n    {{\n      \"quote\": \"When will my order be delivered?\"\n    }}\n  ]\n}}\n\nTranscript:\n{text}\n\n{format_instructions}"
}
```

The template must include `{text}` and `{format_instructions}` placeholders, and any JSON structure in the template must use double curly braces `{{` and `}}` to escape them in the string formatter.

## LLM Provider Configuration
- Default provider is `ollama` for local LLM usage
- OpenAI can be used with `--provider openai`
- When using OpenAI, API key can be provided via:
  - `--openai-api-key` parameter
  - `OPENAI_API_KEY` environment variable
- Appropriate model name must be provided for each provider:
  - Ollama: `gemma3:27b`, `llama3:8b`, etc.
  - OpenAI: `gpt-3.5-turbo`, `gpt-4`, `gpt-4o-mini`, etc.
- For topic representation, OpenAI API key is required with the `--use-representation-model` flag

## Testing Plan
1. [x] Test data transformation
   - [x] Verify customer turn extraction
   - [x] Check metadata preservation
   - [x] Validate text file format
2. [x] Test LLM integration
   - [x] Verify Ollama connectivity
   - [x] Verify OpenAI connectivity
   - [x] Test JSON parsing from LLM output
   - [x] Test structured question extraction
3. [ ] Test BERTopic analysis
   - [ ] Verify topic generation
   - [ ] Check visualization output
4. [ ] Integration testing with CLI

## Future Enhancements
1. Customizable BERTopic parameters
2. Advanced visualization options
3. Topic labeling and interpretation
4. Integration with dashboard
5. Support for more LLM providers beyond Ollama and OpenAI

## Dependencies
- pandas
- BERTopic
- sentence-transformers
- hdbscan
- plotly
- langchain
- ollama (for Ollama provider)
- langchain-openai (for OpenAI provider)
- pydantic
- openai (for OpenAI representation model)